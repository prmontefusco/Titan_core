"""Roteiro executável de `ConsumeStock`."""

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


def _descobrir_consumo(database_url: str, organization_id: str) -> tuple[str, str, Decimal, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT r.reservation_id, w.work_order_id, r.qty, r.version "
                    "FROM core_audit.stock_reservations r "
                    "JOIN core_audit.work_orders w "
                    "ON r.reservation_id = ANY(w.material_reservations) "
                    "WHERE r.record_owner_organization_id = :organization_id "
                    "AND w.record_owner_organization_id = :organization_id "
                    "AND r.state = 'ALLOCATED' AND w.state = 'IN_PROGRESS' "
                    "ORDER BY r.reservation_id LIMIT 1"
                ),
                {"organization_id": organization_id},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma reserva ALLOCATED vinculada a WorkOrder IN_PROGRESS foi encontrada. "
            "Prepare a WorkOrder e execute allocate_stock_reservation.py primeiro."
        )
    return str(row[0]), str(row[1]), Decimal(row[2]), int(row[3])


def _exigir_permissao(cliente: Cliente, reservation_id: str) -> None:
    probe = cliente.post(
        f"/v1/asset/stock-reservations/{reservation_id}/consume",
        {},
        headers={"Idempotency-Key": f"asset-consume-stock-sonda-{uuid4()}"},
    )
    if probe.status == 403 and isinstance(probe.corpo, dict):
        if probe.corpo.get("reason_code") == "PERMISSAO_AUSENTE":
            raise SystemExit(
                f"{AMARELO}O usuário não possui ASSET_INVENTORY.CONSUME.{FIM} "
                "Semeie novamente e reinicie a API com a operadora nova."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — consumir estoque reservado.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir a reserva consumível.")
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
    reservation_id, work_order_id, qty, version = _descobrir_consumo(database_url, organization)
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
    _exigir_permissao(client, reservation_id)
    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  Organization     : {organization}")
    print(f"  WorkOrder         : {work_order_id}")
    print(f"  StockReservation : {reservation_id}")
    print(f"  Quantidade        : {qty}")
    print(f"  Version           : {version}")
    print(f"{CINZA}  Todos os identificadores foram descobertos automaticamente.{FIM}")
    roteiro = Roteiro("Asset A5 — ConsumeStock", diario=diary)
    roteiro.passo(
        "1",
        "Consumir integralmente a reserva alocada",
        lambda: client.post(
            f"/v1/asset/stock-reservations/{reservation_id}/consume",
            {
                "work_order_id": work_order_id,
                "qty": str(qty),
                "expected_version": version,
            },
            headers={"Idempotency-Key": f"asset-consume-stock-{uuid4()}"},
        ),
        200,
        conferir=lambda response: (
            None
            if response["reservation"]["state"] == "CONSUMED"
            and response["reservation"]["version"] == version + 1
            else "resposta não confirmou o consumo integral da reserva"
        ),
        porque="Confirma a baixa física somente durante a execução da WorkOrder.",
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
