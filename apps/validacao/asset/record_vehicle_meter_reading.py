"""Roteiro executável para registrar leitura de medidor de Vehicle.

python -m uv run --locked python -m apps.validacao.asset.record_vehicle_meter_reading
python -m uv run --locked python -m apps.validacao.asset.record_vehicle_meter_reading --pausar
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _descobrir_vehicle_e_leitura(database_url: str, organizacao: str) -> tuple[str, int, Decimal]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT v.vehicle_id, v.version, "
                    "COALESCE(MAX(r.value), 0) AS last_value "
                    "FROM core_audit.vehicles v "
                    "LEFT JOIN core_audit.vehicle_meter_readings r "
                    "ON r.vehicle_id = v.vehicle_id AND r.kind = 'HOURS' "
                    "WHERE v.record_owner_organization_id = :organization_id "
                    "GROUP BY v.vehicle_id, v.version "
                    "ORDER BY v.vehicle_id LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhum Vehicle encontrado para esta Organization. "
            "Rode a semeadura/fixture Asset antes desta validação."
        )
    return str(row[0]), int(row[1]), Decimal(row[2]) + Decimal("1")


def _exigir_permissao(cliente: Cliente, vehicle_id: str) -> None:
    sonda = cliente.post(
        f"/v1/asset/vehicles/{vehicle_id}/meter-readings",
        {
            "expected_version": 0,
            "kind": "HOURS",
            "value": "0",
            "observed_at": "2026-10-08T12:00:00Z",
            "source": "sonda",
        },
        headers={"Idempotency-Key": f"asset-vehicle-meter-sonda-{uuid4()}"},
    )
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui ASSET_VEHICLE.RECORD_METER.{FIM}\n"
            "Papéis guardam as permissões existentes quando foram criados. "
            "Semeie novamente e reinicie a API com a operadora nova."
        )


def _montar_roteiro(
    cliente: Cliente,
    vehicle_id: str,
    version: int,
    next_value: Decimal,
    observed_at: str,
) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Record Vehicle Meter Reading", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Registrar nova leitura monotônica de horímetro",
        lambda: cliente.post(
            f"/v1/asset/vehicles/{vehicle_id}/meter-readings",
            {
                "expected_version": version,
                "kind": "HOURS",
                "value": str(next_value),
                "observed_at": observed_at,
                "source": "roteiro-ficticio-asset-a5",
            },
            headers={"Idempotency-Key": f"asset-vehicle-meter-{uuid4()}"},
        ),
        200,
        conferir=lambda r: (
            None
            if r["vehicle_id"] == vehicle_id
            and r["version"] == version + 1
            and any(
                reading["kind"] == "HOURS" and reading["value"] == str(next_value)
                for reading in r["meter_readings"]
            )
            else "resposta não preservou Vehicle, versão e leitura esperados"
        ),
        porque=(
            "Confirma que uma leitura crescente é anexada ao histórico do Vehicle, "
            "sem substituir leituras anteriores."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — leitura de Vehicle.")
    parser.add_argument("--pausar", action="store_true")
    parser.add_argument("--organizacao", default="")
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
    organizacao = args.organizacao or _descobrir_organizacao(
        database_url,
        issuer=f"{keycloak_url}/realms/{realm}",
        subject=subject,
    )
    vehicle_id, version, next_value = _descobrir_vehicle_e_leitura(database_url, organizacao)
    observed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

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
    print(f"  Vehicle      : {vehicle_id} (versão {version})")
    print(f"  Nova leitura : {next_value} HOURS")
    print(f"{CINZA}  Identificadores, versão e leitura foram calculados automaticamente.{FIM}")

    _exigir_permissao(operador, vehicle_id)
    code = _montar_roteiro(operador, vehicle_id, version, next_value, observed_at).executar(
        pausar=args.pausar
    )
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
