"""Roteiro executavel da governanca auditavel de regras (ADR-0043).

python -m uv run --locked python -m apps.validacao.governanca_regras
python -m uv run --locked python -m apps.validacao.governanca_regras --pausar
"""

import argparse
import os
import sys
from uuid import uuid4

from sqlalchemy import create_engine

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import (
    CLIENTE_DE_VALIDACAO,
    _ambiente,
    _descobrir_organizacao,
)
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro
from packages.core_application.policy_service import PolicyService
from packages.core_infrastructure.persistence import set_local_organization_context
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.shared_kernel import OrganizationId


def _criar_policy_de_apoio(database_url: str, organizacao: str) -> str:
    engine = create_engine(database_url)
    try:
        with engine.connect() as conexao, conexao.begin():
            organization_id = OrganizationId.parse(organizacao)
            set_local_organization_context(conexao, organization_id)
            policy = PolicyService(TransactionalPolicyRepository(conexao)).create_draft(
                organization_id=organization_id,
                code=f"validacao-regra-{uuid4().hex[:8]}",
                name="Policy de apoio para validacao de regra governada",
                description="Registro ficticio criado pelo roteiro executavel.",
            )
            return str(policy.policy_id.value)
    finally:
        engine.dispose()


def _montar_roteiro(operador: Cliente, auditor: Cliente, policy_id: str) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("ADR-0043 - Governanca auditavel de regras", diario=operador.diario)

    roteiro.passo(
        "1",
        "Operador cria identidade imutavel da regra",
        lambda: operador.post(
            "/v1/rule-governance/rule-identities",
            {
                "code": f"carencia-validacao-{uuid4().hex[:8]}",
                "purpose": "Bloquear compra enquanto houver carencia sanitaria.",
                "scope": "Animais destinados ao abate.",
                "source_type": "politica_interna",
                "vertical": "livestock",
                "description": "Regra ficticia de frigorifico para validacao.",
            },
        ),
        201,
        conferir=lambda r: None if r["rule_identity_id"] and r["code"] else "sem identidade",
        guardar=lambda r: ids.update(
            rule_identity_id=str(r["rule_identity_id"]),
            code=str(r["code"]),
        ),
        porque="A identidade da regra nasce antes da versao aplicavel e permanece estavel.",
    )
    roteiro.passo(
        "2",
        "Operador publica a primeira versao da regra",
        lambda: operador.post(
            f"/v1/rule-governance/rule-identities/{ids['rule_identity_id']}/versions",
            {
                "policy_id": policy_id,
                "name": "Carencia sanitaria minima",
                "description": "Nao aceita animal com dias de carencia restantes.",
                "severity": "blocking",
                "normative_source": "politica interna ficticia",
                "required_evidence_types": ["livestock.treatment_applied"],
                "conditions": [
                    {
                        "fact_type": "livestock.treatment",
                        "payload_key": "withdrawal_remaining_days",
                        "operator": "less_or_equal",
                        "expected_value": 0,
                        "description": "Carencia restante precisa ser zero.",
                    }
                ],
                "justification": "Protege a decisao de compra com regra versionada.",
                "corrective_action": "Aguardar o fim da carencia.",
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["code"] == ids["code"] and r["version"] == 1
            else "versao publicada nao preservou codigo e versao esperados"
        ),
        porque="A regra aplicada por decisoes futuras deve apontar para uma versao imutavel.",
    )
    roteiro.passo(
        "3",
        "Auditor consulta a linha do tempo da regra",
        lambda: auditor.get(
            f"/v1/rule-governance/rule-identities/{ids['rule_identity_id']}/timeline"
        ),
        200,
        conferir=lambda r: (
            None
            if {
                "rule_identity_created",
                "rule_version_drafted",
                "rule_version_published",
            }
            == {evento["event_type"] for evento in r.corpo}
            else "timeline nao trouxe os tres eventos esperados"
        ),
        porque="A auditoria precisa reconstruir quem criou a regra e quando ela foi publicada.",
    )
    roteiro.passo(
        "4",
        "Auditor nao publica regra",
        lambda: auditor.post(
            f"/v1/rule-governance/rule-identities/{ids['rule_identity_id']}/versions",
            {"policy_id": policy_id, "name": "Publicacao indevida"},
        ),
        403,
        conferir=lambda r: (
            None
            if r["reason_code"] == "PERMISSAO_AUSENTE"
            else "negacao nao informou ausencia de permissao"
        ),
        porque="Ler a timeline nao concede autoridade para criar versao normativa.",
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro da ADR-0043.")
    argumentos.add_argument("--pausar", action="store_true")
    argumentos.add_argument("--organizacao", default="")
    opcoes = argumentos.parse_args()

    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL para o roteiro criar a Policy de apoio.")
    organizacao = opcoes.organizacao or _descobrir_organizacao(database_url)
    policy_id = _criar_policy_de_apoio(database_url, organizacao)

    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    diario: list[Requisicao] = []

    def cliente(username: str, rotulo: str) -> Cliente:
        return Cliente(
            base_url=api,
            token=admin.token_de_usuario(
                client_id=CLIENTE_DE_VALIDACAO,
                username=username,
                senha=SENHA_DEMONSTRACAO,
            ),
            organization_id=organizacao,
            rotulo=rotulo,
            diario=diario,
        )

    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  API          : {api}")
    print(f"  Keycloak     : {keycloak_url} (realm {realm})")
    print(f"  Organization : {organizacao}")
    print(f"  Policy apoio : {policy_id}")
    print(f"{CINZA}  Rode a semeadura novamente se vier 403 por permissao ausente.{FIM}")

    codigo = _montar_roteiro(
        cliente("titan_operador", "operador"),
        cliente("titan_auditor", "auditor"),
        policy_id,
    ).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(f"{AMARELO}O script confere forma e status; a leitura de negocio segue humana.{FIM}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
