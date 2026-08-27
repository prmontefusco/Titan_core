"""Roteiro executavel para BuyerPolicy Fase 3 Incremento 1.

python -m uv run --locked python -m apps.validacao.buyerpolicy_shared_decision
python -m uv run --locked python -m apps.validacao.buyerpolicy_shared_decision --pausar
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import (
    CLIENTE_DE_VALIDACAO,
    _ambiente,
    _descobrir_organizacao,
)
from apps.validacao.runner import (
    AMARELO,
    CINZA,
    FIM,
    NEGRITO,
    Cliente,
    Requisicao,
    Resposta,
    Roteiro,
)
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_infrastructure.persistence import set_local_organization_context
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.shared_kernel import OrganizationId, TypedId


def _criar_evaluation_de_apoio(database_url: str, organizacao: str, policy_id: str) -> str:
    engine = create_engine(database_url)
    try:
        with engine.connect() as conexao, conexao.begin():
            organization_id = OrganizationId.parse(organizacao)
            set_local_organization_context(conexao, organization_id)
            policy = TransactionalPolicyRepository(conexao).get_by_id(
                TypedId.parse("policy", policy_id)
            )
            if policy is None:
                raise SystemExit("Policy de apoio nao encontrada para criar Evaluation.")
            rules = TransactionalRuleRepository(conexao).list_by_policy(
                organization_id=organization_id,
                policy_id=policy.policy_id,
            )
            if not rules:
                raise SystemExit("Policy de apoio nao possui Rule publicada.")
            agora = datetime.now(UTC)
            snapshot = FactSnapshot.create(
                organization_id=organization_id,
                target_id=TypedId.new("animal"),
                as_of=agora,
                facts=[
                    Fact.create(
                        fact_type="test.fact",
                        payload={"value": "test"},
                        observed_at=agora,
                    )
                ],
            )
            evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
                policy=policy,
                rules=rules,
                snapshot=snapshot,
                purpose="AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            )
            TransactionalEvaluationRepository(conexao).save(evaluation)
            return str(evaluation.evaluation_id.value)
    finally:
        engine.dispose()


def _montar_roteiro(cliente: Cliente, database_url: str, organizacao: str) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("BuyerPolicy Fase 3 - SharedDecision", diario=cliente.diario)

    roteiro.passo(
        "0",
        "Sondar ambiente autenticado",
        lambda: cliente.get("/technical/authentication"),
        200,
        porque="Falha aqui indica API, Keycloak, token ou OrganizationContext fora do lugar.",
    )
    roteiro.passo(
        "1",
        "Criar Policy contratual de apoio",
        lambda: cliente.post(
            "/v1/rule-governance/policies",
            {
                "code": f"shared-decision-{uuid4().hex[:8]}",
                "name": "Policy contratual de validacao SharedDecision",
                "description": "Registro ficticio criado pelo roteiro executavel.",
            },
        ),
        201,
        guardar=lambda r: ids.update(policy_id=str(r["policy_id"])),
        porque="A proposta sempre nasce vinculada a uma Policy compartilhada.",
    )
    roteiro.passo(
        "2",
        "Criar identidade de Rule contratual",
        lambda: cliente.post(
            "/v1/rule-governance/rule-identities",
            {
                "code": f"shared-rule-{uuid4().hex[:8]}",
                "purpose": "Validar proposta de SharedDecision.",
                "scope": "Policy compartilhada ficticia.",
                "source_type": "contrato",
                "vertical": "livestock",
                "description": "Identidade ficticia para o roteiro executavel.",
            },
        ),
        201,
        guardar=lambda r: ids.update(rule_identity_id=str(r["rule_identity_id"])),
        porque="A origem CONTRACT fica na identidade governada da regra.",
    )
    roteiro.passo(
        "3",
        "Publicar Rule contratual minima",
        lambda: cliente.post(
            f"/v1/rule-governance/rule-identities/{ids['rule_identity_id']}/versions",
            {
                "policy_id": ids["policy_id"],
                "name": "Valor de teste deve estar presente",
                "description": "Rule ficticia para produzir Evaluation de apoio.",
                "severity": "blocking",
                "normative_source": "Contrato ficticio de validacao",
                "required_evidence_types": [],
                "conditions": [
                    {
                        "fact_type": "test.fact",
                        "payload_key": "value",
                        "operator": "equals",
                        "expected_value": "test",
                    }
                ],
                "justification": "Permite exercitar uma Evaluation deterministica.",
                "corrective_action": "Corrigir valor de teste.",
            },
        ),
        201,
        porque="O compartilhamento da Fase 2 exige Policy homogeneamente CONTRACT.",
    )
    roteiro.passo(
        "4",
        "Publicar Policy contratual",
        lambda: cliente.post(
            f"/v1/rule-governance/policies/{ids['policy_id']}/publish",
            {"published_at": datetime.now(UTC).isoformat()},
        ),
        200,
        porque="Somente Policy publicada pode ser compartilhada.",
    )
    roteiro.passo(
        "5",
        "Criar grant de apoio",
        lambda: cliente.post(
            f"/v1/rule-governance/policies/{ids['policy_id']}/shares",
            {
                "beneficiary_organization_id": organizacao,
                "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
                "valid_until": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                "field_scope_profile": "CONTRATO_MINIMO",
            },
        ),
        201,
        guardar=lambda r: ids.update(grant_id=str(r["grant_id"])),
        porque="O grant delimita finalidade, validade e Organization beneficiaria.",
    )
    roteiro.passo(
        "6",
        "Criar Evaluation de apoio sem copiar identificadores",
        lambda: _resposta_local(
            {
                "evaluation_id": _criar_evaluation_de_apoio(
                    database_url, organizacao, ids["policy_id"]
                )
            }
        ),
        200,
        guardar=lambda r: ids.update(evaluation_id=str(r["evaluation_id"])),
        porque="A Fase 3 referencia uma Evaluation imutavel; o roteiro a cria diretamente.",
    )
    roteiro.passo(
        "7",
        "Fornecedor cria proposta estruturada",
        lambda: cliente.post(
            f"/v1/rule-governance/policies/shared-policies/{ids['policy_id']}/decisions",
            {
                "grant_id": ids["grant_id"],
                "evaluation_id": ids["evaluation_id"],
                "proposal_content": "Solicito revisao com referencia ficticia controlada.",
                "evidence_references": ["validacao:documento-ficticio"],
            },
        ),
        201,
        conferir=lambda r: None if r["status"] == "PROPOSTA" else "status inesperado",
        guardar=lambda r: ids.update(decision_id=str(r["decision_id"])),
        porque="A proposta nao altera a Evaluation; apenas cria trilha de revisao.",
    )
    roteiro.passo(
        "8",
        "Comprador revisa a proposta",
        lambda: cliente.post(
            (
                f"/v1/rule-governance/policies/shared-policies/{ids['policy_id']}"
                f"/decisions/{ids['decision_id']}/review"
            ),
            {
                "review_decision": "REAVALIACAO_NECESSARIA",
                "review_content": "Referencia aceita para nova avaliacao controlada.",
            },
        ),
        200,
        conferir=lambda r: None if r["status"] == "REVISADA" else "revisao nao fechou",
        porque="A revisao registra resposta do owner sem reescrever o resultado anterior.",
    )
    roteiro.passo(
        "9",
        "Listar historico da Policy compartilhada",
        lambda: cliente.get(
            f"/v1/rule-governance/policies/shared-policies/{ids['policy_id']}/decisions"
        ),
        200,
        conferir=lambda r: None if len(r.corpo) == 1 else "historico inesperado",
        porque="As partes conseguem reconstruir proposta e revisao pelo endpoint de leitura.",
    )
    return roteiro


def _resposta_local(corpo: dict[str, str]) -> Resposta:
    return Resposta(200, corpo)


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro de SharedDecision BuyerPolicy.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para criar a Evaluation de apoio.")
    organizacao = opcoes.organizacao or _descobrir_organizacao(database_url)

    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    diario: list[Requisicao] = []
    cliente = Cliente(
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
    print(f"{CINZA}  Rode seed/bootstrap novamente se vier 403 por permissao ausente.{FIM}")

    codigo = _montar_roteiro(cliente, database_url, organizacao).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(f"{AMARELO}O script confere forma e status; a leitura de negocio segue humana.{FIM}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
