"""Testes de integração para endpoints de compartilhamento de BuyerPolicy (ADR-0065)."""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from packages.core_infrastructure.persistence import set_local_organization_context
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.livestock_application.authorization import OPERADOR_PECUARIO
from packages.shared_kernel import TypedId
from tests.livestock_api_support import (
    DATABASE_URL,
    PERMISSOES_OPERADOR,
    Ambiente,
    ClienteAutenticado,
    _cliente,
)

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada.")


@pytest.fixture
def operador(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.operador)


@pytest.fixture
def fornecedor(ambiente: Ambiente) -> ClienteAutenticado:
    principal = ambiente._principal_com_papel(
        subject=f"fornecedor-{uuid4().hex}",
        organizacao=ambiente.org_b,
        nome_papel=f"{OPERADOR_PECUARIO}_{uuid4().hex[:8]}",
        permissoes=tuple(sorted(PERMISSOES_OPERADOR)),
        agora=datetime.now(UTC),
    )
    return _cliente(ambiente, principal)


@pytest.fixture
def terceiro(ambiente: Ambiente) -> ClienteAutenticado:
    principal = ambiente._principal_com_papel(
        subject=f"terceiro-{uuid4().hex}",
        organizacao=ambiente.operadora,
        nome_papel=f"{OPERADOR_PECUARIO}_{uuid4().hex[:8]}",
        permissoes=tuple(sorted(PERMISSOES_OPERADOR)),
        agora=datetime.now(UTC),
    )
    return _cliente(ambiente, principal)


def _headers(org_id_value: str) -> dict[str, str]:
    return {ORGANIZATION_HEADER: org_id_value}


def _contract_policy(operador: ClienteAutenticado, ambiente: Ambiente) -> str:
    """Criar uma Policy contratual homogeneamente CONTRACT."""
    # Criar Policy
    response = operador.post(
        "/v1/rule-governance/policies",
        json={
            "code": f"policy-contrato-{datetime.now(UTC).timestamp()}",
            "name": "Policy Contratual",
            "description": "Para teste",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201, response.text
    policy_id: str = str(response.json()["policy_id"])

    response = operador.post(
        "/v1/rule-governance/rule-identities",
        json={
            "code": f"rule-contract-{datetime.now(UTC).timestamp()}",
            "purpose": "Validar criterio contratual.",
            "scope": "Policy compartilhada.",
            "source_type": "contrato",
            "vertical": "livestock",
            "description": "Identidade de regra contratual para teste.",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201, response.text
    rule_identity_id = response.json()["rule_identity_id"]

    # Publicar uma Rule contratual
    response = operador.post(
        f"/v1/rule-governance/rule-identities/{rule_identity_id}/versions",
        json={
            "policy_id": policy_id,
            "name": "Rule Contratual",
            "description": "Para teste",
            "severity": "blocking",
            "normative_source": "Contrato ficticio",
            "required_evidence_types": [],
            "conditions": [
                {
                    "fact_type": "test.fact",
                    "payload_key": "value",
                    "operator": "equals",
                    "expected_value": "test",
                }
            ],
            "justification": "Teste de compartilhamento contratual.",
            "corrective_action": "Fix it",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201, response.text

    # Publicar Policy
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/publish",
        json={"published_at": datetime.now(UTC).isoformat()},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 200

    return policy_id


def _share_policy(
    operador: ClienteAutenticado,
    ambiente: Ambiente,
    policy_id: str,
    *,
    beneficiary_org_id: str | None = None,
) -> str:
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": beneficiary_org_id
            or str(ambiente.org_b.organization_id.value),
            "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "field_scope_profile": "CONTRATO_MINIMO",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201, response.text
    return str(response.json()["grant_id"])


def _animal_do_fornecedor(ambiente: Ambiente, fornecedor: ClienteAutenticado) -> str:
    """Um Animal que pertence de fato a Organization beneficiaria.

    A `Ambiente` so semeia propriedade rural na org_a. A autoavaliacao
    compartilhada avalia sujeitos do proprio fornecedor (ADR-0065, D5), entao o
    cenario precisa de propriedade e animal na org_b -- semeados pela conexao
    administrativa, como a propria `Ambiente` faz.
    """
    property_id = TypedId.new("rural_property")
    set_local_organization_context(ambiente.connection, ambiente.org_b.organization_id)
    ambiente.connection.execute(
        text(
            "INSERT INTO core_audit.rural_properties ("
            "property_id, record_owner_organization_id, code, name, "
            "municipality, state_code, created_at) "
            "VALUES (:id, :org, :code, 'Fazenda do fornecedor', 'Uberaba', 'MG', NOW())"
        ),
        {
            "id": property_id.value,
            "org": ambiente.org_b.organization_id.value,
            "code": f"FAZ-B-{uuid4().hex[:8]}",
        },
    )
    resposta = fornecedor.post(
        "/v1/livestock/animals",
        json={"birth_property_id": str(property_id.value), "sex": "FEMALE"},
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["animal_id"])


def _evaluation_for_contract_policy(
    ambiente: Ambiente, fornecedor: ClienteAutenticado, policy_id: str
) -> str:
    """A Evaluation nasce pela rota compartilhada, como na producao.

    Ate a correcao da Fase 2 este auxiliar gravava a Evaluation direto no banco,
    porque a rota devolvia um identificador nulo. Passar pela rota e o que prova
    que Fase 2 e Fase 3 se conectam pela API publica.
    """
    animal_id = _animal_do_fornecedor(ambiente, fornecedor)
    resposta = fornecedor.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/evaluate",
        json={
            "subject_type": "ANIMAL",
            "subject_id": animal_id,
            "purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["evaluation_id"])


def test_POST_shares_criar_grant_valido(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    policy_id = _contract_policy(operador, ambiente)

    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": str(ambiente.org_b.organization_id.value),
            "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "field_scope_profile": "CONTRATO_MINIMO",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "ATIVO"
    assert data["owner_organization_id"] == str(ambiente.org_a.organization_id.value)
    assert data["beneficiary_organization_id"] == str(ambiente.org_b.organization_id.value)


def test_POST_shares_rejeita_policy_nao_contratual(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    # Criar Policy com Rule INTERNAL_POLICY
    response = operador.post(
        "/v1/rule-governance/policies",
        json={
            "code": f"policy-internal-{datetime.now(UTC).timestamp()}",
            "name": "Policy Interna",
            "description": "Para teste",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201, response.text
    policy_id = response.json()["policy_id"]

    response = operador.post(
        "/v1/rule-governance/rule-identities",
        json={
            "code": f"rule-internal-{datetime.now(UTC).timestamp()}",
            "purpose": "Validar criterio interno.",
            "scope": "Policy interna.",
            "source_type": "politica_interna",
            "vertical": "livestock",
            "description": "Identidade de regra interna para teste.",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201, response.text
    rule_identity_id = response.json()["rule_identity_id"]

    # Publicar uma Rule INTERNAL
    response = operador.post(
        f"/v1/rule-governance/rule-identities/{rule_identity_id}/versions",
        json={
            "policy_id": policy_id,
            "name": "Rule Interna",
            "description": "Para teste",
            "severity": "blocking",
            "normative_source": "Politica interna ficticia",
            "required_evidence_types": [],
            "conditions": [],
            "justification": "Teste de rejeicao de origem nao contratual.",
            "corrective_action": "Fix it",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201, response.text

    # Publicar Policy
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/publish",
        json={},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 200

    # Tentar compartilhar — deve falhar
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": str(ambiente.org_b.organization_id.value),
            "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "field_scope_profile": "CONTRATO_MINIMO",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 422


def test_GET_shared_policies_ler_policy_compartilhada(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)

    # Compartilhar
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": str(ambiente.org_b.organization_id.value),
            "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "field_scope_profile": "CONTRATO_MINIMO",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201, response.text

    # Ler como beneficiário - ainda usando o mesmo operador mas em contexto de org_b
    response = fornecedor.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["policy_id"] == policy_id
    assert data["origin"] == "CONTRACT"


def test_GET_shared_policies_retorna_404_sem_grant(
    ambiente: Ambiente, fornecedor: ClienteAutenticado
) -> None:
    from uuid import uuid4

    fake_policy_id = str(uuid4())

    response = fornecedor.get(
        f"/v1/rule-governance/policies/shared-policies/{fake_policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 404


def test_GET_shared_policies_retorna_403_com_grant_expirado(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)

    # Compartilhar com validade no passado
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": str(ambiente.org_b.organization_id.value),
            "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "valid_until": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "field_scope_profile": "CONTRATO_MINIMO",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201, response.text

    # Tentar ler — deve falhar
    response = fornecedor.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 404


def test_POST_shares_revoke_sucesso(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    policy_id = _contract_policy(operador, ambiente)

    # Compartilhar
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": str(ambiente.org_b.organization_id.value),
            "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "field_scope_profile": "CONTRATO_MINIMO",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201, response.text
    grant_id = response.json()["grant_id"]

    # Revogar
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares/{grant_id}/revoke",
        json={"revocation_reason": "Test revocation"},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "REVOGADO"


def test_POST_shared_policies_evaluate_produz_avaliacao_real(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    """A rota executa as Rules do comprador sobre o sujeito do fornecedor.

    Ate a correcao da Fase 2 ela devolvia `evaluation_id` nulo, `CONFORM`
    constante e hash vazio, sem executar Rule nenhuma.
    """
    policy_id = _contract_policy(operador, ambiente)
    _share_policy(operador, ambiente, policy_id)
    animal_id = _animal_do_fornecedor(ambiente, fornecedor)

    response = fornecedor.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/evaluate",
        json={
            "subject_type": "ANIMAL",
            "subject_id": animal_id,
            "purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "reference_time": datetime.now(UTC).isoformat(),
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["policy_id"] == policy_id
    assert data["origin"] == "CONTRACT"
    assert UUID(data["evaluation_id"]).int != 0, "o UUID nulo era a marca do stub"
    assert data["evaluation_hash"]
    assert data["rule_results"], "a Rule contratual publicada tem de ter sido executada"
    assert data["rule_results"][0]["rule_code"]


def test_POST_shared_policies_evaluate_avaliacao_pertence_ao_fornecedor(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    """ADR-0068: a Evaluation nasce sob a Organization que avaliou.

    E o que impede o `FactSnapshot` do fornecedor de atravessar para dentro da
    RLS do comprador, que a ADR-0065 bloqueia expressamente.
    """
    policy_id = _contract_policy(operador, ambiente)
    _share_policy(operador, ambiente, policy_id)
    evaluation_id = _evaluation_for_contract_policy(ambiente, fornecedor, policy_id)

    repositorio = TransactionalEvaluationRepository(ambiente.connection)
    identificador = TypedId.parse("evaluation", evaluation_id)

    # A conexao da fixture e administrativa e ignora RLS: sem trocar para a role
    # de runtime, o segundo trecho passaria mesmo se o isolamento nao existisse.
    role = os.environ.get("TITAN_RUNTIME_DATABASE_ROLE", "titan_app")
    ambiente.connection.execute(text(f"SET LOCAL ROLE {role}"))
    try:
        set_local_organization_context(ambiente.connection, ambiente.org_b.organization_id)
        do_fornecedor = repositorio.get_by_id(identificador)
        assert do_fornecedor is not None
        assert do_fornecedor.organization_id == ambiente.org_b.organization_id

        set_local_organization_context(ambiente.connection, ambiente.org_a.organization_id)
        assert repositorio.get_by_id(identificador) is None, (
            "o comprador nao pode alcancar a Evaluation do fornecedor (ADR-0065/0068)"
        )
    finally:
        ambiente.connection.execute(text("RESET ROLE"))


def test_POST_shared_policies_evaluate_recusa_sujeito_de_fora(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    """Sujeito inexistente nao produz conformidade.

    O stub respondia `201 CONFORM` para qualquer identificador, inclusive um que
    nao existisse em Organization alguma.
    """
    policy_id = _contract_policy(operador, ambiente)
    _share_policy(operador, ambiente, policy_id)

    response = fornecedor.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/evaluate",
        json={
            "subject_type": "ANIMAL",
            "subject_id": str(uuid4()),
            "purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )

    assert response.status_code == 404, response.text
    assert response.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"


def test_terceira_organization_recebe_404_uniforme(
    ambiente: Ambiente, operador: ClienteAutenticado, terceiro: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)

    # Compartilhar apenas com org_b
    operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": str(ambiente.org_b.organization_id.value),
            "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "field_scope_profile": "CONTRATO_MINIMO",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )

    # Terceira org (operadora) tenta acessar — deve receber 404
    response = terceiro.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.operadora.organization_id.value)),
    )
    assert response.status_code == 404


def test_POST_shared_decisions_beneficiario_cria_proposta(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)
    evaluation_id = _evaluation_for_contract_policy(ambiente, fornecedor, policy_id)

    response = fornecedor.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/decisions",
        json={
            "grant_id": grant_id,
            "evaluation_id": evaluation_id,
            "proposal_content": "Peso conferido em balanca auditada.",
            "evidence_references": ["doc-peso-001"],
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "PROPOSTA"
    assert data["policy_id"] == policy_id
    assert data["evaluation_id"] == evaluation_id
    assert data["proposer_organization_id"] == str(ambiente.org_b.organization_id.value)
    assert data["reviewer_organization_id"] == str(ambiente.org_a.organization_id.value)


def test_POST_shared_decisions_owner_nao_cria_proposta(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)
    evaluation_id = _evaluation_for_contract_policy(ambiente, fornecedor, policy_id)

    response = operador.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/decisions",
        json={
            "grant_id": grant_id,
            "evaluation_id": evaluation_id,
            "proposal_content": "Tentativa do owner.",
            "evidence_references": [],
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )

    assert response.status_code == 403


def test_POST_shared_decisions_review_owner_revisa_e_beneficiario_nao_revisa(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)
    evaluation_id = _evaluation_for_contract_policy(ambiente, fornecedor, policy_id)
    created = fornecedor.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/decisions",
        json={
            "grant_id": grant_id,
            "evaluation_id": evaluation_id,
            "proposal_content": "Solicito reavaliacao.",
            "evidence_references": ["doc-001"],
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert created.status_code == 201
    decision_id = created.json()["decision_id"]

    denied = fornecedor.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/decisions/{decision_id}/review",
        json={"review_decision": "APROVADA", "review_content": "ok"},
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert denied.status_code == 403

    reviewed = operador.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/decisions/{decision_id}/review",
        json={"review_decision": "REAVALIACAO_NECESSARIA", "review_content": "Nova pesagem."},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert reviewed.status_code == 200
    data = reviewed.json()
    assert data["status"] == "REVISADA"
    assert data["review_decision"] == "REAVALIACAO_NECESSARIA"
    assert data["reviewed_at"] is not None

    repeated = operador.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/decisions/{decision_id}/review",
        json={"review_decision": "APROVADA", "review_content": "segunda revisao"},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert repeated.status_code == 409


def test_GET_shared_decisions_lista_para_partes_e_oculta_terceiro(
    ambiente: Ambiente,
    operador: ClienteAutenticado,
    fornecedor: ClienteAutenticado,
    terceiro: ClienteAutenticado,
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)
    evaluation_id = _evaluation_for_contract_policy(ambiente, fornecedor, policy_id)
    response = fornecedor.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/decisions",
        json={
            "grant_id": grant_id,
            "evaluation_id": evaluation_id,
            "proposal_content": "Registro para listagem.",
            "evidence_references": ["doc-xyz"],
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 201, response.text

    beneficiary = fornecedor.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/decisions",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert beneficiary.status_code == 200
    assert len(beneficiary.json()) == 1

    owner = operador.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/decisions",
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert owner.status_code == 200
    assert len(owner.json()) == 1

    third = terceiro.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/decisions",
        headers=_headers(str(ambiente.operadora.organization_id.value)),
    )
    assert third.status_code == 200
    assert third.json() == []
