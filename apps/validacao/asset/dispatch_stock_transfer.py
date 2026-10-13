"""Roteiro executável de `DispatchStockTransfer`."""

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


def _descobrir_transferencia(
    database_url: str, organization_id: str
) -> tuple[str, int, Decimal, Decimal]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    WITH positions AS (
                        SELECT p.stock_position_id, p.part_id, p.location_id, p.purpose,
                               p.on_hand,
                               p.on_hand - p.quarantine - p.inspection - p.damaged
                               - COALESCE(sum(r.qty), 0) AS available
                        FROM core_audit.stock_positions p
                        LEFT JOIN core_audit.stock_position_reservations r
                          ON r.stock_position_id = p.stock_position_id
                        WHERE p.record_owner_organization_id = :organization_id
                        GROUP BY p.stock_position_id
                    )
                    SELECT t.transfer_id, t.version, source.on_hand, source.available
                    FROM core_audit.stock_transfers t
                    JOIN positions source
                      ON source.part_id = t.part_id
                     AND source.location_id = t.from_location_id
                     AND source.purpose = t.purpose
                    WHERE t.record_owner_organization_id = :organization_id
                      AND t.state = 'REQUESTED'
                      AND source.available >= t.qty
                    ORDER BY t.transfer_id
                    LIMIT 1
                    """
                ),
                {"organization_id": organization_id},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma StockTransfer REQUESTED com disponibilidade suficiente foi encontrada. "
            "Execute primeiro apps.validacao.asset.request_stock_transfer."
        )
    return str(row[0]), int(row[1]), Decimal(row[2]), Decimal(row[3])


def _exigir_permissao(cliente: Cliente, transfer_id: str) -> None:
    probe = cliente.post(
        f"/v1/asset/stock-transfers/{transfer_id}/dispatch",
        {},
        headers={"Idempotency-Key": f"asset-dispatch-transfer-sonda-{uuid4()}"},
    )
    if probe.status == 403 and isinstance(probe.corpo, dict):
        if probe.corpo.get("reason_code") == "PERMISSAO_AUSENTE":
            raise SystemExit(
                f"{AMARELO}O usuário não possui ASSET_INVENTORY.TRANSFER_DISPATCH.{FIM} "
                "Semeie novamente e reinicie a API com a operadora nova."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — despachar transferência.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir a transferência.")
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
    transfer_id, version, on_hand_before, available_before = _descobrir_transferencia(
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
    _exigir_permissao(client, transfer_id)
    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  Organization       : {organization}")
    print(f"  StockTransfer      : {transfer_id}")
    print(f"  Versão esperada    : {version}")
    print(f"  On hand na origem  : {on_hand_before}")
    print(f"  Disponível origem  : {available_before}")
    print(f"{CINZA}  Transferência e versão foram descobertas automaticamente.{FIM}")
    roteiro = Roteiro("Asset A5 — DispatchStockTransfer", diario=diary)
    roteiro.passo(
        "1",
        "Despachar transferência solicitada",
        lambda: client.post(
            f"/v1/asset/stock-transfers/{transfer_id}/dispatch",
            {"expected_version": version},
            headers={"Idempotency-Key": f"asset-dispatch-transfer-{uuid4()}"},
        ),
        200,
        conferir=lambda response: (
            None
            if response["transfer"]["state"] == "IN_TRANSIT"
            and Decimal(response["source_stock_position"]["on_hand"])
            == on_hand_before - Decimal(response["transfer"]["qty"])
            else "despacho não confirmou trânsito e baixa integral na origem"
        ),
        porque=(
            "Confirma que a quantidade deixa o on_hand da origem e passa a existir somente na "
            "transferência em trânsito."
        ),
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
