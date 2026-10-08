"""Roteiro executável de `POST /v1/asset/parts`."""

from __future__ import annotations

import argparse
import os
import sys
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — RegisterPart.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir a Organization.")
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
    probe = client.post(
        "/v1/asset/parts",
        {"part_number": "", "description": "sonda", "manufacturer": "sonda"},
        headers={"Idempotency-Key": f"asset-part-sonda-{uuid4()}"},
    )
    if probe.status == 403 and isinstance(probe.corpo, dict):
        if probe.corpo.get("reason_code") == "PERMISSAO_AUSENTE":
            raise SystemExit(
                f"{AMARELO}O usuário não possui ASSET_PART.REGISTER.{FIM} "
                "Semeie novamente e reinicie a API com a operadora nova."
            )
    part_number = f"PN-VALIDACAO-{uuid4().hex[:12].upper()}"
    print(
        f"{NEGRITO}Ambiente{FIM}\n  Organization : {organization}\n  Part number  : {part_number}"
    )
    print(f"{CINZA}  Organization e número único foram resolvidos automaticamente.{FIM}")
    roteiro = Roteiro("Asset A5 — RegisterPart", diario=diary)
    roteiro.passo(
        "1",
        "Cadastrar peça fictícia com número tenant-scoped",
        lambda: client.post(
            "/v1/asset/parts",
            {
                "part_number": part_number,
                "description": "Peça fictícia do roteiro Asset A5",
                "manufacturer": "Titan Test",
                "external_classifications": ["TEST_ONLY"],
            },
            headers={"Idempotency-Key": f"asset-part-{uuid4()}"},
        ),
        201,
        conferir=lambda r: (
            None
            if r["part_number"] == part_number and r["version"] == 1
            else "resposta não preservou número e versão esperados"
        ),
        porque="Confirma cadastro auditável sem reutilizar identificadores manualmente.",
    )
    result = roteiro.executar(pausar=args.pausar)
    if result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento é humano.{FIM}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
