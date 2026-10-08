"""Roteiro executável de `ChangeInterchangeabilityGroup`."""

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


def _descobrir_revisao(database_url: str, organization_id: str) -> str:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT revision_id FROM core_audit.part_revisions "
                    "WHERE record_owner_organization_id = :organization_id "
                    "ORDER BY revision_id LIMIT 1"
                ),
                {"organization_id": organization_id},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit("Nenhuma revisão de Part encontrada. Execute primeiro add_part_revision.")
    return str(row[0])


def _exigir_permissao(cliente: Cliente, group_id: str, revision_id: str) -> None:
    probe = cliente.post(
        f"/v1/asset/interchangeability-groups/{group_id}/members/change",
        {"expected_version": 1, "revision_id": revision_id, "change": "ADDED"},
        headers={"Idempotency-Key": f"asset-interchange-sonda-{uuid4()}"},
    )
    if probe.status == 403 and isinstance(probe.corpo, dict):
        if probe.corpo.get("reason_code") == "PERMISSAO_AUSENTE":
            raise SystemExit(
                f"{AMARELO}O usuário não possui ASSET_PART.EDIT_INTERCHANGE.{FIM} "
                "Semeie novamente e reinicie a API com a operadora nova."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — intercambiabilidade.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Organization e revisão.")
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
    revision_id = _descobrir_revisao(database_url, organization)
    group_id = str(uuid4())
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
    _exigir_permissao(client, group_id, revision_id)
    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  Organization : {organization}")
    print(f"  Grupo        : {group_id} (novo)")
    print(f"  Revisão      : {revision_id}")
    print(f"{CINZA}  Organization, grupo e revisão foram resolvidos automaticamente.{FIM}")
    roteiro = Roteiro("Asset A5 — ChangeInterchangeabilityGroup", diario=diary)
    roteiro.passo(
        "1",
        "Criar grupo implicitamente com seu primeiro membro",
        lambda: client.post(
            f"/v1/asset/interchangeability-groups/{group_id}/members/change",
            {"expected_version": 0, "revision_id": revision_id, "change": "ADDED"},
            headers={"Idempotency-Key": f"asset-interchange-{uuid4()}"},
        ),
        200,
        conferir=lambda response: (
            None
            if response["group_id"] == group_id
            and response["member_part_revisions"] == [revision_id]
            and response["version"] == 1
            else "resposta não preservou grupo, membro e versão esperados"
        ),
        porque=(
            "Confirma que a pertinência é registrada no agregado simétrico de intercambiabilidade."
        ),
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
