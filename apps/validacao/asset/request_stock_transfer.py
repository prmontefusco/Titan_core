"""Roteiro executável de `RequestStockTransfer`."""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _descobrir_rota(database_url: str, organization_id: str) -> tuple[str, str, str, str, Decimal]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    WITH positions AS (
                        SELECT p.part_id, p.location_id, p.purpose,
                               p.on_hand - p.quarantine - p.inspection - p.damaged
                               - COALESCE(sum(r.qty), 0) AS available
                        FROM core_audit.stock_positions p
                        LEFT JOIN core_audit.stock_position_reservations r
                          ON r.stock_position_id = p.stock_position_id
                        WHERE p.record_owner_organization_id = :organization_id
                        GROUP BY p.stock_position_id
                    )
                    SELECT source.part_id, source.location_id, destination.location_id,
                           source.purpose, LEAST(source.available, 1)
                    FROM positions source
                    JOIN positions destination
                      ON destination.part_id = source.part_id
                     AND destination.purpose = source.purpose
                     AND destination.location_id <> source.location_id
                    WHERE source.available > 0
                    ORDER BY source.part_id, source.location_id, destination.location_id
                    LIMIT 1
                    """
                ),
                {"organization_id": organization_id},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhum par de StockPositions compatíveis foi encontrado. Crie duas posições da mesma "
            "peça e propósito em localizações diferentes, com saldo disponível na origem."
        )
    return str(row[0]), str(row[1]), str(row[2]), str(row[3]), Decimal(row[4])


def _exigir_permissao(cliente: Cliente) -> None:
    probe = cliente.post(
        "/v1/asset/stock-transfers",
        {},
        headers={"Idempotency-Key": f"asset-request-transfer-sonda-{uuid4()}"},
    )
    if probe.status == 403 and isinstance(probe.corpo, dict):
        if probe.corpo.get("reason_code") == "PERMISSAO_AUSENTE":
            raise SystemExit(
                f"{AMARELO}O usuário não possui ASSET_INVENTORY.TRANSFER_REQUEST.{FIM} "
                "Semeie novamente e reinicie a API com a operadora nova."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — solicitar transferência.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir as posições de estoque.")
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
    part_id, from_location_id, to_location_id, purpose, qty = _descobrir_rota(
        database_url, organization
    )
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
    print(f"  Organization : {organization}")
    print(f"  Part         : {part_id}")
    print(f"  Origem       : {from_location_id}")
    print(f"  Destino      : {to_location_id}")
    print(f"  Purpose      : {purpose}")
    print(f"  Quantidade   : {qty}")
    print(f"{CINZA}  Rota e quantidade foram descobertas automaticamente.{FIM}")
    roteiro = Roteiro("Asset A5 — RequestStockTransfer", diario=diary)
    roteiro.passo(
        "1",
        "Solicitar transferência entre posições compatíveis",
        lambda: client.post(
            "/v1/asset/stock-transfers",
            {
                "part_id": part_id,
                "from_location_id": from_location_id,
                "to_location_id": to_location_id,
                "purpose": purpose,
                "qty": str(qty),
            },
            headers={"Idempotency-Key": f"asset-request-transfer-{uuid4()}"},
        ),
        201,
        conferir=lambda response: (
            None
            if response["state"] == "REQUESTED"
            and response["purpose"] == purpose
            and Decimal(response["qty"]) == qty
            else "resposta não confirmou a transferência solicitada"
        ),
        porque="Confirma disponibilidade e compatibilidade de peça e propósito nas duas pontas.",
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
