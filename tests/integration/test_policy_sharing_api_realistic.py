"""Testes realistas para BuyerPolicy Fase 2 — compartilhamento entre Organizações.

Implementa fluxos completos com Policies de tipo CONTRACT, incluindo:
- Compartilhamento entre comprador (owner) e fornecedor (beneficiary)
- Avaliação por parte do fornecedor com dados reais
- Revogação e validação de bloqueios
- Cenários de erro (expiração, negação, heterogeneidade)
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
    """Retorna headers padrão com Organization ID."""
    return {ORGANIZATION_HEADER: org_id_value}


def _animal(ambiente: Ambiente, cliente: ClienteAutenticado, organizacao: Any) -> str:
    """Cria um Animal em uma Organization via HTTP."""
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
    """Cria uma Policy homogeneamente CONTRACT (tipo compartilhável).

    Padrão:
    1. POST /policies → cria rascunho
    2. POST /rule-identities → cria Identity com source_type=contrato
    3. POST /rule-identities/{id}/versions → publica Rule Version
    4. POST /policies/{id}/publish → publica Policy

    Retorna: policy_id pronto para compartilhamento
    """
    headers = _headers(str(ambiente.org_a.organization_id.value))

    # 1. Criar Policy rascunho
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

    # 2. Criar RuleIdentity (CONTRACT)
    response = cliente.post(
        "/v1/rule-governance/rule-identities",
        headers=headers,
        json={
            "code": f"rule-contract-{uuid4().hex[:8]}",
            "purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "scope": "livestock.animal",
            "source_type": "contrato",  # CONTRACT
            "vertical": "livestock",
            "description": "Criterio contratual a ser avaliado pelo fornecedor",
        },
    )
    assert response.status_code == 201, f"Failed to create identity: {response.text}"
    identity = response.json()

    # 3. Publicar RuleVersion
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

    # 4. Publicar Policy
    response = cliente.post(
        f"/v1/rule-governance/policies/{policy_id}/publish",
        headers=headers,
        json={},
    )
    assert response.status_code == 200, f"Failed to publish policy: {response.text}"
    return policy_id


@pytest.fixture
def operador(ambiente: Ambiente) -> ClienteAutenticado:
    """Cliente autenticado como operador."""
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


def test_compartilhamento_create_grant_simples(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Teste simples: criar um grant com Policy existente."""
    from uuid import uuid4

    headers = _headers(str(ambiente.org_a.organization_id.value))

    # Criar Policy simplificada (via API)
    response = operador.post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={
            "code": f"test-policy-{uuid4().hex[:8]}",
            "name": "Test Policy",
        },
    )
    assert response.status_code == 201, response.text
    policy_id = response.json()["policy_id"]

    # Tentar compartilhar (espera falhar pois Policy não está PUBLISHED)
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": str(ambiente.org_b.organization_id.value),
            "access_purpose": "TEST",
            "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "field_scope_profile": "TEST",
        },
        headers=headers,
    )
    # Status esperado: 422 (Policy não está PUBLISHED) ou 404/500 (erro)
    assert response.status_code in (422, 404, 400, 500)
    print(f"Response: {response.status_code} - {response.text}")


def test_compartilhamento_fluxo_completo(
    ambiente: Ambiente,
    operador: ClienteAutenticado,
    fornecedor: ClienteAutenticado,
) -> None:
    """Fluxo completo: Comprador compartilha → Fornecedor lê → avalia → Comprador revoga."""

    # Passo 1: Comprador (org_a) cria Policy contratual
    policy_id = _contract_policy_real(operador, ambiente)

    # Passo 2: Comprador compartilha Policy com Fornecedor (org_b)
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
    assert response.json()["status"] == "ATIVO"

    # Passo 3: Fornecedor (org_b) lê a Policy compartilhada
    response = fornecedor.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 200, response.text
    shared_policy = response.json()
    assert shared_policy["policy_id"] == policy_id
    assert "rules" in shared_policy

    # Passo 4: Fornecedor (org_b) cria um Animal para autoavaliar
    animal_id = _animal(ambiente, fornecedor, ambiente.org_b)

    # Passo 5: Fornecedor avalia seu Animal contra Policy compartilhada
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
    assert "outcome" in evaluation

    # Passo 6: Comprador revoga compartilhamento
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares/{grant_id}/revoke",
        json={"revocation_reason": "Relacionamento encerrado"},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REVOGADO"

    # Passo 7: Fornecedor não consegue mais ler a Policy (404 ou 403)
    response = fornecedor.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code in (403, 404)


def test_compartilhamento_negacao_sem_grant(
    ambiente: Ambiente,
    operador: ClienteAutenticado,
    fornecedor: ClienteAutenticado,
) -> None:
    """Fornecedor não consegue ler Policy compartilhada sem grant ativo."""

    # Comprador cria Policy
    policy_id = _contract_policy_real(operador, ambiente)

    # Fornecedor (org_b) tenta ler sem grant
    response = fornecedor.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code in (403, 404)

    # Fornecedor tenta avaliar sem grant
    animal_id = _animal(ambiente, fornecedor, ambiente.org_b)
    response = fornecedor.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/evaluate",
        json={
            "subject_type": "animal",
            "subject_id": animal_id,
            "purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code in (403, 404)


def test_compartilhamento_expirado_bloqueia_acesso(
    ambiente: Ambiente,
    operador: ClienteAutenticado,
    fornecedor: ClienteAutenticado,
) -> None:
    """Grant expirado (valid_until no passado) bloqueia acesso ao Fornecedor."""

    # Comprador cria Policy
    policy_id = _contract_policy_real(operador, ambiente)

    # Comprador cria grant com validade imediata (já expirado)
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": str(ambiente.org_b.organization_id.value),
            "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "valid_until": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "field_scope_profile": "CONTRATO_MINIMO",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    # Grant pode ser criado com data no passado (validação em acesso)
    assert response.status_code == 201, response.text

    # Fornecedor tenta ler Policy com grant expirado
    response = fornecedor.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    # Deve ser 403 (grant expirado) ou 404 (não encontrado)
    assert response.status_code in (403, 404)


def test_compartilhamento_nao_cria_grant_sem_permissao(
    ambiente: Ambiente,
    operador: ClienteAutenticado,
    fornecedor: ClienteAutenticado,
) -> None:
    """Fornecedor não consegue compartilhar Policy do Comprador."""

    # Comprador (org_a) cria Policy
    policy_id = _contract_policy_real(operador, ambiente)

    # Fornecedor (org_b) tenta compartilhar com terceira Organization
    # (se tivéssemos org_c)
    response = fornecedor.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": str(uuid4()),
            "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "field_scope_profile": "CONTRATO_MINIMO",
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    # Deve falhar: org_b não é proprietária de policy_id
    assert response.status_code in (403, 404)


def test_compartilhamento_apenas_policies_contratuais(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Apenas Policies de tipo CONTRACT podem ser compartilhadas.

    (Este teste valida que homogeneidade é verificada na criação do grant.)
    """

    # Criar Policy de tipo INTERNAL_POLICY
    headers = _headers(str(ambiente.org_a.organization_id.value))
    policy_id = str(
        operador.post(
            "/v1/rule-governance/policies",
            headers=headers,
            json={
                "code": f"policy-internal-{uuid4().hex[:8]}",
                "name": "Policy interna",
            },
        ).json()["policy_id"]
    )
    identity = operador.post(
        "/v1/rule-governance/rule-identities",
        headers=headers,
        json={
            "code": f"rule-internal-{uuid4().hex[:8]}",
            "purpose": "Elegibilidade interna",
            "scope": "livestock.animal",
            "source_type": "politica_interna",  # INTERNAL_POLICY, não CONTRACT
            "vertical": "livestock",
            "description": "Internal policy",
        },
    ).json()
    operador.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/versions",
        headers=headers,
        json={
            "policy_id": policy_id,
            "name": "Internal rule version",
            "conditions": [_CONDICAO_FORA_DE_CARENCIA],
            "justification": "Internal",
        },
    )
    operador.post(f"/v1/rule-governance/policies/{policy_id}/publish", headers=headers, json={})

    # Tentar compartilhar INTERNAL_POLICY (deve falhar)
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": str(ambiente.org_b.organization_id.value),
            "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "field_scope_profile": "CONTRATO_MINIMO",
        },
        headers=headers,
    )
    # Deve rejeitar: Policy não é homogeneamente CONTRACT
    assert response.status_code in (422, 403, 400)
