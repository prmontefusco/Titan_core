"""Roteiro executável para cadastrar CustomerSite.

python -m uv run --locked python -m apps.validacao.asset.register_customer_site
python -m uv run --locked python -m apps.validacao.asset.register_customer_site --pausar
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


def _descobrir_customer_ref(database_url: str, organizacao: str) -> str:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            value = connection.execute(
                text(
                    "SELECT customer_id FROM core_audit.customer_sites "
                    "WHERE record_owner_organization_id = :organization_id "
                    "ORDER BY site_id LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).scalar_one_or_none()
    finally:
        engine.dispose()
    if value is None:
        raise SystemExit(
            "Nenhum customer_ref de CustomerSite existente foi encontrado. "
            "Rode a semeadura/fixture Asset antes desta validação."
        )
    return str(value)


def _exigir_permissao(cliente: Cliente) -> None:
    sonda = cliente.post(
        "/v1/asset/customer-sites",
        {
            "customer_id": "nao-e-uuid",
            "code": "SONDA",
            "display_name": "Sonda",
            "kind": "OM",
            "contacts": [],
        },
        headers={"Idempotency-Key": f"asset-site-sonda-{uuid4()}"},
    )
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui ASSET_SITE.REGISTER.{FIM}\n"
            "Semeie novamente as permissões e reinicie a API com a operadora nova."
        )


def _montar_roteiro(cliente: Cliente, customer_ref: str, code: str) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Register CustomerSite", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Cadastrar uma oficina fictícia para cliente conhecido",
        lambda: cliente.post(
            "/v1/asset/customer-sites",
            {
                "customer_id": customer_ref,
                "code": code,
                "display_name": "Oficina fictícia do roteiro Asset A5",
                "kind": "OM",
                "contacts": [
                    {
                        "name": "Contato fictício",
                        "role": "Planejamento",
                        "email": "asset-validacao@example.test",
                    }
                ],
            },
            headers={"Idempotency-Key": f"asset-site-{uuid4()}"},
        ),
        201,
        conferir=lambda r: (
            None
            if r["customer_ref"] == customer_ref
            and r["code"] == code
            and r["kind"] == "OM"
            and r["version"] == 1
            else "resposta não preservou cliente, código, tipo e versão esperados"
        ),
        porque=(
            "Confirma o cadastro tenant-scoped de uma oficina com código único e contato "
            "fictício, sem reutilizar identificadores manualmente."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — CustomerSite.")
    parser.add_argument("--pausar", action="store_true")
    parser.add_argument("--organizacao", default="")
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Organization e cliente.")

    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    subject = admin.garantir_usuario(username="titan_operador", senha=SENHA_DEMONSTRACAO)
    organizacao = args.organizacao or _descobrir_organizacao(
        database_url,
        issuer=f"{keycloak_url}/realms/{realm}",
        subject=subject,
    )
    customer_ref = _descobrir_customer_ref(database_url, organizacao)
    code = f"OM-VALIDACAO-{uuid4().hex[:10].upper()}"

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
    print(f"  Customer     : {customer_ref}")
    print(f"  Novo code    : {code}")
    print(f"{CINZA}  Organization, cliente e código foram resolvidos automaticamente.{FIM}")

    _exigir_permissao(operador)
    code_result = _montar_roteiro(operador, customer_ref, code).executar(pausar=args.pausar)
    if code_result == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code_result


if __name__ == "__main__":
    raise SystemExit(main())
