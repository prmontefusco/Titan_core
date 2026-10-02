"""Roteiro executável para validar `GET /v1/asset/vehicles/{vehicle_id}`.

python -m uv run --locked python -m apps.validacao.asset.vehicle_detail
python -m uv run --locked python -m apps.validacao.asset.vehicle_detail --pausar

O roteiro não pede identificadores manualmente: descobre a Organization do
usuário de validação e o primeiro Vehicle Asset no banco local.
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _descobrir_vehicle(database_url: str, organizacao: str) -> str:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT vehicle_id FROM core_audit.vehicles "
                    "WHERE record_owner_organization_id = :organization_id "
                    "ORDER BY created_at ASC, vehicle_id ASC LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhum Vehicle Asset encontrado para esta Organization. "
            "Rode a semeadura/fixture Asset antes de validar o detalhe de veículo."
        )
    return str(row[0])


def _exigir_permissao_vehicle_read(cliente: Cliente, vehicle_id: str) -> None:
    sonda = cliente.get(f"/v1/asset/vehicles/{vehicle_id}")
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui ASSET_VEHICLE.READ.{FIM}\n"
            "Papéis guardam as permissões existentes quando foram criados. "
            "Semeie novamente com as permissões Asset e reinicie a API."
        )


def _montar_roteiro(cliente: Cliente, vehicle_id: str) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Vehicle Detail", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Consultar detalhe de veículo",
        lambda: cliente.get(f"/v1/asset/vehicles/{vehicle_id}"),
        200,
        conferir=lambda r: (
            None
            if r["vehicle_id"] == vehicle_id
            and isinstance(r["identifiers"], dict)
            and isinstance(r["meter_readings"], list)
            else "resposta não preservou vehicle_id, identifiers ou meter_readings"
        ),
        porque=(
            "Confirma que a Fleet View pode abrir um veículo específico e exibir "
            "identificadores, baseline vigente, ciclo de vida e histórico de medidor."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — Vehicle Detail.")
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
    vehicle_id = _descobrir_vehicle(database_url, organizacao)

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
    print(f"{CINZA}  Organization e Vehicle foram descobertos; nada foi copiado à mão.{FIM}")

    _exigir_permissao_vehicle_read(operador, vehicle_id)
    code = _montar_roteiro(operador, vehicle_id).executar(pausar=args.pausar)
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
