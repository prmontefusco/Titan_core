"""Testes de integração para endpoints de compartilhamento de BuyerPolicy (ADR-0065)."""

from datetime import UTC, datetime, timedelta

import pytest

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from tests.livestock_api_support import DATABASE_URL, Ambiente, ClienteAutenticado, _cliente

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada.")


@pytest.fixture
def operador(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.operador)


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
    assert response.status_code == 201
    policy_id: str = str(response.json()["policy_id"])

    # Criar uma Rule contratual
    response = operador.post(
        "/v1/rule-governance/rules",
        json={
            "policy_id": policy_id,
            "rule_code": f"rule-contract-{datetime.now(UTC).timestamp()}",
            "rule_name": "Rule Contratual",
            "description": "Para teste",
            "severity": "BLOCKING",
            "required_evidence_types": [],
            "conditions": [
                {
                    "fact_type": "test.fact",
                    "payload_key": "value",
                    "operator": "EQUALS",
                    "expected_value": "test",
                }
            ],
            "corrective_action": "Fix it",
            "source_type": "CONTRACT",
            "provider_name": "test-provider",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201

    # Publicar Policy
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/publish",
        json={"published_at": datetime.now(UTC).isoformat()},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 200

    return policy_id


def test_POST_shares_criar_grant_valido(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
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
    assert response.status_code == 201
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
    assert response.status_code == 201
    policy_id = response.json()["policy_id"]

    # Criar uma Rule INTERNAL
    response = operador.post(
        "/v1/rule-governance/rules",
        json={
            "policy_id": policy_id,
            "rule_code": f"rule-internal-{datetime.now(UTC).timestamp()}",
            "rule_name": "Rule Interna",
            "description": "Para teste",
            "severity": "BLOCKING",
            "required_evidence_types": [],
            "conditions": [],
            "corrective_action": "Fix it",
            "source_type": "INTERNAL_POLICY",
            "provider_name": "test-provider",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201

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
    ambiente: Ambiente, operador: ClienteAutenticado
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
    assert response.status_code == 201

    # Ler como beneficiário - ainda usando o mesmo operador mas em contexto de org_b
    response = operador.get(
        f"/v1/rule-governance/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["policy_id"] == policy_id
    assert data["origin"] == "CONTRACT"


def test_GET_shared_policies_retorna_404_sem_grant(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    from uuid import uuid4

    fake_policy_id = str(uuid4())

    response = operador.get(
        f"/v1/rule-governance/shared-policies/{fake_policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 404


def test_GET_shared_policies_retorna_403_com_grant_expirado(
    ambiente: Ambiente, operador: ClienteAutenticado
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
    assert response.status_code == 201

    # Tentar ler — deve falhar
    response = operador.get(
        f"/v1/rule-governance/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 403


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
    assert response.status_code == 201
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


def test_POST_shared_policies_evaluate_conform(
    ambiente: Ambiente, operador: ClienteAutenticado
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
    assert response.status_code == 201

    # Avaliar como beneficiário
    response = operador.post(
        f"/v1/rule-governance/shared-policies/{policy_id}/evaluate",
        json={
            "subject_type": "ANIMAL",
            "subject_id": "00000000-0000-0000-0000-000000000001",
            "purpose": "TEST",
            "reference_time": datetime.now(UTC).isoformat(),
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["policy_id"] == policy_id
    assert data["origin"] == "CONTRACT"


def test_terceira_organization_recebe_404_uniforme(
    ambiente: Ambiente, operador: ClienteAutenticado
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
    response = operador.get(
        f"/v1/rule-governance/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.operadora.organization_id.value)),
    )
    assert response.status_code == 404
