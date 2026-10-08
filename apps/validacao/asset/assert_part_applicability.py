"""Roteiro executável de `AssertPartApplicability`."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _descobrir_referencias(
    database_url: str, organization_id: str
) -> tuple[str, str, str, str | None, str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            part = connection.execute(
                text(
                    "SELECT p.part_id, r.revision_id FROM core_audit.parts p "
                    "JOIN core_audit.part_revisions r ON r.part_id = p.part_id "
                    "WHERE p.record_owner_organization_id = :organization_id "
                    "ORDER BY p.created_at DESC, r.position DESC LIMIT 1"
                ),
                {"organization_id": organization_id},
            ).fetchone()
            vehicle = connection.execute(
                text(
                    "SELECT model_id, variant_id FROM core_audit.vehicles "
                    "WHERE record_owner_organization_id = :organization_id "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"organization_id": organization_id},
            ).fetchone()
            evidence = connection.execute(
                text(
                    "SELECT evidence_id FROM core_audit.evidences "
                    "WHERE record_owner_organization_id = :organization_id "
                    "ORDER BY registered_at DESC LIMIT 1"
                ),
                {"organization_id": organization_id},
            ).fetchone()
    finally:
        engine.dispose()
    if part is None or vehicle is None or evidence is None:
        raise SystemExit(
            "A validação exige Part com revisão, Vehicle e Evidence da mesma Organization. "
            "Execute a semeadura e os roteiros de cadastro anteriores."
        )
    return (
        str(part[0]),
        str(part[1]),
        str(vehicle[0]),
        (None if vehicle[1] is None else str(vehicle[1])),
        str(evidence[0]),
    )


def _exigir_permissao(cliente: Cliente) -> None:
    probe = cliente.post(
        "/v1/asset/part-applicability/assertions",
        {},
        headers={"Idempotency-Key": f"asset-applicability-sonda-{uuid4()}"},
    )
    if probe.status == 403 and isinstance(probe.corpo, dict):
        if probe.corpo.get("reason_code") == "PERMISSAO_AUSENTE":
            raise SystemExit(
                f"{AMARELO}O usuário não possui ASSET_APPLICABILITY.ASSERT.{FIM} "
                "Semeie novamente e reinicie a API com a operadora nova."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — aplicabilidade.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir as referências.")
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
    part_id, revision_id, model_id, variant_id, evidence_id = _descobrir_referencias(
        database_url, organization
    )
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
    _exigir_permissao(client)
    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  Organization : {organization}")
    print(f"  Part/revisão : {part_id} / {revision_id}")
    print(f"  Modelo       : {model_id}")
    print(f"  Evidência    : {evidence_id}")
    print(f"{CINZA}  Todas as referências foram descobertas automaticamente.{FIM}")
    body: dict[str, object] = {
        "part_id": part_id,
        "part_revision_id": revision_id,
        "model_id": model_id,
        "valid_from": datetime.now(UTC).isoformat(),
        "evidence_id": evidence_id,
    }
    if variant_id is not None:
        body["variant_id"] = variant_id
    roteiro = Roteiro("Asset A5 — AssertPartApplicability", diario=diary)
    roteiro.passo(
        "1",
        "Afirmar aplicabilidade sustentada por Evidence",
        lambda: client.post(
            "/v1/asset/part-applicability/assertions",
            body,
            headers={"Idempotency-Key": f"asset-applicability-{uuid4()}"},
        ),
        201,
        conferir=lambda response: (
            None
            if response["part_ref"] == part_id
            and response["part_revision_ref"] == revision_id
            and response["evidence_ref"] == evidence_id
            and response["state"] == "ASSERTED"
            else "resposta não preservou Part, revisão, Evidence e estado"
        ),
        porque="Confirma I-APP-1: não existe aplicabilidade sem evidência explícita.",
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
