from uuid import uuid4

from packages.core_application.policy_service import PolicyService
from packages.core_infrastructure.persistence import set_local_organization_context
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from tests.livestock_api_support import _cliente


def _criar_policy(ambiente) -> str:  # type: ignore[no-untyped-def]
    set_local_organization_context(ambiente.connection, ambiente.org_a.organization_id)
    policy = PolicyService(TransactionalPolicyRepository(ambiente.connection)).create_draft(
        organization_id=ambiente.org_a.organization_id,
        code=f"politica-regras-{uuid4().hex[:8]}",
        name="Politica de regras governadas",
        description="Policy ficticia para validar publicacao de regra governada.",
    )
    return str(policy.policy_id.value)


def test_fluxo_http_cria_publica_e_consulta_timeline_governada(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    policy_id = _criar_policy(ambiente)

    identity_response = cliente.post(
        "/v1/rule-governance/rule-identities",
        headers=headers,
        json={
            "code": f"carencia-sanitaria-{uuid4().hex[:8]}",
            "purpose": "Bloquear abate durante carencia sanitaria.",
            "scope": "Animais com tratamento veterinario declarado.",
            "source_type": "politica_interna",
            "vertical": "livestock",
            "description": "Regra propria do frigorifico para compra.",
        },
    )
    assert identity_response.status_code == 201
    identity = identity_response.json()

    rule_response = cliente.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/versions",
        headers=headers,
        json={
            "policy_id": policy_id,
            "name": "Carencia sanitaria minima",
            "description": "Exige carencia completa antes do abate.",
            "severity": "blocking",
            "normative_source": "politica interna",
            "required_evidence_types": ["livestock.treatment_applied"],
            "conditions": [
                {
                    "fact_type": "livestock.treatment",
                    "payload_key": "withdrawal_remaining_days",
                    "operator": "less_or_equal",
                    "expected_value": 0,
                    "description": "Nao pode haver dias de carencia restantes.",
                }
            ],
            "justification": "Compra somente de animal fora da carencia.",
            "corrective_action": "Aguardar fim da carencia.",
        },
    )
    assert rule_response.status_code == 201
    rule = rule_response.json()
    assert rule["code"] == identity["code"]
    assert rule["version"] == 1

    adoption_response = cliente.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/adoptions",
        headers=headers,
        json={
            "rule_version_id": rule["rule_id"],
            "purpose": "compra-abate",
            "scope": "fornecedores-diretos",
            "reason": "Politica do frigorifico.",
        },
    )
    assert adoption_response.status_code == 201
    adoption = adoption_response.json()
    assert adoption["rule_identity_id"] == identity["rule_identity_id"]
    assert adoption["rule_version_id"] == rule["rule_id"]
    assert adoption["status"] == "active"

    timeline_response = _cliente(ambiente, ambiente.auditor).get(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/timeline",
        headers=headers,
    )
    assert timeline_response.status_code == 200
    event_types = {event["event_type"] for event in timeline_response.json()}
    assert event_types == {
        "rule_identity_created",
        "rule_version_drafted",
        "rule_version_published",
        "rule_adopted",
    }


def test_fluxo_http_substitui_adocao_ativa_por_nova_versao(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    policy_id = _criar_policy(ambiente)

    identity = cliente.post(
        "/v1/rule-governance/rule-identities",
        headers=headers,
        json={
            "code": f"carencia-revisada-{uuid4().hex[:8]}",
            "purpose": "Bloquear compra sob norma revisada.",
            "scope": "fornecedores-diretos",
            "source_type": "politica_interna",
            "vertical": "livestock",
        },
    ).json()
    rule_v1 = cliente.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/versions",
        headers=headers,
        json={"policy_id": policy_id, "name": "Carencia v1"},
    ).json()
    adoption = cliente.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/adoptions",
        headers=headers,
        json={
            "rule_version_id": rule_v1["rule_id"],
            "purpose": "compra-abate",
            "scope": "fornecedores-diretos",
            "reason": "Versao inicial.",
        },
    ).json()
    rule_v2 = cliente.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/versions",
        headers=headers,
        json={"policy_id": _criar_policy(ambiente), "name": "Carencia v2 revisada"},
    ).json()

    replaced = cliente.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/adoptions/replace",
        headers=headers,
        json={
            "current_adoption_id": adoption["adoption_id"],
            "new_rule_version_id": rule_v2["rule_id"],
            "reason": "Norma interna revisada.",
        },
    )

    assert replaced.status_code == 201, replaced.text
    body = replaced.json()
    assert body["rule_version_id"] == rule_v2["rule_id"]
    assert body["status"] == "active"

    timeline = cliente.get(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/timeline",
        headers=headers,
    ).json()
    assert timeline[-1]["event_type"] == "rule_adoption_changed"
    assert timeline[-1]["rule_version_id"] == rule_v2["rule_id"]


def test_auditor_nao_publica_versao_de_regra(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente_operador = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    policy_id = _criar_policy(ambiente)
    identity = cliente_operador.post(
        "/v1/rule-governance/rule-identities",
        headers=headers,
        json={
            "code": f"regra-auditoria-{uuid4().hex[:8]}",
            "purpose": "Validar autorizacao.",
            "scope": "Teste de API.",
            "source_type": "politica_interna",
        },
    ).json()

    resposta = _cliente(ambiente, ambiente.auditor).post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/versions",
        headers=headers,
        json={"policy_id": policy_id, "name": "Nao deve publicar"},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_auditor_nao_adota_regra(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente_operador = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    identity = cliente_operador.post(
        "/v1/rule-governance/rule-identities",
        headers=headers,
        json={
            "code": f"regra-adocao-{uuid4().hex[:8]}",
            "purpose": "Validar autorizacao.",
            "scope": "Teste de API.",
            "source_type": "politica_interna",
        },
    ).json()
    rule = cliente_operador.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/versions",
        headers=headers,
        json={"policy_id": _criar_policy(ambiente), "name": "Regra adotavel"},
    ).json()

    resposta = _cliente(ambiente, ambiente.auditor).post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/adoptions",
        headers=headers,
        json={
            "rule_version_id": rule["rule_id"],
            "purpose": "compra-abate",
            "scope": "fornecedores-diretos",
        },
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_publicar_regra_para_identidade_inexistente_retorna_404(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = _cliente(ambiente, ambiente.operador).post(
        f"/v1/rule-governance/rule-identities/{uuid4()}/versions",
        headers=headers,
        json={"policy_id": _criar_policy(ambiente), "name": "Regra sem identidade"},
    )

    assert resposta.status_code == 404
    assert resposta.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"
