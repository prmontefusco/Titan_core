"""Roteiro de validação da superfície HTTP do Commercial Passport.

Este roteiro valida a segurança da API antes de qualquer habilitação produtiva:
- Por padrão, a rota deve estar ausente quando `TITAN_COMMERCIAL_PASSPORT_API_ENABLED`
  está desligada.
- Quando publicada por feature flag, GET dinâmico e POST de emissão formal devem
  exigir autenticação antes de revelar qualquer informação de produtor, propriedade,
  animais, readiness, Dossier ou VerificationBundle.
- Com `--autenticado`, também valida que usuários locais semeados passam pelo
  gate de autenticação/permissão, mas a API segue fail-closed em 503 enquanto a
  pipeline produtiva não estiver injetada.

Uso:
python -m uv run --locked python -m apps.validacao.commercial_passport_api
python -m uv run --locked python -m apps.validacao.commercial_passport_api --autenticado
python -m uv run --locked python -m apps.validacao.commercial_passport_api --pausar
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import (
    AMARELO,
    CINZA,
    FIM,
    NEGRITO,
    VERDE,
    VERMELHO,
    Cliente,
    Requisicao,
    Resposta,
    Roteiro,
)

PROPERTY_ID = "00000000-0000-0000-0000-000000000001"
GET_ROUTE_TEMPLATE = "/v1/livestock/properties/{property_id}/commercial-passport"
ISSUE_ROUTE_TEMPLATE = "/v1/livestock/properties/{property_id}/commercial-passport/issue"
GET_ROUTE = GET_ROUTE_TEMPLATE.format(property_id=PROPERTY_ID)
ISSUE_ROUTE = ISSUE_ROUTE_TEMPLATE.format(property_id=PROPERTY_ID)


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: Any


def _request(
    *,
    base_url: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> HttpResponse:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return HttpResponse(
                status=response.status,
                headers={key.lower(): value for key, value in response.headers.items()},
                body=json.loads(raw) if raw else None,
            )
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            payload: Any = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw.decode("utf-8", errors="replace")
        return HttpResponse(
            status=error.code,
            headers={key.lower(): value for key, value in error.headers.items()},
            body=payload,
        )
    except urllib.error.URLError as error:
        raise SystemExit(
            f"{VERMELHO}A API não respondeu: {error.reason}{FIM}\n"
            "Suba a API antes de rodar o roteiro (ex: uvicorn apps.api.main:app)."
        ) from error


def _query() -> str:
    return "reference_time=2026-09-11T00%3A00%3A00Z&knowledge_cutoff=2026-09-11T00%3A00%3A00Z"


def _issue_body() -> dict[str, Any]:
    return {
        "reference_time": "2026-09-11T00:00:00Z",
        "knowledge_cutoff": "2026-09-11T00:00:00Z",
        "audience": "internal-audit",
    }


def _print_body(value: Any) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    for line in text.splitlines()[:32]:
        print(f"{CINZA}     {line}{FIM}")


def _pause(enabled: bool) -> None:
    if enabled:
        input(f"{CINZA}  — ENTER para o próximo —{FIM}")


def _route_is_published(openapi: dict[str, Any], route_template: str) -> bool:
    return route_template in openapi.get("paths", {})


def _property_from_listing(operador: Cliente) -> str:
    resposta = operador.get("/v1/livestock/properties?limit=1")
    if resposta.status != 200 or not resposta["items"]:
        raise SystemExit(
            f"Não achei propriedade nesta Organization (status {resposta.status}).\n"
            "Rode a semeadura, ou confira se a API subiu com a configuração certa."
        )
    return str(resposta["items"][0]["property_id"])


def _reason_code(expected: str) -> Callable[[Resposta], str | None]:
    def conferir(resposta: Resposta) -> str | None:
        reason_code = (
            resposta.corpo.get("reason_code") if isinstance(resposta.corpo, dict) else None
        )
        if reason_code == expected:
            return None
        return f"reason_code veio {reason_code!r}, esperado {expected!r}"

    return conferir


def _authenticated_clients(
    *,
    api: str,
    organizacao: str,
    keycloak_url: str,
    realm: str,
) -> tuple[Cliente, Cliente]:
    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    diario: list[Requisicao] = []

    def cliente(username: str, rotulo: str) -> Cliente:
        return Cliente(
            base_url=api,
            token=admin.token_de_usuario(
                client_id=CLIENTE_DE_VALIDACAO,
                username=username,
                senha=SENHA_DEMONSTRACAO,
            ),
            organization_id=organizacao,
            rotulo=rotulo,
            diario=diario,
        )

    return cliente("titan_operador", "operador"), cliente("titan_auditor", "auditor")


def _authenticated_validation(
    *,
    api: str,
    organizacao: str,
    keycloak_url: str,
    realm: str,
    pausar: bool,
) -> int:
    operador, auditor = _authenticated_clients(
        api=api,
        organizacao=organizacao,
        keycloak_url=keycloak_url,
        realm=realm,
    )
    propriedade = _property_from_listing(operador)
    get_route = GET_ROUTE_TEMPLATE.format(property_id=propriedade)
    issue_route = ISSUE_ROUTE_TEMPLATE.format(property_id=propriedade)

    print(f"\n{NEGRITO}Ambiente autenticado{FIM}")
    print(f"  API          : {api}")
    print(f"  Keycloak     : {keycloak_url} (realm {realm})")
    print(f"  Organization : {organizacao}")
    print(f"  Propriedade  : {propriedade}")
    print(f"{CINZA}  Rode a semeadura novamente se vier 403 por permissão ausente.{FIM}")

    roteiro = Roteiro(
        "Commercial Passport — gate autenticado e pipeline fail-closed",
        diario=operador.diario,
    )
    roteiro.passo(
        "4",
        "Operador consulta projection dinâmica com permissão de propriedade",
        lambda: operador.get(f"{get_route}?{_query()}"),
        503,
        conferir=_reason_code("COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO"),
        porque=(
            "Depois de autenticar e autorizar, a rota ainda não pode fabricar passaporte; "
            "sem pipeline produtiva injetada, deve falhar fechado."
        ),
    )
    roteiro.passo(
        "5",
        "Auditor solicita emissão formal com permissão de Dossier",
        lambda: auditor.post(issue_route, _issue_body()),
        503,
        conferir=_reason_code("COMMERCIAL_PASSPORT_ISSUANCE_NAO_HABILITADA"),
        porque=(
            "A emissão formal exige autorização, mas também não deve criar Dossier ou "
            "VerificationBundle sem a pipeline produtiva."
        ),
    )
    codigo = roteiro.executar(pausar=pausar)
    if codigo == 0:
        print(
            f"{AMARELO}O roteiro autenticado valida o portão técnico; "
            f"a aprovação de negócio continua humana.{FIM}"
        )
    return codigo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=os.environ.get("TITAN_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument(
        "--autenticado",
        action="store_true",
        help="Também valida chamadas autenticadas contra usuários locais semeados.",
    )
    parser.add_argument("--organizacao", default="")
    parser.add_argument("--pausar", action="store_true")
    args = parser.parse_args()
    base_url = str(args.api)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    print(f"\n{NEGRITO}Commercial Passport — superfície HTTP protegida{FIM}")
    print("=" * 58)
    print(f"{CINZA}API: {base_url}{FIM}")

    print(f"\n{NEGRITO}[1] Descobrir se as rotas estão publicadas no OpenAPI{FIM}")
    print(
        f"{CINZA}  Por que: a feature flag controla a existência pública da consulta "
        f"dinâmica e da emissão formal.{FIM}"
    )
    print(f"  {CINZA}->{FIM} {NEGRITO}GET{FIM} /openapi.json")
    openapi_response = _request(base_url=base_url, method="GET", path="/openapi.json")
    print(f"  {CINZA}<-{FIM} {NEGRITO}{openapi_response.status}{FIM}")
    if openapi_response.status != 200 or not isinstance(openapi_response.body, dict):
        print(f"{VERMELHO}OpenAPI indisponível; não é possível validar a superfície.{FIM}")
        _print_body(openapi_response.body)
        return 1
    openapi = openapi_response.body
    get_published = _route_is_published(openapi, GET_ROUTE_TEMPLATE)
    issue_published = _route_is_published(openapi, ISSUE_ROUTE_TEMPLATE)
    if get_published != issue_published:
        print(f"{VERMELHO}FALHOU{FIM} — consulta e emissão divergiram no release gate.")
        print(f"{CINZA}GET publicado: {get_published}; ISSUE publicado: {issue_published}{FIM}")
        return 1
    print(
        f"{VERDE}OK{FIM} — rotas "
        f"{'publicadas por feature flag' if get_published else 'ausentes/default-off'}"
    )
    _pause(args.pausar)

    print(f"\n{NEGRITO}[2] Chamar consulta dinâmica sem autenticação{FIM}")
    print(
        f"{CINZA}  Por que: a consulta não pode revelar propriedade, readiness, gaps "
        f"ou população antes de autenticar.{FIM}"
    )
    get_path = f"{GET_ROUTE}?{_query()}"
    print(f"  {CINZA}->{FIM} {NEGRITO}GET{FIM} {get_path}")
    get_response = _request(base_url=base_url, method="GET", path=get_path)
    print(f"  {CINZA}<-{FIM} {NEGRITO}{get_response.status}{FIM}")
    _print_body(get_response.body)
    expected = 401 if get_published else 404
    if get_response.status != expected:
        print(
            f"{VERMELHO}FALHOU{FIM} — esperava {expected} "
            f"({'rota autenticada' if get_published else 'rota ausente'})."
        )
        return 1
    _pause(args.pausar)

    print(f"\n{NEGRITO}[3] Chamar emissão formal sem autenticação{FIM}")
    print(
        f"{CINZA}  Por que: emissão formal não pode produzir Dossier/VerificationBundle "
        f"ou IDs/digests antes de autenticar e autorizar.{FIM}"
    )
    print(f"  {CINZA}->{FIM} {NEGRITO}POST{FIM} {ISSUE_ROUTE}")
    _print_body(_issue_body())
    issue_response = _request(
        base_url=base_url,
        method="POST",
        path=ISSUE_ROUTE,
        body=_issue_body(),
    )
    print(f"  {CINZA}<-{FIM} {NEGRITO}{issue_response.status}{FIM}")
    _print_body(issue_response.body)
    if issue_response.status != expected:
        print(
            f"{VERMELHO}FALHOU{FIM} — esperava {expected} "
            f"({'rota autenticada' if issue_published else 'rota ausente'})."
        )
        return 1

    print(
        f"{VERDE}OK{FIM} — nenhuma informação de Commercial Passport foi liberada sem autenticação."
    )
    if not args.autenticado:
        return 0
    if not get_published:
        print(
            f"{AMARELO}Validação autenticada ignorada:{FIM} as rotas não estão publicadas. "
            "Suba a API com TITAN_COMMERCIAL_PASSPORT_API_ENABLED=true."
        )
        return 1

    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url and not args.organizacao:
        raise SystemExit(
            "Defina TITAN_DATABASE_URL (para descobrir a Organization) ou passe --organizacao."
        )
    organizacao = str(args.organizacao) or _descobrir_organizacao(database_url)
    return _authenticated_validation(
        api=base_url,
        organizacao=organizacao,
        keycloak_url=keycloak_url,
        realm=realm,
        pausar=bool(args.pausar),
    )


if __name__ == "__main__":
    raise SystemExit(main())
