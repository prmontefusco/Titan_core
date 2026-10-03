"""Roteiro executável para validar `GET /v1/asset/availability`.

python -m uv run --locked python -m apps.validacao.asset.availability
python -m uv run --locked python -m apps.validacao.asset.availability --pausar

O roteiro não pede identificadores manualmente: descobre a Organization do
usuário de validação e a primeira StockPosition no banco local.
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlencode

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _descobrir_posicao(database_url: str, organizacao: str) -> tuple[str, str, str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT part_id, location_id, purpose FROM core_audit.stock_positions "
                    "WHERE record_owner_organization_id = :organization_id "
                    "ORDER BY stock_position_id ASC LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma StockPosition encontrada para esta Organization. "
            "Rode a semeadura/fixture Asset antes de validar disponibilidade."
        )
    return str(row[0]), str(row[1]), str(row[2])


def _availability_path(part_id: str, location_id: str, purpose: str) -> str:
    query = urlencode({"part_id": part_id, "location_id": location_id, "purpose": purpose})
    return f"/v1/asset/availability?{query}"


def _exigir_permissao_inventory_read(
    cliente: Cliente, part_id: str, location_id: str, purpose: str
) -> None:
    sonda = cliente.get(_availability_path(part_id, location_id, purpose))
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui ASSET_INVENTORY.READ.{FIM}\n"
            "Papéis guardam as permissões existentes quando foram criados. "
            "Semeie novamente com as permissões Asset e reinicie a API."
        )


def _montar_roteiro(cliente: Cliente, part_id: str, location_id: str, purpose: str) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Availability", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Consultar disponibilidade de estoque",
        lambda: cliente.get(_availability_path(part_id, location_id, purpose)),
        200,
        conferir=lambda r: (
            None
            if r["part_ref"] == part_id
            and r["location_ref"] == location_id
            and r["purpose"] == purpose
            and isinstance(r["breakdown"], dict)
            and "available" in r["breakdown"]
            else "resposta não preservou part_ref, location_ref, purpose ou breakdown"
        ),
        porque=(
            "Confirma que A5 expõe AvailabilityBreakdown explicável por peça, "
            "localização e propósito, sem executar reserva ou ajuste de estoque."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — Availability.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Organization e StockPosition.")

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
    part_id, location_id, purpose = _descobrir_posicao(database_url, organizacao)

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
    print(f"  Part         : {part_id}")
    print(f"  Location     : {location_id}")
    print(f"  Purpose      : {purpose}")
    print(
        f"{CINZA}  Organization, Part, Location e Purpose foram descobertos; "
        f"nada foi copiado à mão.{FIM}"
    )

    _exigir_permissao_inventory_read(operador, part_id, location_id, purpose)
    code = _montar_roteiro(operador, part_id, location_id, purpose).executar(pausar=args.pausar)
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
