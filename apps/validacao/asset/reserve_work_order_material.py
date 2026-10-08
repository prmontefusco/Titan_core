"""Roteiro executável de `ReserveMaterialForWorkOrder`."""

from __future__ import annotations

import argparse
import os
import sys
from uuid import uuid4

from sqlalchemy import create_engine, text

from apps.api.asset.commands import _canonical_response_data
from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _descobrir_escopo(database_url: str, organization_id: str) -> tuple[str, int, str, str, str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT w.work_order_id, w.version, w.vehicle_id, d.part_id, "
                    "p.stock_position_id "
                    "FROM core_audit.work_orders w "
                    "JOIN core_audit.work_order_material_demands d "
                    "ON d.work_order_id = w.work_order_id "
                    "JOIN core_audit.stock_positions p "
                    "ON p.record_owner_organization_id = w.record_owner_organization_id "
                    "AND p.part_id = d.part_id AND p.purpose = 'SERVICE_SLI' "
                    "WHERE w.record_owner_organization_id = :organization_id "
                    "AND d.qty >= 1 + COALESCE((SELECT SUM(r.qty) "
                    "FROM core_audit.stock_reservations r "
                    "JOIN core_audit.stock_positions rp "
                    "ON rp.stock_position_id = r.stock_position_id "
                    "WHERE r.reservation_id = ANY(w.material_reservations) "
                    "AND rp.part_id = d.part_id "
                    "AND r.state <> 'RELEASED'), 0) "
                    "AND p.on_hand - p.quarantine - p.inspection - p.damaged >= 1 + "
                    "COALESCE((SELECT SUM(l.qty) FROM core_audit.stock_position_reservations l "
                    "WHERE l.stock_position_id = p.stock_position_id), 0) "
                    "ORDER BY w.created_at DESC LIMIT 20"
                ),
                {"organization_id": organization_id},
            ).fetchall()
            events = connection.execute(
                text(
                    "SELECT event_id, payload_canonical_bytes "
                    "FROM core_audit.domain_events "
                    "WHERE record_owner_organization_id = :organization_id "
                    "AND event_type = 'asset.sustainment.entitlement_resolved' "
                    "ORDER BY occurred_at DESC"
                ),
                {"organization_id": organization_id},
            ).fetchall()
    finally:
        engine.dispose()
    for row in rows:
        for event in events:
            data = _canonical_response_data(bytes(event[1]))
            if (
                data.get("vehicle_ref") == str(row[2])
                and data.get("subject_ref") == str(row[3])
                and data.get("outcome") in {"GRANTED", "GRANTED_WITH_EXCEPTION"}
            ):
                return str(row[0]), int(row[1]), str(row[3]), str(row[4]), str(event[0])
    raise SystemExit(
        "Nenhuma combinação reservável com demanda, estoque SERVICE_SLI e entitlement "
        "GRANTED persistido foi encontrada. Prepare esse fluxo fictício antes da validação."
    )


def _exigir_permissao(cliente: Cliente, work_order_id: str) -> None:
    probe = cliente.post(
        f"/v1/asset/work-orders/{work_order_id}/material-reservations",
        {},
        headers={"Idempotency-Key": f"asset-reserve-material-sonda-{uuid4()}"},
    )
    if probe.status == 403 and isinstance(probe.corpo, dict):
        if probe.corpo.get("reason_code") == "PERMISSAO_AUSENTE":
            raise SystemExit(
                f"{AMARELO}O usuário não possui SUSTAINMENT_WO.RESERVE_MATERIAL.{FIM} "
                "Semeie novamente e reinicie a API com a operadora nova."
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Roteiro Asset A5 — reservar material de WorkOrder."
    )
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir o fluxo reservável.")
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
    work_order_id, version, part_id, position_id, entitlement_event_id = _descobrir_escopo(
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
    _exigir_permissao(client, work_order_id)
    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  Organization     : {organization}")
    print(f"  WorkOrder         : {work_order_id}")
    print(f"  Part              : {part_id}")
    print(f"  StockPosition     : {position_id}")
    print(f"  Entitlement event : {entitlement_event_id}")
    print(f"{CINZA}  Todo o fluxo e a versão foram descobertos automaticamente.{FIM}")
    roteiro = Roteiro("Asset A5 — ReserveMaterialForWorkOrder", diario=diary)
    roteiro.passo(
        "1",
        "Reservar uma unidade demandada e coberta",
        lambda: client.post(
            f"/v1/asset/work-orders/{work_order_id}/material-reservations",
            {
                "expected_version": version,
                "stock_position_id": position_id,
                "part_id": part_id,
                "qty": "1",
                "priority": 10,
                "entitlement_event_id": entitlement_event_id,
            },
            headers={"Idempotency-Key": f"asset-reserve-material-{uuid4()}"},
        ),
        200,
        conferir=lambda response: (
            None
            if response["work_order_id"] == work_order_id
            and response["version"] == version + 1
            and response["material_reservations"]
            else "resposta não confirmou a reserva vinculada e a nova versão"
        ),
        porque="Confirma I-WO-2 e I-INV-1 usando demanda e entitlement persistidos.",
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
