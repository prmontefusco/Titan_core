from datetime import UTC, datetime
from uuid import UUID, uuid4

from packages.core_application.policy_service import PolicyService
from packages.core_domain.rule import Rule
from packages.core_domain.rule_governance import RuleIdentity, RuleSourceType
from packages.core_infrastructure.persistence import set_local_organization_context
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.core_infrastructure.persistence.rule_governance import (
    TransactionalRuleIdentityRepository,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from tests.livestock_api_support import PERMISSOES_OPERADOR, _cliente

_CONDICAO_FORA_DE_CARENCIA = {
    "fact_type": "livestock.withdrawal",
    "payload_key": "in_withdrawal",
    "operator": "equals",
    "expected_value": False,
    "description": "Nao pode estar em carencia no momento da avaliacao.",
}


def _ator(org_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId(entity_type="actor", value=uuid4()),
        organization_id=org_id,
        contract_version=1,
    )


def _animal(ambiente, cliente, organizacao) -> str:  # type: ignore[no-untyped-def]
    resposta = cliente.post(
        "/v1/livestock/animals",
        json={"birth_property_id": str(ambiente.property_id.value), "sex": "FEMALE"},
        headers={"X-Titan-Organization-Id": str(organizacao.organization_id.value)},
    )
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["animal_id"])


def _buyerpolicy_homogenea(ambiente, cliente, organizacao) -> str:  # type: ignore[no-untyped-def]
    """Cria, via HTTP, uma Policy + RuleIdentity(INTERNAL_POLICY) + RuleVersion
    publicadas, prontas para avaliacao. Retorna o policy_id."""
    headers = {"X-Titan-Organization-Id": str(organizacao.organization_id.value)}
    policy_id = str(
        cliente.post(
            "/v1/rule-governance/policies",
            headers=headers,
            json={
                "code": f"buyerpolicy-{uuid4().hex[:8]}",
                "name": "Criterio interno do comprador",
            },
        ).json()["policy_id"]
    )
    identity = cliente.post(
        "/v1/rule-governance/rule-identities",
        headers=headers,
        json={
            "code": f"rule-buyerpolicy-{uuid4().hex[:8]}",
            "purpose": "Elegibilidade interna do comprador.",
            "scope": "livestock.animal",
            "source_type": "politica_interna",
            "vertical": "livestock",
            "description": "Criterio proprio do comprador.",
        },
    ).json()
    cliente.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/versions",
        headers=headers,
        json={
            "policy_id": policy_id,
            "name": "Fora de carencia",
            "conditions": [_CONDICAO_FORA_DE_CARENCIA],
            "justification": "Criterio interno do comprador.",
        },
    )
    cliente.post(f"/v1/rule-governance/policies/{policy_id}/publish", headers=headers, json={})
    return policy_id


def test_cria_publica_e_consulta_policy(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    criada = cliente.post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={
            "code": f"politica-mercado-{uuid4().hex[:8]}",
            "name": "Politica de mercado interno",
            "description": "Rascunho fictício para validar o fluxo de governança.",
        },
    )
    assert criada.status_code == 201, criada.text
    corpo = criada.json()
    assert corpo["status"] == "draft"
    assert corpo["version"] == 1
    assert corpo["published_at"] is None

    publicada = cliente.post(
        f"/v1/rule-governance/policies/{corpo['policy_id']}/publish",
        headers=headers,
        json={},
    )
    assert publicada.status_code == 200, publicada.text
    publicada_corpo = publicada.json()
    assert publicada_corpo["status"] == "published"
    assert publicada_corpo["published_at"] is not None

    consultada = cliente.get(f"/v1/rule-governance/policies/{corpo['policy_id']}", headers=headers)
    assert consultada.status_code == 200
    assert consultada.json()["status"] == "published"


def test_lista_policies_da_organization(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    codigo = f"politica-lista-{uuid4().hex[:8]}"
    cliente.post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={"code": codigo, "name": "Politica listada"},
    )

    listadas = cliente.get("/v1/rule-governance/policies", headers=headers)

    assert listadas.status_code == 200
    codigos = {item["code"] for item in listadas.json()["items"]}
    assert codigo in codigos


def test_publicar_policy_ja_publicada_e_recusado_com_conflito(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    policy_id = cliente.post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={"code": f"politica-dupla-{uuid4().hex[:8]}", "name": "Politica dupla publicacao"},
    ).json()["policy_id"]
    cliente.post(f"/v1/rule-governance/policies/{policy_id}/publish", headers=headers, json={})

    resposta = cliente.post(
        f"/v1/rule-governance/policies/{policy_id}/publish", headers=headers, json={}
    )

    assert resposta.status_code == 409
    assert resposta.json()["reason_code"] == "CONFLITO_DE_DOMINIO"


def test_publicar_policy_inexistente_retorna_404(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = cliente.post(
        f"/v1/rule-governance/policies/{uuid4()}/publish", headers=headers, json={}
    )

    assert resposta.status_code == 404
    assert resposta.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"


def test_auditor_nao_cria_policy(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = _cliente(ambiente, ambiente.auditor).post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={"code": f"politica-negada-{uuid4().hex[:8]}", "name": "Nao deve criar"},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_auditor_nao_publica_policy_mas_le(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente_operador = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    policy_id = cliente_operador.post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={"code": f"politica-leitura-{uuid4().hex[:8]}", "name": "Leitura do auditor"},
    ).json()["policy_id"]

    cliente_auditor = _cliente(ambiente, ambiente.auditor)
    negada = cliente_auditor.post(
        f"/v1/rule-governance/policies/{policy_id}/publish", headers=headers, json={}
    )
    assert negada.status_code == 403
    assert negada.json()["reason_code"] == "PERMISSAO_AUSENTE"

    permitida = cliente_auditor.get(f"/v1/rule-governance/policies/{policy_id}", headers=headers)
    assert permitida.status_code == 200


def test_criar_policy_com_codigo_repetido_e_recusado_com_conflito(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    codigo = f"politica-repetida-{uuid4().hex[:8]}"
    cliente.post(
        "/v1/rule-governance/policies", headers=headers, json={"code": codigo, "name": "Primeira"}
    )

    resposta = cliente.post(
        "/v1/rule-governance/policies", headers=headers, json={"code": codigo, "name": "Segunda"}
    )

    assert resposta.status_code == 409
    assert resposta.json()["reason_code"] == "CONFLITO_DE_DOMINIO"


def test_avaliar_buyerpolicy_homogenea_produz_evaluation_isolada(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    policy_id = _buyerpolicy_homogenea(ambiente, cliente, ambiente.org_a)
    animal_id = _animal(ambiente, cliente, ambiente.org_a)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = cliente.post(
        f"/v1/rule-governance/policies/{policy_id}/evaluate",
        headers=headers,
        json={"animal_id": animal_id, "purpose": "compra-abate"},
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["policy_id"] == policy_id
    assert corpo["origin"] == "politica_interna"
    assert corpo["recognition_boundary"] == "INTERNAL_ONLY"
    assert corpo["owner_organization_id"] == str(ambiente.org_a.organization_id.value)
    assert corpo["requesting_organization_id"] == str(ambiente.org_a.organization_id.value)
    assert corpo["outcome"] == "condicoes_satisfeitas"
    assert len(corpo["rule_results"]) == 1


def test_avaliar_policy_com_origem_heterogenea_e_recusada(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    org_id = ambiente.org_a.organization_id
    policy_id = _buyerpolicy_homogenea(ambiente, cliente, ambiente.org_a)
    animal_id = _animal(ambiente, cliente, ambiente.org_a)

    # Simula uma Policy que ja existia antes deste incremento e mistura origem:
    # insercao direta no repositorio, contornando o gate de publicacao que agora
    # recusa isso via HTTP (defesa em profundidade da avaliacao, ADR-0064 §4.3).
    set_local_organization_context(ambiente.connection, org_id)
    ator = _ator(org_id)
    identidade_regulatoria = RuleIdentity.create(
        organization_id=org_id,
        code=f"rule-regulatoria-{uuid4().hex[:8]}",
        purpose="Exigencia regulatoria.",
        scope="livestock.animal",
        source_type=RuleSourceType.LAW,
        created_by=ator,
    )
    TransactionalRuleIdentityRepository(ambiente.connection).save(identidade_regulatoria)
    regra_regulatoria = Rule.create(
        policy_id=TypedId("policy", UUID(policy_id)),
        organization_id=org_id,
        code=identidade_regulatoria.code,
        name="Exigencia regulatoria",
    )
    TransactionalRuleRepository(ambiente.connection).save(regra_regulatoria)

    resposta = cliente.post(
        f"/v1/rule-governance/policies/{policy_id}/evaluate",
        headers={"X-Titan-Organization-Id": str(org_id.value)},
        json={"animal_id": animal_id, "purpose": "compra-abate"},
    )

    assert resposta.status_code == 422, resposta.text
    assert resposta.json()["reason_code"] == "POLICY_NAO_RECONHECIDA_COMO_BUYERPOLICY"


def test_avaliar_policy_de_outra_organization_retorna_404(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente_a = _cliente(ambiente, ambiente.operador)
    policy_id = _buyerpolicy_homogenea(ambiente, cliente_a, ambiente.org_a)
    animal_id = _animal(ambiente, cliente_a, ambiente.org_a)

    principal_b = ambiente._principal_com_papel(
        subject=f"comprador-b-{uuid4().hex}",
        organizacao=ambiente.org_b,
        nome_papel=f"OPERADOR_B_{uuid4().hex[:8]}",
        permissoes=tuple(sorted(PERMISSOES_OPERADOR)),
        agora=datetime.now(UTC),
    )
    cliente_b = _cliente(ambiente, principal_b)

    resposta = cliente_b.post(
        f"/v1/rule-governance/policies/{policy_id}/evaluate",
        headers={"X-Titan-Organization-Id": str(ambiente.org_b.organization_id.value)},
        json={"animal_id": animal_id, "purpose": "compra-abate"},
    )

    assert resposta.status_code == 404, resposta.text
    assert resposta.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"


def test_auditor_nao_avalia_buyerpolicy(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente_operador = _cliente(ambiente, ambiente.operador)
    policy_id = _buyerpolicy_homogenea(ambiente, cliente_operador, ambiente.org_a)
    animal_id = _animal(ambiente, cliente_operador, ambiente.org_a)

    resposta = _cliente(ambiente, ambiente.auditor).post(
        f"/v1/rule-governance/policies/{policy_id}/evaluate",
        headers={"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)},
        json={"animal_id": animal_id, "purpose": "compra-abate"},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_avaliar_policy_revogada_e_recusada_com_conflito(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    policy_id = _buyerpolicy_homogenea(ambiente, cliente, ambiente.org_a)
    animal_id = _animal(ambiente, cliente, ambiente.org_a)

    set_local_organization_context(ambiente.connection, ambiente.org_a.organization_id)
    PolicyService(TransactionalPolicyRepository(ambiente.connection)).revoke_policy(
        TypedId("policy", UUID(policy_id))
    )

    resposta = cliente.post(
        f"/v1/rule-governance/policies/{policy_id}/evaluate",
        headers={"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)},
        json={"animal_id": animal_id, "purpose": "compra-abate"},
    )

    assert resposta.status_code == 409, resposta.text
    assert resposta.json()["reason_code"] == "CONFLITO_DE_DOMINIO"
