"""Roteiro de validação da superfície HTTP do Commercial Passport.

Este roteiro valida a segurança da API antes de qualquer habilitação produtiva:
- Por padrão, a rota deve estar ausente quando `TITAN_COMMERCIAL_PASSPORT_API_ENABLED`
  está desligada.
- Quando publicada por feature flag, GET dinâmico e POST de emissão formal devem
  exigir autenticação antes de revelar qualquer informação de produtor, propriedade,
  animais, readiness, Dossier ou VerificationBundle.

Uso:
python -m uv run --locked python -m apps.validacao.commercial_passport_api
python -m uv run --locked python -m apps.validacao.commercial_passport_api --pausar
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from apps.validacao.runner import CINZA, FIM, NEGRITO, VERDE, VERMELHO

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=os.environ.get("TITAN_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--pausar", action="store_true")
    args = parser.parse_args()
    base_url = str(args.api)

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
