"""Roteiro executável para validar `POST /v1/asset/work-orders/{id}/removed-components`.

python -m uv run --locked python -m apps.validacao.asset.record_removed_component
python -m uv run --locked python -m apps.validacao.asset.record_removed_component --pausar

O roteiro não pede identificadores manualmente: descobre a Organization do
usuário de validação, uma WorkOrder em execução, uma Part e a versão atual da
WorkOrder.
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


def _descobrir_work_order_em_execucao(database_url: str, organizacao: str) -> tuple[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT work_order_id, version "
                    "FROM core_audit.work_orders "
                    "WHERE record_owner_organization_id = :organization_id "
                    "AND state = 'IN_PROGRESS' "
                    "ORDER BY created_at ASC, work_order_id ASC LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma WorkOrder em execução foi encontrada para esta Organization. "
            "Avance uma WorkOrder até IN_PROGRESS antes de validar RecordRemovedComponent."
        )
    return str(row[0]), int(row[1])


def _descobrir_part(database_url: str, organizacao: str) -> str:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT part_id FROM core_audit.parts "
                    "WHERE record_owner_organization_id = :organization_id "
                    "ORDER BY created_at ASC, part_id ASC LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma Part encontrada para esta Organization. "
            "Cadastre/semeie uma Part antes de validar RecordRemovedComponent."
        )
    return str(row[0])


def _corpo_record_removed_component(version: int, part_id: str, serial: str) -> dict[str, object]:
    return {
        "expected_version": version,
        "part_id": part_id,
        "disposition": "Validação manual: componente removido fictício.",
        "serial": serial,
    }


def _exigir_permissao_record_removed_component(cliente: Cliente) -> None:
    sonda = cliente.post(
        "/v1/asset/work-orders/nao-e-uuid/removed-components",
        _corpo_record_removed_component(
            1,
            "00000000-0000-0000-0000-000000000701",
            "REM-SONDA",
        ),
        headers={"Idempotency-Key": f"asset-record-removed-component-sonda-{uuid4()}"},
    )
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui "
            f"SUSTAINMENT_WO.RECORD_REMOVAL.{FIM}\n"
            "Papéis guardam as permissões existentes quando foram criados. "
            "Semeie novamente com as permissões Asset e reinicie a API."
        )


def _montar_roteiro(
    cliente: Cliente,
    work_order_id: str,
    version: int,
    part_id: str,
    serial: str,
) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Record Removed Component", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Registrar componente removido em uma WorkOrder em execução",
        lambda: cliente.post(
            f"/v1/asset/work-orders/{work_order_id}/removed-components",
            _corpo_record_removed_component(version, part_id, serial),
            headers={"Idempotency-Key": f"asset-record-removed-component-{uuid4()}"},
        ),
        200,
        conferir=lambda r: (
            None
            if r["work_order_id"] == work_order_id
            and r["state"] == "IN_PROGRESS"
            and r["version"] == version + 1
            and any(
                component["part_ref"] == part_id
                and component["disposition"] == "Validação manual: componente removido fictício."
                and component["serial"] == serial
                for component in r["removed_components"]
            )
            else (
                "resposta não preservou work_order_id, estado em execução, "
                "versão incrementada ou componente removido criado"
            )
        ),
        porque=(
            "Confirma que o comando usa concorrência otimista por expected_version, "
            "registra a disposição do componente removido e retorna o detalhe atualizado "
            "da WorkOrder."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — Record Removed Component.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Organization, WorkOrder e Part.")

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
    work_order_id, version = _descobrir_work_order_em_execucao(database_url, organizacao)
    part_id = _descobrir_part(database_url, organizacao)
    serial = f"REM-{uuid4().hex[:12].upper()}"

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
    print(f"  WorkOrder    : {work_order_id}")
    print(f"  Version      : {version}")
    print(f"  Part         : {part_id}")
    print(f"  Serial       : {serial}")
    print(
        f"{CINZA}  Organization, WorkOrder, versão e Part foram descobertas; "
        f"nada foi copiado à mão.{FIM}"
    )

    _exigir_permissao_record_removed_component(operador)
    code = _montar_roteiro(operador, work_order_id, version, part_id, serial).executar(
        pausar=args.pausar
    )
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
