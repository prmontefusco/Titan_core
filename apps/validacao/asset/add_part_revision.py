"""Roteiro executável de `POST /v1/asset/parts/{part_id}/revisions`."""

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


def _descobrir_part(database_url: str, organization_id: str) -> tuple[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT part_id, version FROM core_audit.parts "
                    "WHERE record_owner_organization_id = :organization_id "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"organization_id": organization_id},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma Part encontrada para esta Organization. "
            "Execute primeiro o roteiro register_part."
        )
    return str(row[0]), int(row[1])


def _exigir_permissao(cliente: Cliente, part_id: str) -> None:
    probe = cliente.post(
        f"/v1/asset/parts/{part_id}/revisions",
        {"expected_version": 0, "revision_code": ""},
        headers={"Idempotency-Key": f"asset-part-revision-sonda-{uuid4()}"},
    )
    if probe.status != 403:
        return
    reason = probe.corpo.get("reason_code") if isinstance(probe.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário não possui ASSET_PART.ADD_REVISION.{FIM} "
            "Semeie novamente e reinicie a API com a operadora nova."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — AddPartRevision.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Organization e Part.")
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
    part_id, version = _descobrir_part(database_url, organization)
    revision_code = f"VAL-{uuid4().hex[:10].upper()}"
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
    _exigir_permissao(client, part_id)
    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  Organization : {organization}")
    print(f"  Part         : {part_id} (versão {version})")
    print(f"  Revisão      : {revision_code}")
    print(f"{CINZA}  Organization, Part, versão e código foram resolvidos automaticamente.{FIM}")
    roteiro = Roteiro("Asset A5 — AddPartRevision", diario=diary)
    roteiro.passo(
        "1",
        "Adicionar revisão de engenharia fictícia à Part",
        lambda: client.post(
            f"/v1/asset/parts/{part_id}/revisions",
            {
                "expected_version": version,
                "revision_code": revision_code,
                "materials": ["Material fictício para validação"],
            },
            headers={"Idempotency-Key": f"asset-part-revision-{uuid4()}"},
        ),
        200,
        conferir=lambda response: (
            None
            if response["version"] == version + 1
            and any(
                revision["revision_code"] == revision_code
                and revision["lifecycle_state"] == "ACTIVE"
                for revision in response["revisions"]
            )
            else "resposta não preservou revisão e versão esperadas"
        ),
        porque=(
            "Confirma que uma revisão de engenharia é anexada ao histórico da Part "
            "sem copiar identificadores manualmente."
        ),
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
