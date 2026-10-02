"""Roteiro executável para validar `GET /v1/asset/fleet-view`.

python -m uv run --locked python -m apps.validacao.asset.fleet_view
python -m uv run --locked python -m apps.validacao.asset.fleet_view --pausar

O roteiro não pede identificadores manualmente: descobre a Organization do
usuário de validação e, quando existir, o primeiro `CustomerSite` Asset para
validar o filtro opcional. Cada passo mostra requisição e resposta formatadas.
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _descobrir_site_opcional(database_url: str, organizacao: str) -> str | None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT site_id FROM core_audit.customer_sites "
                    "WHERE record_owner_organization_id = :organization_id "
                    "ORDER BY code ASC LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    return None if row is None else str(row[0])


def _exigir_permissao_vehicle_read(cliente: Cliente) -> None:
    sonda = cliente.get("/v1/asset/fleet-view")
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui ASSET_VEHICLE.READ.{FIM}\n"
            "Papéis guardam as permissões existentes quando foram criados. "
            "Semeie novamente com as permissões Asset e reinicie a API."
        )


def _montar_roteiro(cliente: Cliente, site_id: str | None) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Fleet View", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Consultar visão operacional da frota inteira",
        lambda: cliente.get("/v1/asset/fleet-view"),
        200,
        conferir=lambda r: (
            None
            if r["site_ref"] is None
            and isinstance(r["lines"], list)
            and isinstance(r["counts_by_state"], dict)
            else "resposta não preservou site_ref nulo, lines ou counts_by_state"
        ),
        porque=(
            "Confirma que A5 expõe a projection A6 da frota sem materializar nova "
            "fonte de verdade: estados operacionais são derivados de Vehicle e WorkOrder."
        ),
    )
    if site_id is not None:
        roteiro.passo(
            "2",
            "Consultar visão operacional filtrada por site",
            lambda: cliente.get(f"/v1/asset/fleet-view?site_id={site_id}"),
            200,
            conferir=lambda r: (
                None
                if r["site_ref"] == site_id and isinstance(r["lines"], list)
                else "resposta filtrada não preservou site_ref ou lines"
            ),
            porque=(
                "Confirma que o filtro opcional por CustomerSite é aceito sem copiar "
                "identificador manualmente entre ferramentas."
            ),
        )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — Fleet View.")
    parser.add_argument("--pausar", action="store_true")
    parser.add_argument(
        "--organizacao", default="", help="Organization do teste. Sem isto, descobre pelo vínculo."
    )
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Organization Asset.")

    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    subject = admin.garantir_usuario(username="titan_operador", senha=SENHA_DEMONSTRACAO)
    issuer = f"{keycloak_url}/realms/{realm}"
    organizacao = args.organizacao or _descobrir_organizacao(
        database_url, issuer=issuer, subject=subject
    )
    site_id = _descobrir_site_opcional(database_url, organizacao)

    diario: list[Requisicao] = []
    operador = Cliente(
        base_url=api,
        token=admin.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO,
            username="titan_operador",
            senha=SENHA_DEMONSTRACAO,
        ),
        organization_id=organizacao,
        rotulo="operador",
        diario=diario,
    )

    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  API          : {api}")
    print(f"  Keycloak     : {keycloak_url} (realm {realm})")
    print(f"  Organization : {organizacao}")
    if site_id is None:
        print(f"{CINZA}  CustomerSite : nenhum encontrado; filtro opcional será pulado.{FIM}")
    else:
        print(f"  CustomerSite : {site_id}")
    print(f"{CINZA}  Organization e CustomerSite foram descobertos; nada foi copiado à mão.{FIM}")

    _exigir_permissao_vehicle_read(operador)
    code = _montar_roteiro(operador, site_id).executar(pausar=args.pausar)
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
