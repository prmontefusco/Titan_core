"""Roteiro executável para corrigir uma leitura de medidor sem apagá-la.

python -m uv run --locked python -m apps.validacao.asset.correct_vehicle_meter_reading
python -m uv run --locked python -m apps.validacao.asset.correct_vehicle_meter_reading --pausar
"""

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


def _descobrir_leitura_sem_correcao(
    database_url: str, organizacao: str
) -> tuple[str, int, str, Decimal]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT v.vehicle_id, v.version, r.reading_id, r.value "
                    "FROM core_audit.vehicles v "
                    "JOIN core_audit.vehicle_meter_readings r ON r.vehicle_id = v.vehicle_id "
                    "LEFT JOIN core_audit.vehicle_meter_corrections c "
                    "ON c.original_reading_id = r.reading_id "
                    "WHERE v.record_owner_organization_id = :organization_id "
                    "AND c.correction_id IS NULL "
                    "ORDER BY r.recorded_at, r.reading_id LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma leitura sem correção encontrada. Execute primeiro o roteiro "
            "record_vehicle_meter_reading com massa fictícia dedicada."
        )
    return str(row[0]), int(row[1]), str(row[2]), Decimal(row[3]) + Decimal("0.1")


def _exigir_permissao(cliente: Cliente, vehicle_id: str, reading_id: str) -> None:
    sonda = cliente.post(
        f"/v1/asset/vehicles/{vehicle_id}/meter-readings/{reading_id}/corrections",
        {"expected_version": 0, "corrected_value": "0", "reason": "sonda"},
        headers={"Idempotency-Key": f"asset-vehicle-correction-sonda-{uuid4()}"},
    )
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário não possui ASSET_VEHICLE.CORRECT_METER.{FIM}\n"
            "Semeie novamente as permissões e reinicie a API com a operadora nova."
        )


def _montar_roteiro(
    cliente: Cliente,
    vehicle_id: str,
    version: int,
    reading_id: str,
    corrected_value: Decimal,
) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Correct Vehicle Meter Reading", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Registrar correção aditiva da leitura",
        lambda: cliente.post(
            f"/v1/asset/vehicles/{vehicle_id}/meter-readings/{reading_id}/corrections",
            {
                "expected_version": version,
                "corrected_value": str(corrected_value),
                "reason": "Correção fictícia para validar preservação do histórico",
            },
            headers={"Idempotency-Key": f"asset-vehicle-correction-{uuid4()}"},
        ),
        200,
        conferir=lambda r: (
            None
            if r["vehicle_id"] == vehicle_id
            and r["version"] == version + 1
            and any(item["reading_id"] == reading_id for item in r["meter_readings"])
            and any(
                item["original_reading_id"] == reading_id
                and item["corrected_value"] == str(corrected_value)
                for item in r["meter_corrections"]
            )
            else "resposta não preservou a leitura original e sua correção"
        ),
        porque=(
            "Confirma que corrigir uma leitura cria um registro adicional e mantém "
            "o valor originalmente observado no histórico."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — correção de medidor.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Vehicle e leitura.")

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
    vehicle_id, version, reading_id, corrected_value = _descobrir_leitura_sem_correcao(
        database_url, organizacao
    )

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
    print(f"  Leitura      : {reading_id}")
    print(f"  Correção     : {corrected_value}")
    print(f"{CINZA}  Todos os identificadores e valores foram descobertos automaticamente.{FIM}")

    _exigir_permissao(operador, vehicle_id, reading_id)
    code = _montar_roteiro(operador, vehicle_id, version, reading_id, corrected_value).executar(
        pausar=args.pausar
    )
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
