"""Roteiro executável de `WithdrawPartApplicability`."""

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


def _descobrir_applicability(database_url: str, organization_id: str) -> tuple[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT applicability_id, version FROM core_audit.applicability "
                    "WHERE record_owner_organization_id = :organization_id "
                    "AND state = 'ASSERTED' ORDER BY asserted_at DESC LIMIT 1"
                ),
                {"organization_id": organization_id},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma Applicability ASSERTED encontrada. Execute primeiro assert_part_applicability."
        )
    return str(row[0]), int(row[1])


def _exigir_permissao(cliente: Cliente, applicability_id: str) -> None:
    probe = cliente.post(
        f"/v1/asset/part-applicability/{applicability_id}/withdraw",
        {"expected_version": 0, "reason": "sonda"},
        headers={"Idempotency-Key": f"asset-applicability-withdraw-sonda-{uuid4()}"},
    )
    if probe.status == 403 and isinstance(probe.corpo, dict):
        if probe.corpo.get("reason_code") == "PERMISSAO_AUSENTE":
            raise SystemExit(
                f"{AMARELO}O usuário não possui ASSET_APPLICABILITY.WITHDRAW.{FIM} "
                "Semeie novamente e reinicie a API com a operadora nova."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — retirar aplicabilidade.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir a Applicability.")
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
    applicability_id, version = _descobrir_applicability(database_url, organization)
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
    _exigir_permissao(client, applicability_id)
    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  Organization  : {organization}")
    print(f"  Applicability : {applicability_id} (versão {version})")
    print(f"{CINZA}  Organization, Applicability e versão foram descobertas automaticamente.{FIM}")
    roteiro = Roteiro("Asset A5 — WithdrawPartApplicability", diario=diary)
    roteiro.passo(
        "1",
        "Retirar asserção por correção aditiva",
        lambda: client.post(
            f"/v1/asset/part-applicability/{applicability_id}/withdraw",
            {
                "expected_version": version,
                "reason": "Retirada fictícia para validação manual do fluxo corretivo.",
            },
            headers={"Idempotency-Key": f"asset-applicability-withdraw-{uuid4()}"},
        ),
        200,
        conferir=lambda response: (
            None
            if response["applicability_id"] == applicability_id
            and response["state"] == "WITHDRAWN"
            and response["version"] == version + 1
            else "resposta não preservou identificador, estado e versão esperados"
        ),
        porque=(
            "Confirma I-APP-2: a retirada muda o estado sem apagar a asserção original "
            "e seu evento permanece ligado por causalidade."
        ),
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
