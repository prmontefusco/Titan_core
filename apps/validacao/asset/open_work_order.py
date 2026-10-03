"""Roteiro executável para validar `POST /v1/asset/work-orders`.

python -m uv run --locked python -m apps.validacao.asset.open_work_order
python -m uv run --locked python -m apps.validacao.asset.open_work_order --pausar

O roteiro não pede identificadores manualmente: descobre a Organization do
usuário de validação e um Vehicle com site e cobertura contratual vigente.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _instant_utc(value: datetime) -> str:
    instant = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return instant.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _descobrir_vehicle_coberto(database_url: str, organizacao: str) -> tuple[str, str, str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT v.vehicle_id, v.site_id, cv.effective_valid_from "
                    "FROM core_audit.vehicles v "
                    "JOIN core_audit.contract_version_coverage_lines cl "
                    "ON cl.record_owner_organization_id = v.record_owner_organization_id "
                    "AND ("
                    "  (cl.scope = 'VEHICLE' AND cl.scope_value = v.vehicle_id::text) "
                    "  OR (cl.scope = 'MODEL' AND cl.scope_value = v.model_id::text) "
                    "  OR ("
                    "    cl.scope = 'SITE' "
                    "    AND v.site_id IS NOT NULL "
                    "    AND cl.scope_value = v.site_id::text"
                    "  )"
                    ") "
                    "JOIN core_audit.contract_versions cv "
                    "ON cv.contract_id = cl.contract_id "
                    "AND cv.version_no = cl.version_no "
                    "WHERE v.record_owner_organization_id = :organization_id "
                    "AND v.site_id IS NOT NULL "
                    "ORDER BY cv.effective_valid_from ASC, v.vehicle_id ASC LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhum Vehicle com site e SLIContract vigente encontrado para esta Organization. "
            "Rode a semeadura/fixture Asset antes de validar OpenWorkOrder."
        )
    return str(row[0]), str(row[1]), _instant_utc(row[2])


def _corpo_open_work_order(vehicle_id: str, instant: str) -> dict[str, str]:
    return {
        "vehicle_id": vehicle_id,
        "at_instant": instant,
        "failure_mode": "Falha observada no roteiro Asset A5",
        "failure_reported_at": instant,
        "failure_affected_position": "posição de validação",
    }


def _exigir_permissao_work_order_open(cliente: Cliente) -> None:
    sonda = cliente.post(
        "/v1/asset/work-orders",
        {
            "vehicle_id": "nao-e-uuid",
            "at_instant": "2026-10-03T12:00:00Z",
            "failure_mode": "sonda de permissão",
            "failure_reported_at": "2026-10-03T12:00:00Z",
        },
        headers={"Idempotency-Key": f"asset-open-wo-sonda-{uuid4()}"},
    )
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui SUSTAINMENT_WO.OPEN.{FIM}\n"
            "Papéis guardam as permissões existentes quando foram criados. "
            "Semeie novamente com as permissões Asset e reinicie a API."
        )


def _montar_roteiro(cliente: Cliente, vehicle_id: str, site_id: str, instant: str) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Open WorkOrder", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Abrir WorkOrder para Vehicle coberto por contrato",
        lambda: cliente.post(
            "/v1/asset/work-orders",
            _corpo_open_work_order(vehicle_id, instant),
            headers={"Idempotency-Key": f"asset-open-wo-{uuid4()}"},
        ),
        201,
        conferir=lambda r: (
            None
            if r["vehicle_ref"] == vehicle_id
            and r["site_ref"] == site_id
            and r["state"] == "DRAFT"
            and r["contract_context"]["resolved_at"] == instant
            and r["failure"]["mode"] == "Falha observada no roteiro Asset A5"
            else "resposta não preservou vehicle/site/state/contract_context/failure esperados"
        ),
        porque=(
            "Confirma que o comando HTTP resolve contrato vigente, congela ContractContext "
            "e cria uma WorkOrder em DRAFT sem copiar identificadores manualmente."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — Open WorkOrder.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Organization e Vehicle.")

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
    vehicle_id, site_id, instant = _descobrir_vehicle_coberto(database_url, organizacao)

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
    print(f"  Vehicle      : {vehicle_id}")
    print(f"  Site         : {site_id}")
    print(f"  Instant      : {instant}")
    print(
        f"{CINZA}  Organization, Vehicle, Site e instant foram descobertos; "
        f"nada foi copiado à mão.{FIM}"
    )

    _exigir_permissao_work_order_open(operador)
    code = _montar_roteiro(operador, vehicle_id, site_id, instant).executar(pausar=args.pausar)
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
