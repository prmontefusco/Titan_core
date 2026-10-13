"""Roteiro executável de `ReleaseStockReservation`."""

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


def _descobrir_reserva(database_url: str, organization_id: str) -> tuple[str, int, str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT reservation_id, version, stock_position_id "
                    "FROM core_audit.stock_reservations "
                    "WHERE record_owner_organization_id = :organization_id "
                    "AND state IN ('HELD', 'ALLOCATED') "
                    "ORDER BY reservation_id LIMIT 1"
                ),
                {"organization_id": organization_id},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma StockReservation HELD ou ALLOCATED foi encontrada. "
            "Execute primeiro reserve_work_order_material.py."
        )
    return str(row[0]), int(row[1]), str(row[2])


def _exigir_permissao(cliente: Cliente, reservation_id: str) -> None:
    probe = cliente.post(
        f"/v1/asset/stock-reservations/{reservation_id}/release",
        {},
        headers={"Idempotency-Key": f"asset-release-reservation-sonda-{uuid4()}"},
    )
    if probe.status == 403 and isinstance(probe.corpo, dict):
        if probe.corpo.get("reason_code") == "PERMISSAO_AUSENTE":
            raise SystemExit(
                f"{AMARELO}O usuário não possui ASSET_INVENTORY.RELEASE.{FIM} "
                "Semeie novamente e reinicie a API com a operadora nova."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — liberar reserva de estoque.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir a StockReservation.")
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
    reservation_id, version, position_id = _descobrir_reserva(database_url, organization)
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
    print(f"  StockReservation : {reservation_id}")
    print(f"  StockPosition    : {position_id}")
    print(f"  Version          : {version}")
    print(f"{CINZA}  Reserva, posição e versão foram descobertas automaticamente.{FIM}")
    roteiro = Roteiro("Asset A5 — ReleaseStockReservation", diario=diary)
    roteiro.passo(
        "1",
        "Liberar reserva ativa com motivo auditável",
        lambda: client.post(
            f"/v1/asset/stock-reservations/{reservation_id}/release",
            {
                "expected_version": version,
                "reason": "Liberação fictícia do roteiro de validação.",
            },
            headers={"Idempotency-Key": f"asset-release-reservation-{uuid4()}"},
        ),
        200,
        conferir=lambda response: (
            None
            if response["reservation"]["reservation_id"] == reservation_id
            and response["reservation"]["state"] == "RELEASED"
            and response["reservation"]["version"] == version + 1
            and response["stock_position"]["stock_position_id"] == position_id
            else "resposta não confirmou a liberação e suas versões"
        ),
        porque="Confirma que a liberação devolve disponibilidade e preserva auditoria.",
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
