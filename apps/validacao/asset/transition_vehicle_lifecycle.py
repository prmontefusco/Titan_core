"""Roteiro executável para transicionar o ciclo de vida de um Vehicle.

python -m uv run --locked python -m apps.validacao.asset.transition_vehicle_lifecycle
python -m uv run --locked python -m apps.validacao.asset.transition_vehicle_lifecycle --pausar
"""

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


def _descobrir_vehicle_disponivel(database_url: str, organizacao: str) -> tuple[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT vehicle_id, version FROM core_audit.vehicles "
                    "WHERE record_owner_organization_id = :organization_id "
                    "AND lifecycle_state = 'AVAILABLE' "
                    "ORDER BY vehicle_id LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhum Vehicle AVAILABLE encontrado para esta Organization. "
            "Rode a semeadura/fixture Asset antes desta validação."
        )
    return str(row[0]), int(row[1])


def _exigir_permissao(cliente: Cliente, vehicle_id: str) -> None:
    sonda = cliente.post(
        f"/v1/asset/vehicles/{vehicle_id}/transition-lifecycle",
        {"expected_version": 0, "new_state": "DEGRADED"},
        headers={"Idempotency-Key": f"asset-vehicle-transition-sonda-{uuid4()}"},
    )
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui ASSET_VEHICLE.TRANSITION.{FIM}\n"
            "Papéis guardam as permissões existentes quando foram criados. "
            "Semeie novamente e reinicie a API com a operadora nova."
        )


def _montar_roteiro(cliente: Cliente, vehicle_id: str, version: int) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Transition Vehicle Lifecycle", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Marcar Vehicle disponível como degradado",
        lambda: cliente.post(
            f"/v1/asset/vehicles/{vehicle_id}/transition-lifecycle",
            {
                "expected_version": version,
                "new_state": "DEGRADED",
                "reason": "Degradação fictícia para validação do fluxo Asset A5",
            },
            headers={"Idempotency-Key": f"asset-vehicle-transition-{uuid4()}"},
        ),
        200,
        conferir=lambda r: (
            None
            if r["vehicle_id"] == vehicle_id
            and r["lifecycle_state"] == "DEGRADED"
            and r["version"] == version + 1
            else "resposta não preservou Vehicle, estado e versão esperados"
        ),
        porque=(
            "Confirma que a API aplica a transição autorizada, auditável e protegida "
            "por versão esperada."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — ciclo de vida do Vehicle.")
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
    vehicle_id, version = _descobrir_vehicle_disponivel(database_url, organizacao)

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
    print(f"{CINZA}  Organization, Vehicle e versão foram descobertos automaticamente.{FIM}")

    _exigir_permissao(operador, vehicle_id)
    code = _montar_roteiro(operador, vehicle_id, version).executar(pausar=args.pausar)
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
