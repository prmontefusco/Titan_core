"""Roteiro executável de `OpenStockPosition`."""

from __future__ import annotations

import argparse
import os
import sys
from uuid import uuid4

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _descobrir_escopo(database_url: str, organization_id: str) -> tuple[str, str, str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT p.part_id, l.location_id, purposes.purpose "
                    "FROM core_audit.parts p CROSS JOIN core_audit.stock_locations l "
                    "CROSS JOIN (VALUES ('PRODUCTION'), ('SERVICE_SLI'), ('OM_REMOTE'), "
                    "('COMMERCIAL')) AS purposes(purpose) "
                    "WHERE p.record_owner_organization_id = :organization_id "
                    "AND l.record_owner_organization_id = :organization_id "
                    "AND NOT EXISTS (SELECT 1 FROM core_audit.stock_positions s "
                    "WHERE s.record_owner_organization_id = :organization_id "
                    "AND s.part_id = p.part_id AND s.location_id = l.location_id "
                    "AND s.purpose = purposes.purpose) "
                    "ORDER BY p.created_at DESC, l.location_id, purposes.purpose LIMIT 1"
                ),
                {"organization_id": organization_id},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma combinação inédita de Part, StockLocation e purpose foi encontrada. "
            "Prepare massa fictícia adicional."
        )
    return str(row[0]), str(row[1]), str(row[2])


def _exigir_permissao(cliente: Cliente) -> None:
    probe = cliente.post(
        "/v1/asset/stock-positions",
        {},
        headers={"Idempotency-Key": f"asset-stock-position-sonda-{uuid4()}"},
    )
    if probe.status == 403 and isinstance(probe.corpo, dict):
        if probe.corpo.get("reason_code") == "PERMISSAO_AUSENTE":
            raise SystemExit(
                f"{AMARELO}O usuário não possui ASSET_INVENTORY.OPEN_POSITION.{FIM} "
                "Semeie novamente e reinicie a API com a operadora nova."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — abrir posição de estoque.")
    parser.add_argument("--pausar", action="store_true")
    parser.add_argument("--organizacao", default="")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Part e StockLocation.")
    admin = AdminKeycloak.autenticar(
        base_url=keycloak,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    subject = admin.garantir_usuario(username="titan_operador", senha=SENHA_DEMONSTRACAO)
    organization = args.organizacao or _descobrir_organizacao(
        database_url, issuer=f"{keycloak}/realms/{realm}", subject=subject
    )
    part_id, location_id, purpose = _descobrir_escopo(database_url, organization)
    diary: list[Requisicao] = []
    client = Cliente(
        base_url=api,
        token=admin.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO,
            username="titan_operador",
            senha=SENHA_DEMONSTRACAO,
        ),
        organization_id=organization,
        rotulo="operador",
        diario=diary,
    )
    _exigir_permissao(client)
    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  Organization  : {organization}")
    print(f"  Part          : {part_id}")
    print(f"  StockLocation : {location_id}")
    print(f"  Purpose       : {purpose}")
    print(f"{CINZA}  O escopo inédito foi descoberto automaticamente.{FIM}")
    roteiro = Roteiro("Asset A5 — OpenStockPosition", diario=diary)
    roteiro.passo(
        "1",
        "Abrir posição com quantidades fictícias por bucket",
        lambda: client.post(
            "/v1/asset/stock-positions",
            {
                "part_id": part_id,
                "location_id": location_id,
                "purpose": purpose,
                "ownership": "COMPANY_OWNED",
                "on_hand": "10",
                "quarantine": "2",
                "lot": f"VALIDACAO-{uuid4().hex[:8].upper()}",
            },
            headers={"Idempotency-Key": f"asset-stock-position-{uuid4()}"},
        ),
        201,
        conferir=lambda response: (
            None
            if response["part_ref"] == part_id
            and response["location_ref"] == location_id
            and response["purpose"] == purpose
            and response["available"] == "8"
            else "resposta não preservou escopo e breakdown esperado"
        ),
        porque="Confirma que estoque nasce somente numa StockPosition explícita (I-INV-0).",
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
