"""Roteiro executável para validar `POST /v1/asset/work-orders/{id}/cancel`.

python -m uv run --locked python -m apps.validacao.asset.cancel_work_order
python -m uv run --locked python -m apps.validacao.asset.cancel_work_order --pausar

O roteiro não pede identificadores manualmente: descobre a Organization do
usuário de validação e uma WorkOrder não terminal.
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


def _descobrir_work_order_cancelavel(database_url: str, organizacao: str) -> tuple[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT wo.work_order_id, wo.version "
                    "FROM core_audit.work_orders AS wo "
                    "WHERE wo.record_owner_organization_id = :organization_id "
                    "AND wo.state NOT IN ('COMPLETED', 'CANCELLED') "
                    "ORDER BY wo.created_at ASC, wo.work_order_id ASC LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma WorkOrder não terminal foi encontrada para esta Organization. "
            "Prepare uma WorkOrder ativa antes de validar CancelWorkOrder."
        )
    return str(row[0]), int(row[1])


def _corpo_cancel(version: int) -> dict[str, object]:
    return {
        "expected_version": version,
        "reason": "Validação manual: cancelamento fictício solicitado pelo cliente.",
    }


def _exigir_permissao_cancel(cliente: Cliente) -> None:
    sonda = cliente.post(
        "/v1/asset/work-orders/nao-e-uuid/cancel",
        _corpo_cancel(1),
        headers={"Idempotency-Key": f"asset-cancel-wo-sonda-{uuid4()}"},
    )
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui SUSTAINMENT_WO.CANCEL.{FIM}\n"
            "Papéis guardam as permissões existentes quando foram criados. "
            "Semeie novamente com as permissões Asset e reinicie a API."
        )


def _montar_roteiro(cliente: Cliente, work_order_id: str, version: int) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Cancel WorkOrder", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Cancelar uma WorkOrder não terminal com motivo obrigatório",
        lambda: cliente.post(
            f"/v1/asset/work-orders/{work_order_id}/cancel",
            _corpo_cancel(version),
            headers={"Idempotency-Key": f"asset-cancel-wo-{uuid4()}"},
        ),
        200,
        conferir=lambda r: (
            None
            if r["work_order_id"] == work_order_id
            and r["version"] == version + 1
            and r["state"] == "CANCELLED"
            else "resposta não preservou work_order_id, versão incrementada ou estado CANCELLED"
        ),
        porque=(
            "Confirma a transição T17: uma WorkOrder não terminal pode ser cancelada "
            "com motivo obrigatório e o caso de uso libera reservas vinculadas."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — Cancel WorkOrder.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Organization e WorkOrder.")

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
    work_order_id, version = _descobrir_work_order_cancelavel(database_url, organizacao)

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
    print(
        f"{CINZA}  Organization, WorkOrder e versão foram descobertas; nada foi copiado à mão.{FIM}"
    )

    _exigir_permissao_cancel(operador)
    code = _montar_roteiro(operador, work_order_id, version).executar(pausar=args.pausar)
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
