"""Roteiro executável para superseder uma revisão de Part."""

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


def _descobrir_revisoes(database_url: str, organization_id: str) -> tuple[str, int, str, str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT p.part_id, p.version, r1.revision_id, r2.revision_id "
                    "FROM core_audit.parts p "
                    "JOIN core_audit.part_revisions r1 ON r1.part_id = p.part_id "
                    "JOIN core_audit.part_revisions r2 ON r2.part_id = p.part_id "
                    "AND r2.revision_id <> r1.revision_id "
                    "LEFT JOIN core_audit.part_supersessions s ON s.part_id = p.part_id "
                    "AND s.predecessor_revision_id = r1.revision_id "
                    "WHERE p.record_owner_organization_id = :organization_id "
                    "AND r1.lifecycle_state = 'ACTIVE' AND r2.lifecycle_state = 'ACTIVE' "
                    "AND s.part_id IS NULL ORDER BY p.created_at DESC LIMIT 1"
                ),
                {"organization_id": organization_id},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma Part com duas revisões ACTIVE disponível. "
            "Execute duas vezes o roteiro add_part_revision para a mesma Part."
        )
    return str(row[0]), int(row[1]), str(row[2]), str(row[3])


def _exigir_permissao(cliente: Cliente, part_id: str) -> None:
    probe = cliente.post(
        f"/v1/asset/parts/{part_id}/revisions/supersede",
        {
            "expected_version": 0,
            "predecessor_revision_id": str(uuid4()),
            "successor_revision_id": str(uuid4()),
            "reason": "sonda",
        },
        headers={"Idempotency-Key": f"asset-part-supersede-sonda-{uuid4()}"},
    )
    if probe.status == 403 and isinstance(probe.corpo, dict):
        if probe.corpo.get("reason_code") == "PERMISSAO_AUSENTE":
            raise SystemExit(
                f"{AMARELO}O usuário não possui ASSET_PART.SUPERSEDE.{FIM} "
                "Semeie novamente e reinicie a API com a operadora nova."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — SupersedePartRevision.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Part e revisões.")
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
    part_id, version, predecessor_id, successor_id = _descobrir_revisoes(database_url, organization)
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
    print(f"  Predecessora : {predecessor_id}")
    print(f"  Sucessora    : {successor_id}")
    print(f"{CINZA}  Todos os identificadores e a versão foram descobertos automaticamente.{FIM}")
    roteiro = Roteiro("Asset A5 — SupersedePartRevision", diario=diary)
    roteiro.passo(
        "1",
        "Superseder revisão predecessora por revisão sucessora",
        lambda: client.post(
            f"/v1/asset/parts/{part_id}/revisions/supersede",
            {
                "expected_version": version,
                "predecessor_revision_id": predecessor_id,
                "successor_revision_id": successor_id,
                "reason": "Supersessão fictícia para validação manual.",
            },
            headers={"Idempotency-Key": f"asset-part-supersede-{uuid4()}"},
        ),
        200,
        conferir=lambda response: (
            None
            if response["version"] == version + 1
            and any(
                revision["revision_id"] == predecessor_id
                and revision["lifecycle_state"] == "SUPERSEDED"
                for revision in response["revisions"]
            )
            else "resposta não marcou a revisão predecessora como SUPERSEDED"
        ),
        porque="Confirma I-PRT-1 sem reescrever instalações históricas da revisão.",
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
