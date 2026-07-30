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
    event_types = {event["event_type"] for event in timeline_response.json()["items"]}
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
    ).json()["items"]
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


def test_catalogo_http_de_templates_de_mercado_publica_fatos_e_modelos(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = _cliente(ambiente, ambiente.auditor).get(
        "/v1/rule-governance/catalogs/livestock-market-rules",
        headers=headers,
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["vertical"] == "livestock"
    assert corpo["catalog_version"] == 1

    facts = {item["fact_type"]: item for item in corpo["fact_types"]}
    assert "livestock.withdrawal" in facts
    assert "livestock.environmental_embargo.ibama" in facts
    assert facts["livestock.sanitary_requirement.brucelose"]["parameterized"] is True

    templates = {item["rule_code"]: item for item in corpo["templates"]}
    assert "rule-carencia-farmacologica" in templates
    assert "rule-embargo-ambiental-ibama" in templates
    assert "rule-exigibilidade-sanitaria" in templates
    assert (
        templates["rule-habilitacao-estabelecimento"]["conditions"][0]["fact_type"]
        == "livestock.establishment_qualification.{{market_purpose}}"
    )
    assert (
        templates["rule-exigibilidade-sanitaria"]["conditions"][0]["fact_type"]
        == "livestock.sanitary_requirement.{{campaign_code}}"
    )


def test_materializa_template_parametrizado_de_campanha_sanitaria(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = _cliente(ambiente, ambiente.operador).post(
        "/v1/rule-governance/catalogs/livestock-market-rules/templates/"
        "sanitary-requirement-campaign-v1/drafts",
        headers=headers,
        json={
            "name": "Brucelose obrigatoria para exportacao",
            "description": "Exige campanha sanitaria de brucelose satisfeita.",
            "normative_source": "IN ficticia de validacao",
            "parameters": {"campaign_code": "brucelose"},
        },
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["template_code"] == "sanitary-requirement-campaign-v1"
    assert corpo["rule_code"] == "rule-exigibilidade-sanitaria"
    assert corpo["severity"] == "blocking"
    assert corpo["normative_source"] == "IN ficticia de validacao"
    assert corpo["conditions"] == [
        {
            "fact_type": "livestock.sanitary_requirement.brucelose",
            "payload_key": "status",
            "operator": "equals",
            "expected_value": "SATISFEITO",
            "description": "A campanha sanitaria exigida precisa estar satisfeita.",
        }
    ]


def test_materializa_template_parametrizado_exige_parametro_obrigatorio(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = _cliente(ambiente, ambiente.operador).post(
        "/v1/rule-governance/catalogs/livestock-market-rules/templates/"
        "slaughterhouse-qualification-v1/drafts",
        headers=headers,
        json={
            "name": "Habilitacao do frigorifico",
            "parameters": {},
        },
    )

    assert resposta.status_code == 422
    assert resposta.json()["reason_code"] == "PARAMETRO_DE_TEMPLATE_INVALIDO"


def test_auditor_nao_materializa_rascunho_de_template(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = _cliente(ambiente, ambiente.auditor).post(
        "/v1/rule-governance/catalogs/livestock-market-rules/templates/"
        "pharmacological-withdrawal-v1/drafts",
        headers=headers,
        json={"name": "Carencia base"},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_sugere_fluxo_completo_de_governanca_para_template_de_mercado(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = _cliente(ambiente, ambiente.operador).post(
        "/v1/rule-governance/catalogs/livestock-market-rules/templates/"
        "sanitary-requirement-campaign-v1/governance-flow",
        headers=headers,
        json={
            "market_purpose": "exportacao-china",
            "adoption_scope": "livestock.animal",
            "name": "Brucelose obrigatoria para China",
            "normative_source": "Protocolo China 2026",
            "identity_description": "Regra sugerida para mercado internacional.",
            "version_description": "Campanha obrigatoria para exportacao.",
            "adoption_reason": "Ativar regra para simulacao comercial.",
            "parameters": {"campaign_code": "brucelose"},
        },
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["template_code"] == "sanitary-requirement-campaign-v1"
    assert corpo["identity"] == {
        "code": "rule-exigibilidade-sanitaria",
        "purpose": "Aplicar 'Brucelose obrigatoria para China' para o mercado 'exportacao-china'.",
        "scope": "livestock.animal",
        "source_type": "politica_interna",
        "vertical": "livestock",
        "description": "Regra sugerida para mercado internacional.",
    }
    assert corpo["version"]["rule_code"] == "rule-exigibilidade-sanitaria"
    assert corpo["version"]["name"] == "Brucelose obrigatoria para China"
    assert corpo["version"]["normative_source"] == "Protocolo China 2026"
    assert (
        corpo["version"]["conditions"][0]["fact_type"] == "livestock.sanitary_requirement.brucelose"
    )
    assert corpo["adoption"] == {
        "purpose": "exportacao-china",
        "scope": "livestock.animal",
        "reason": "Ativar regra para simulacao comercial.",
    }


def test_auditor_nao_sugere_fluxo_de_governanca(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = _cliente(ambiente, ambiente.auditor).post(
        "/v1/rule-governance/catalogs/livestock-market-rules/templates/"
        "pharmacological-withdrawal-v1/governance-flow",
        headers=headers,
        json={
            "market_purpose": "exportacao-estados-unidos",
            "adoption_scope": "livestock.animal",
            "name": "Carencia para EUA",
        },
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_executa_fluxo_assistido_e_cria_identidade_versao_e_adocao(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    policy_id = _criar_policy(ambiente)

    resposta = _cliente(ambiente, ambiente.operador).post(
        "/v1/rule-governance/catalogs/livestock-market-rules/templates/"
        "sanitary-requirement-campaign-v1/execute",
        headers=headers,
        json={
            "policy_id": policy_id,
            "market_purpose": "exportacao-china",
            "adoption_scope": "livestock.animal",
            "name": "Brucelose obrigatoria China",
            "normative_source": "Protocolo China 2026",
            "identity_description": "Fluxo assistido de validacao.",
            "version_description": "Regra publicada via fluxo guiado.",
            "adoption_reason": "Ativar regra por mercado.",
            "parameters": {"campaign_code": "brucelose"},
        },
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["template_code"] == "sanitary-requirement-campaign-v1"
    assert corpo["identity"]["code"] == "rule-exigibilidade-sanitaria"
    assert corpo["version"]["code"] == "rule-exigibilidade-sanitaria"
    assert corpo["version"]["normative_source"] == "Protocolo China 2026"
    assert (
        corpo["version"]["conditions"][0]["fact_type"] == "livestock.sanitary_requirement.brucelose"
    )
    assert corpo["adoption"] is not None
    assert corpo["adoption"]["purpose"] == "exportacao-china"
    assert corpo["adoption"]["scope"] == "livestock.animal"

    timeline = _cliente(ambiente, ambiente.auditor).get(
        f"/v1/rule-governance/rule-identities/{corpo['identity']['rule_identity_id']}/timeline",
        headers=headers,
    )
    assert timeline.status_code == 200, timeline.text
    assert {item["event_type"] for item in timeline.json()["items"]} == {
        "rule_identity_created",
        "rule_version_drafted",
        "rule_version_published",
        "rule_adopted",
    }


def test_executa_fluxo_sem_adocao_quando_solicitado(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    policy_id = _criar_policy(ambiente)

    resposta = _cliente(ambiente, ambiente.operador).post(
        "/v1/rule-governance/catalogs/livestock-market-rules/templates/"
        "pharmacological-withdrawal-v1/execute",
        headers=headers,
        json={
            "policy_id": policy_id,
            "market_purpose": "exportacao-estados-unidos",
            "adoption_scope": "livestock.animal",
            "name": "Carencia base EUA",
            "create_adoption": False,
        },
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["identity"]["code"] == "rule-carencia-farmacologica"
    assert corpo["adoption"] is None


def test_auditor_nao_executa_fluxo_assistido(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = _cliente(ambiente, ambiente.auditor).post(
        "/v1/rule-governance/catalogs/livestock-market-rules/templates/"
        "pharmacological-withdrawal-v1/execute",
        headers=headers,
        json={
            "policy_id": str(uuid4()),
            "market_purpose": "exportacao-estados-unidos",
            "adoption_scope": "livestock.animal",
            "name": "Carencia base EUA",
        },
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"
