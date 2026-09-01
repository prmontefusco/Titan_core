"""Testes realistas para BuyerPolicy Fase 2 - compartilhamento entre Organizacoes.

Implementa fluxos completos com Policies de tipo CONTRACT, usando dois clientes:
- operador_org_a: Comprador (owner)
- cliente: Fornecedor (beneficiary)
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
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

_CONDICAO_FORA_DE_CARENCIA = {
    "fact_type": "livestock.withdrawal",
    "payload_key": "in_withdrawal",
    "operator": "equals",
    "expected_value": False,
    "description": "Nao pode estar em carencia no momento da avaliacao.",
}


def _headers(org_id_value: str) -> dict[str, str]:
    return {ORGANIZATION_HEADER: org_id_value}


def _animal(ambiente: Ambiente, cliente: ClienteAutenticado, organizacao: Any) -> str:
    property_id = ambiente.property_id
    if organizacao.organization_id != ambiente.org_a.organization_id:
        property_id = TypedId.new("rural_property")
        ambiente.connection.execute(
            text("SELECT set_config('titan.organization_id', :organization_id, true)"),
            {"organization_id": str(organizacao.organization_id.value)},
        )
        ambiente.connection.execute(
            text(
                "INSERT INTO core_audit.rural_properties ("
                "property_id, record_owner_organization_id, code, name, "
                "municipality, state_code, created_at) "
                "VALUES (:id, :org, :code, 'Fazenda do fornecedor', 'Uberaba', 'MG', NOW())"
            ),
            {
                "id": property_id.value,
                "org": organizacao.organization_id.value,
                "code": f"FAZ-B-{uuid4().hex[:8]}",
            },
        )
    resposta = cliente.post(
        "/v1/livestock/animals",
        json={"birth_property_id": str(property_id.value), "sex": "FEMALE"},
        headers=_headers(str(organizacao.organization_id.value)),
    )
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["animal_id"])


def _contract_policy_real(
    cliente: ClienteAutenticado,
    ambiente: Ambiente,
    conditions: list[dict[str, object]] | None = None,
) -> str:
    """Cria Policy homogeneamente CONTRACT."""
    headers = _headers(str(ambiente.org_a.organization_id.value))

    response = cliente.post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={
            "code": f"policy-contract-{uuid4().hex[:8]}",
            "name": "Criterio contratual do comprador",
            "description": "Policy bilateral para compartilhamento com fornecedor",
        },
    )
    assert response.status_code == 201, f"Failed to create policy: {response.text}"
    policy_id = str(response.json()["policy_id"])

    response = cliente.post(
        "/v1/rule-governance/rule-identities",
        headers=headers,
        json={
            "code": f"rule-contract-{uuid4().hex[:8]}",
            "purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "scope": "livestock.animal",
            "source_type": "contrato",
            "vertical": "livestock",
            "description": "Criterio contratual a ser avaliado pelo fornecedor",
        },
    )
    assert response.status_code == 201, f"Failed to create identity: {response.text}"
    identity = response.json()

    if conditions is None:
        conditions = [_CONDICAO_FORA_DE_CARENCIA]

    response = cliente.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/versions",
        headers=headers,
        json={
            "policy_id": policy_id,
            "name": "Avaliacao contratual",
            "conditions": conditions,
            "justification": "Criterio bilateral acordado em contrato",
        },
    )
    assert response.status_code == 201, f"Failed to create rule version: {response.text}"

    response = cliente.post(
        f"/v1/rule-governance/policies/{policy_id}/publish",
        headers=headers,
        json={},
    )
    assert response.status_code == 200, f"Failed to publish policy: {response.text}"
    return policy_id


@pytest.fixture
def cliente(ambiente: Ambiente) -> ClienteAutenticado:
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


def test_compartilhamento_fluxo_completo(
    ambiente: Ambiente,
    cliente: ClienteAutenticado,
    fornecedor: ClienteAutenticado,
) -> None:
    """Fluxo completo: Comprador compartilha, Fornecedor le/avalia, Comprador revoga."""

    # 1. Comprador cria Policy contratual
    policy_id = _contract_policy_real(cliente, ambiente)

    # 2. Comprador compartilha Policy com Fornecedor
    response = cliente.post(
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
    assert response.json()["status"] == "ATIVO"

    # 3. Fornecedor le a Policy compartilhada
    response = fornecedor.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 200, response.text
    shared_policy = response.json()
    assert shared_policy["policy_id"] == policy_id

    # 4. Fornecedor cria Animal para autoavaliar
    animal_id = _animal(ambiente, fornecedor, ambiente.org_b)

    # 5. Fornecedor avalia seu Animal contra Policy compartilhada
    response = fornecedor.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/evaluate",
        json={
            "subject_type": "animal",
            "subject_id": animal_id,
            "purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 201, response.text
    evaluation = response.json()
    assert evaluation["policy_id"] == policy_id

    # 6. Comprador revoga compartilhamento
    response = cliente.post(
        f"/v1/rule-governance/policies/{policy_id}/shares/{grant_id}/revoke",
        json={"revocation_reason": "Relacionamento encerrado"},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REVOGADO"

    # 7. Fornecedor nao consegue mais ler a Policy
    response = fornecedor.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code in (403, 404)
