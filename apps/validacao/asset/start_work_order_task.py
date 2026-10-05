"""Roteiro executável para validar `POST /v1/asset/work-orders/{id}/tasks/start`.

python -m uv run --locked python -m apps.validacao.asset.start_work_order_task
python -m uv run --locked python -m apps.validacao.asset.start_work_order_task --pausar

O roteiro não pede identificadores manualmente: descobre a Organization do
usuário de validação e uma WorkOrder IN_PROGRESS com tarefa PENDING.
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


def _descobrir_work_order_task_pending(database_url: str, organizacao: str) -> tuple[str, str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT wo.work_order_id, task.task_id, wo.version "
                    "FROM core_audit.work_orders AS wo "
                    "JOIN core_audit.work_order_tasks AS task "
                    "ON task.work_order_id = wo.work_order_id "
                    "WHERE wo.record_owner_organization_id = :organization_id "
                    "AND wo.state = 'IN_PROGRESS' "
                    "AND task.state = 'PENDING' "
                    "ORDER BY wo.created_at ASC, wo.work_order_id ASC, task.task_id ASC LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma WorkOrder IN_PROGRESS com tarefa PENDING foi encontrada para esta "
            "Organization. Prepare uma WorkOrder em execução com uma tarefa ainda não iniciada "
            "antes de validar StartTask."
        )
    return str(row[0]), str(row[1]), int(row[2])


def _corpo_start_task(version: int, task_id: str) -> dict[str, object]:
    return {"expected_version": version, "task_id": task_id}


def _exigir_permissao_execute(cliente: Cliente, task_id: str) -> None:
    sonda = cliente.post(
        "/v1/asset/work-orders/nao-e-uuid/tasks/start",
        _corpo_start_task(1, task_id),
        headers={"Idempotency-Key": f"asset-start-task-sonda-{uuid4()}"},
    )
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui SUSTAINMENT_WO.EXECUTE.{FIM}\n"
            "Papéis guardam as permissões existentes quando foram criados. "
            "Semeie novamente com as permissões Asset e reinicie a API."
        )


def _montar_roteiro(cliente: Cliente, work_order_id: str, task_id: str, version: int) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Start WorkOrder Task", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Iniciar uma tarefa pendente de WorkOrder em execução",
        lambda: cliente.post(
            f"/v1/asset/work-orders/{work_order_id}/tasks/start",
            _corpo_start_task(version, task_id),
            headers={"Idempotency-Key": f"asset-start-task-{uuid4()}"},
        ),
        200,
        conferir=lambda r: (
            None
            if r["work_order_id"] == work_order_id
            and r["version"] == version + 1
            and any(
                task["task_id"] == task_id and task["state"] == "IN_PROGRESS" for task in r["tasks"]
            )
            else "resposta não preservou work_order_id, versão incrementada ou tarefa IN_PROGRESS"
        ),
        porque=(
            "Confirma que a execução granular da tarefa usa SUSTAINMENT_WO.EXECUTE, "
            "concorrência otimista por expected_version e mantém a WorkOrder em execução."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — Start WorkOrder Task.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Organization, WorkOrder e task.")

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
    work_order_id, task_id, version = _descobrir_work_order_task_pending(database_url, organizacao)

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
    print(f"  Task         : {task_id}")
    print(f"  Version      : {version}")
    print(
        f"{CINZA}  Organization, WorkOrder, task e versão foram descobertas; "
        f"nada foi copiado à mão.{FIM}"
    )

    _exigir_permissao_execute(operador, task_id)
    code = _montar_roteiro(operador, work_order_id, task_id, version).executar(pausar=args.pausar)
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
