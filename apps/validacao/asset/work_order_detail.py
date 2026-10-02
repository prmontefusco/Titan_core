"""Roteiro executável para validar `GET /v1/asset/work-orders/{work_order_id}`.

python -m uv run --locked python -m apps.validacao.asset.work_order_detail
python -m uv run --locked python -m apps.validacao.asset.work_order_detail --pausar

O roteiro não pede identificadores manualmente: descobre a Organization do
usuário de validação e a primeira Work Order Asset no banco local, mostra a
requisição e imprime a resposta formatada.
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


def _descobrir_work_order(database_url: str, organizacao: str) -> str:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT work_order_id FROM core_audit.work_orders "
                    "WHERE record_owner_organization_id = :organization_id "
                    "ORDER BY created_at ASC, work_order_id ASC LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma WorkOrder Asset encontrada para esta Organization. "
            "Rode a semeadura/fixture Asset antes de validar o detalhe de WO."
        )
    return str(row[0])


def _exigir_permissao_work_order_read(cliente: Cliente, work_order_id: str) -> None:
    sonda = cliente.get(f"/v1/asset/work-orders/{work_order_id}")
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui SUSTAINMENT_WO.READ.{FIM}\n"
            "Papéis guardam as permissões existentes quando foram criados. "
            "Semeie novamente com as permissões Asset e reinicie a API."
        )


def _montar_roteiro(cliente: Cliente, work_order_id: str) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Work Order Detail", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Consultar detalhe de Work Order",
        lambda: cliente.get(f"/v1/asset/work-orders/{work_order_id}"),
        200,
        conferir=lambda r: (
            None
            if r["work_order_id"] == work_order_id
            and isinstance(r["tasks"], list)
            and isinstance(r["material_demands"], list)
            and isinstance(r["contract_context"], dict)
            else "resposta não preservou work_order_id, tasks, material_demands ou contract_context"
        ),
        porque=(
            "Confirma que o dashboard pode abrir uma WO e exibir tarefas, demandas, "
            "reservas e contexto contratual congelado sem executar comando de escrita."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — Work Order Detail.")
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
    work_order_id = _descobrir_work_order(database_url, organizacao)

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
    print(f"{CINZA}  Organization e WorkOrder foram descobertas; nada foi copiado à mão.{FIM}")

    _exigir_permissao_work_order_read(operador, work_order_id)
    code = _montar_roteiro(operador, work_order_id).executar(pausar=args.pausar)
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
