"""Listagem, detalhe e paginação (Marco 12).

Sem listagem, quem cadastrasse um animal e perdesse o UUID não o alcançaria mais.
Estes testes cobrem o que uma interface precisa: encontrar, paginar, e não
enxergar o que é de outra organização.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from apps.api.pagination import LIMITE_MAXIMO
from packages.core_application.policy_service import PolicyService
from packages.core_infrastructure.persistence import set_local_organization_context
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.livestock_application.eligibility import (
    ELIGIBILITY_RULE_ADOPTION_SCOPE,
    ELIGIBILITY_RULE_CODE,
)
from packages.livestock_application.establishment_qualification_service import (
    establishment_qualification_fact_type,
)
from packages.livestock_application.market_eligibility import (
    ENVIRONMENTAL_EMBARGO_RULE_CODE,
    ESTABLISHMENT_RULE_CODE,
    TRACEABILITY_RULE_CODE,
    MarketEligibilityPurpose,
)
from packages.livestock_domain.environmental_embargo_assertion import (
    EnvironmentalEmbargoAssertionStatus,
    PropertyEnvironmentalEmbargoAssertion,
)
from packages.livestock_infrastructure.persistence import (
    TransactionalPropertyEnvironmentalEmbargoAssertionRepository,
)
from packages.shared_kernel import TypedId
from tests.livestock_api_support import DATABASE_URL, Ambiente, ClienteAutenticado, _cliente

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)


@pytest.fixture
def operador(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.operador)


@pytest.fixture
def auditor(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.auditor)


def _cabecalho(ambiente: Ambiente) -> dict[str, str]:
    return {ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)}


def _criar_animais(ambiente: Ambiente, operador: ClienteAutenticado, quantos: int) -> list[str]:
    criados = []
    for _ in range(quantos):
        resposta = operador.post(
            "/v1/livestock/animals",
            json={
                "birth_property_id": str(ambiente.property_id.value),
                "sex": "FEMALE",
            },
            headers=_cabecalho(ambiente),
        )
        assert resposta.status_code == 201, resposta.text
        criados.append(resposta.json()["animal_id"])
    return criados


def _criar_policy_de_regra(ambiente: Ambiente) -> str:
    set_local_organization_context(ambiente.connection, ambiente.org_a.organization_id)
    servico = PolicyService(TransactionalPolicyRepository(ambiente.connection))
    draft = servico.create_draft(
        organization_id=ambiente.org_a.organization_id,
        code=f"politica-mercado-{uuid4().hex[:8]}",
        name="Politica de elegibilidade por mercado",
        description="Policy ficticia para validar matriz comercial.",
    )
    # Politica em draft nao e executavel: PolicyEvaluationService recusa
    # avaliar qualquer coisa que nao esteja PUBLISHED ou SUPERSEDED.
    publicada = servico.publish_policy(draft.policy_id)
    return str(publicada.policy_id.value)


def _adotar_regra_de_carencia_para_mercados(
    operador: ClienteAutenticado,
    ambiente: Ambiente,
    mercados: tuple[MarketEligibilityPurpose, ...],
) -> None:
    cabecalho = _cabecalho(ambiente)
    identity = operador.post(
        "/v1/rule-governance/rule-identities",
        json={
            "code": ELIGIBILITY_RULE_CODE,
            "purpose": "Elegibilidade farmacologica por mercado.",
            "scope": ELIGIBILITY_RULE_ADOPTION_SCOPE,
            "source_type": "politica_interna",
            "vertical": "livestock",
            "description": "Regra ficticia para validar matriz comercial.",
        },
        headers=cabecalho,
    )
    assert identity.status_code == 201, identity.text
    identity_id = identity.json()["rule_identity_id"]

    rule = operador.post(
        f"/v1/rule-governance/rule-identities/{identity_id}/versions",
        json={
            "policy_id": _criar_policy_de_regra(ambiente),
            "name": "Carencia farmacologica",
            "description": "Nao aceita animal em periodo de carencia.",
            "severity": "blocking",
            "normative_source": "politica interna ficticia",
            # Sem required_evidence_types: a regra real (build_eligibility_rule,
            # eligibility.py) tambem nao declara nenhum. O fato WITHDRAWAL_FACT_TYPE
            # e sempre emitido pelo fact_provider para qualquer animal (com
            # in_withdrawal=False quando nao ha tratamento), entao exigir aqui um
            # tipo de evidencia (ex.: fato importado de tratamento) que o cenario
            # nunca produz faria esta regra ficar para sempre INDETERMINADA.
            "conditions": [
                {
                    "fact_type": "livestock.withdrawal",
                    "payload_key": "in_withdrawal",
                    "operator": "equals",
                    "expected_value": False,
                    "description": "Animal nao pode estar em periodo de carencia.",
                }
            ],
            "justification": "Destino comercial exige carencia cumprida.",
            "corrective_action": "Aguardar fim da carencia.",
        },
        headers=cabecalho,
    )
    assert rule.status_code == 201, rule.text
    rule_id = rule.json()["rule_id"]

    for mercado in mercados:
        adoption = operador.post(
            f"/v1/rule-governance/rule-identities/{identity_id}/adoptions",
            json={
                "rule_version_id": rule_id,
                "purpose": mercado.code,
                "scope": ELIGIBILITY_RULE_ADOPTION_SCOPE,
                "reason": f"Regra adotada para {mercado.code}.",
            },
            headers=cabecalho,
        )
        assert adoption.status_code == 201, adoption.text
    if MarketEligibilityPurpose.EXPORTACAO_CHINA in mercados:
        identidade_estabelecimento = operador.post(
            "/v1/rule-governance/rule-identities",
            json={
                "code": ESTABLISHMENT_RULE_CODE,
                "purpose": "Habilitacao de estabelecimento por mercado.",
                "scope": "livestock.slaughterhouse",
                "source_type": "politica_interna",
                "vertical": "livestock",
                "description": "Regra ficticia de frigorifico para validar matriz comercial.",
            },
            headers=cabecalho,
        )
        assert identidade_estabelecimento.status_code == 201, identidade_estabelecimento.text
        identity_id = identidade_estabelecimento.json()["rule_identity_id"]
        rule = operador.post(
            f"/v1/rule-governance/rule-identities/{identity_id}/versions",
            json={
                "policy_id": _criar_policy_de_regra(ambiente),
                "name": "Habilitacao do estabelecimento",
                "description": "Exige frigorifico com SIF.",
                "severity": "blocking",
                "normative_source": "politica interna ficticia",
                "required_evidence_types": ["livestock.external_counterparty"],
                "conditions": [
                    {
                        "fact_type": establishment_qualification_fact_type(
                            MarketEligibilityPurpose.EXPORTACAO_CHINA.code
                        ),
                        "payload_key": "qualification_status",
                        "operator": "equals",
                        "expected_value": "HABILITADO",
                        "description": "O estabelecimento deve estar habilitado para a China.",
                    },
                ],
                "justification": "China exige habilitacao do estabelecimento escolhido.",
                "corrective_action": "Selecionar frigorifico habilitado com SIF.",
            },
            headers=cabecalho,
        )
        assert rule.status_code == 201, rule.text
        adoption = operador.post(
            f"/v1/rule-governance/rule-identities/{identity_id}/adoptions",
            json={
                "rule_version_id": rule.json()["rule_id"],
                "purpose": MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                "scope": "livestock.slaughterhouse",
                "reason": "Regra adotada para a habilitacao do estabelecimento na China.",
            },
            headers=cabecalho,
        )
        assert adoption.status_code == 201, adoption.text
    if MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA in mercados:
        # O perfil da UE (DEFAULT_MARKET_PROFILES) tem tres requisitos: carencia,
        # rastreabilidade minima e embargo ambiental. Sem adotar tambem os dois
        # complementares, algum requisito fica AUSENTE, e AUSENTE tem precedencia sobre
        # INDETERMINADO na agregacao (_aggregate_requirement_status) -- o
        # status do mercado inteiro apareceria como AUSENTE em vez de refletir
        # o requisito de carencia que o teste realmente quer exercitar.
        identidade_rastreabilidade = operador.post(
            "/v1/rule-governance/rule-identities",
            json={
                "code": TRACEABILITY_RULE_CODE,
                "purpose": "Rastreabilidade minima por mercado.",
                "scope": ELIGIBILITY_RULE_ADOPTION_SCOPE,
                "source_type": "politica_interna",
                "vertical": "livestock",
                "description": "Regra ficticia de rastreabilidade para validar matriz comercial.",
            },
            headers=cabecalho,
        )
        assert identidade_rastreabilidade.status_code == 201, identidade_rastreabilidade.text
        identity_id = identidade_rastreabilidade.json()["rule_identity_id"]
        rule = operador.post(
            f"/v1/rule-governance/rule-identities/{identity_id}/versions",
            json={
                "policy_id": _criar_policy_de_regra(ambiente),
                "name": "Rastreabilidade minima",
                "description": "Exige historico rastreavel do animal.",
                "severity": "blocking",
                "normative_source": "politica interna ficticia",
                "conditions": [
                    {
                        "fact_type": "livestock.withdrawal",
                        "payload_key": "in_withdrawal",
                        "operator": "equals",
                        "expected_value": False,
                        "description": "Fato sempre presente, usado apenas para "
                        "exercitar o requisito de rastreabilidade na matriz.",
                    }
                ],
                "justification": "UE exige rastreabilidade minima do animal.",
                "corrective_action": "Completar o historico rastreavel do animal.",
            },
            headers=cabecalho,
        )
        assert rule.status_code == 201, rule.text
        adoption = operador.post(
            f"/v1/rule-governance/rule-identities/{identity_id}/adoptions",
            json={
                "rule_version_id": rule.json()["rule_id"],
                "purpose": MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA.code,
                "scope": ELIGIBILITY_RULE_ADOPTION_SCOPE,
                "reason": "Regra adotada para a rastreabilidade minima na UE.",
            },
            headers=cabecalho,
        )
        assert adoption.status_code == 201, adoption.text
        identidade_embargo = operador.post(
            "/v1/rule-governance/rule-identities",
            json={
                "code": ENVIRONMENTAL_EMBARGO_RULE_CODE,
                "purpose": "Embargo ambiental por mercado.",
                "scope": ELIGIBILITY_RULE_ADOPTION_SCOPE,
                "source_type": "politica_interna",
                "vertical": "livestock",
                "description": "Regra ficticia de embargo ambiental para validar matriz comercial.",
            },
            headers=cabecalho,
        )
        assert identidade_embargo.status_code == 201, identidade_embargo.text
        identity_id = identidade_embargo.json()["rule_identity_id"]
        rule = operador.post(
            f"/v1/rule-governance/rule-identities/{identity_id}/versions",
            json={
                "policy_id": _criar_policy_de_regra(ambiente),
                "name": "Ausencia de embargo ambiental do IBAMA",
                "description": "Exige ausencia de embargo ambiental conhecido.",
                "severity": "blocking",
                "normative_source": "politica interna ficticia",
                "conditions": [
                    {
                        "fact_type": "livestock.environmental_embargo.ibama",
                        "payload_key": "status",
                        "operator": "equals",
                        "expected_value": "SEM_RESTRICAO",
                        "description": "A propriedade nao pode ter embargo ambiental do IBAMA.",
                    }
                ],
                "justification": "UE exige ausencia de embargo ambiental conhecido.",
                "corrective_action": "Resolver o embargo ou registrar nova assertion valida.",
            },
            headers=cabecalho,
        )
        assert rule.status_code == 201, rule.text
        adoption = operador.post(
            f"/v1/rule-governance/rule-identities/{identity_id}/adoptions",
            json={
                "rule_version_id": rule.json()["rule_id"],
                "purpose": MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA.code,
                "scope": ELIGIBILITY_RULE_ADOPTION_SCOPE,
                "reason": "Regra adotada para embargo ambiental na UE.",
            },
            headers=cabecalho,
        )
        assert adoption.status_code == 201, adoption.text


def _registrar_assertion_embargo_ambiental(
    ambiente: Ambiente,
    *,
    status: EnvironmentalEmbargoAssertionStatus,
) -> None:
    set_local_organization_context(ambiente.connection, ambiente.org_a.organization_id)
    assertion = PropertyEnvironmentalEmbargoAssertion.create(
        organization_id=ambiente.org_a.organization_id,
        property_id=ambiente.property_id,
        geometry_id=TypedId.new("property_geometry"),
        geometry_version=1,
        source_name="IBAMA",
        source_layer="IBAMA_EMBARGOS",
        operation="intersects",
        status=status,
        source_digest="a" * 64,
        response_digest="b" * 64,
        version_ids=("ibama_v1",),
        restrictions_payload=(
            {
                "source": "IBAMA",
                "layer": "IBAMA_EMBARGOS",
                "feature_id": 101,
                "version_id": "ibama_v1",
                "polygon_digest": "c" * 64,
                "attributes": {"nom_embarg": "Area de validacao"},
            },
        )
        if status is EnvironmentalEmbargoAssertionStatus.COM_RESTRICAO
        else (),
        observed_at=datetime.now(UTC),
    )
    TransactionalPropertyEnvironmentalEmbargoAssertionRepository(ambiente.connection).save(
        assertion
    )


def _criar_contraparte_externa(
    operador: ClienteAutenticado,
    ambiente: Ambiente,
    *,
    name: str,
    counterparty_type: str,
) -> str:
    resposta = operador.post(
        "/v1/livestock/external-counterparties",
        json={
            "name": name,
            "counterparty_type": counterparty_type,
        },
        headers=_cabecalho(ambiente),
    )
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["counterparty_id"])


def _registrar_qualificacao_de_estabelecimento(
    operador: ClienteAutenticado,
    ambiente: Ambiente,
    *,
    counterparty_id: str,
    market_purpose: str,
    status: str = "HABILITADO",
) -> None:
    resposta = operador.post(
        f"/v1/livestock/external-counterparties/{counterparty_id}/establishment-qualifications",
        json={
            "market_purpose": market_purpose,
            "status": status,
            "source_name": "lista-sif-ficticia",
            "source_version": "2026-07",
            "assessed_at": datetime.now(UTC).isoformat(),
        },
        headers=_cabecalho(ambiente),
    )
    assert resposta.status_code == 201, resposta.text


def test_o_animal_cadastrado_aparece_na_listagem(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """É o que torna a API utilizável: cadastrar e depois encontrar."""
    criado = _criar_animais(ambiente, operador, 1)[0]

    resposta = operador.get("/v1/livestock/animals", headers=_cabecalho(ambiente))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert criado in [item["animal_id"] for item in corpo["items"]]
    assert corpo["limit"] > 0
    assert corpo["offset"] == 0


def test_a_pagina_indica_se_ha_mais_sem_precisar_contar_tudo(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """`has_more` responde a pergunta da interface sem varrer a tabela."""
    _criar_animais(ambiente, operador, 3)

    primeira = operador.get(
        "/v1/livestock/animals?limit=2&offset=0", headers=_cabecalho(ambiente)
    ).json()

    assert len(primeira["items"]) == 2
    assert primeira["has_more"] is True

    segunda = operador.get(
        "/v1/livestock/animals?limit=2&offset=2", headers=_cabecalho(ambiente)
    ).json()
    assert segunda["has_more"] is False
    # As páginas não se sobrepõem.
    assert not {i["animal_id"] for i in primeira["items"]} & {
        i["animal_id"] for i in segunda["items"]
    }


def test_pedir_acima_do_teto_e_recusado_e_nao_reduzido_em_silencio(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Reduzir calado faria o cliente acreditar que recebeu tudo."""
    resposta = operador.get(
        f"/v1/livestock/animals?limit={LIMITE_MAXIMO + 1}", headers=_cabecalho(ambiente)
    )

    assert resposta.status_code == 422
    assert resposta.json()["reason_code"] == "ENTRADA_INVALIDA"


def test_o_detalhe_traz_o_animal_pelo_identificador(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    criado = _criar_animais(ambiente, operador, 1)[0]

    resposta = operador.get(f"/v1/livestock/animals/{criado}", headers=_cabecalho(ambiente))

    assert resposta.status_code == 200
    assert resposta.json()["animal_id"] == criado


def test_animal_de_outra_organizacao_responde_como_inexistente(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Distinguir viraria oráculo sobre o que existe fora do alcance."""
    criado = _criar_animais(ambiente, operador, 1)[0]

    resposta = operador.get(
        f"/v1/livestock/animals/{criado}",
        headers={ORGANIZATION_HEADER: str(ambiente.org_b.organization_id.value)},
    )

    # A negação acontece antes: o operador não opera na Org B.
    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "CONTEXTO_ORGANIZACIONAL_NEGADO"


def test_identificador_malformado_e_erro_do_cliente(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    resposta = operador.get("/v1/livestock/animals/nao-e-uuid", headers=_cabecalho(ambiente))

    assert resposta.status_code == 422
    assert resposta.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_o_ciclo_completo_de_uma_entidade_nova_funciona_pela_api(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Propriedade não tinha rota alguma; agora cria, lista e detalha."""
    cabecalho = _cabecalho(ambiente)
    criada = operador.post(
        "/v1/livestock/properties",
        json={
            "code": f"FAZ-{datetime.now(UTC).timestamp():.0f}",
            "name": "Fazenda Nova",
            "municipality": "Uberaba",
            "state_code": "MG",
            "total_area_hectares": 320.5,
        },
        headers=cabecalho,
    )
    assert criada.status_code == 201, criada.text
    property_id = criada.json()["property_id"]

    listagem = operador.get("/v1/livestock/properties", headers=cabecalho).json()
    assert property_id in [item["property_id"] for item in listagem["items"]]

    detalhe = operador.get(f"/v1/livestock/properties/{property_id}", headers=cabecalho)
    assert detalhe.status_code == 200
    assert detalhe.json()["total_area_hectares"] == 320.5


def test_lote_recebe_e_encerra_a_permanencia_sem_apagar_o_vinculo(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Não há DELETE: encerrar fecha a vigência e o vínculo continua na história."""
    cabecalho = _cabecalho(ambiente)
    animal = _criar_animais(ambiente, operador, 1)[0]
    lote = operador.post(
        "/v1/livestock/lots",
        json={
            "property_id": str(ambiente.property_id.value),
            "code": f"L-{datetime.now(UTC).timestamp():.0f}",
            "name": "Lote de teste",
        },
        headers=cabecalho,
    ).json()["lot_id"]

    assert (
        operador.post(
            f"/v1/livestock/lots/{lote}/members",
            json={"animal_id": animal},
            headers=cabecalho,
        ).status_code
        == 201
    )
    vigente = operador.get(f"/v1/livestock/lots/{lote}/members", headers=cabecalho).json()
    assert len(vigente["members"]) == 1

    encerrado = operador.post(
        f"/v1/livestock/lots/{lote}/removals",
        json={"animal_id": animal},
        headers=cabecalho,
    )
    assert encerrado.status_code == 201
    assert encerrado.json()["valid_until"] is not None

    depois = operador.get(f"/v1/livestock/lots/{lote}/members", headers=cabecalho).json()
    assert depois["members"] == []

    # A composição é temporal: no instante da inclusão o animal estava lá.
    instante = encerrado.json()["valid_from"]
    antes = operador.get(
        f"/v1/livestock/lots/{lote}/members?at_time={instante}", headers=cabecalho
    ).json()
    assert len(antes["members"]) == 1


def test_movimentacao_e_um_fato_so_ainda_que_mova_varios(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)
    animais = _criar_animais(ambiente, operador, 2)
    destino = operador.post(
        "/v1/livestock/properties",
        json={
            "code": f"DEST-{datetime.now(UTC).timestamp():.0f}",
            "name": "Destino",
            "municipality": "Franca",
            "state_code": "SP",
        },
        headers=cabecalho,
    ).json()["property_id"]

    resposta = operador.post(
        "/v1/livestock/movements",
        json={
            "origin_property_id": str(ambiente.property_id.value),
            "destination_property_id": destino,
            "movement_time": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "animal_ids": animais,
            "reason": "Transferência para engorda",
        },
        headers=cabecalho,
    )

    assert resposta.status_code == 201, resposta.text
    assert sorted(resposta.json()["animal_ids"]) == sorted(animais)

    por_animal = operador.get(
        f"/v1/livestock/movements?animal_id={animais[0]}", headers=cabecalho
    ).json()
    assert len(por_animal["items"]) == 1


def test_o_veterinario_nao_expoe_cpf_na_consulta(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Dado de pessoa natural não sai da API só porque é necessário para cadastrar."""
    cabecalho = _cabecalho(ambiente)
    cpf = "12345678901"
    criado = operador.post(
        "/v1/livestock/veterinarians",
        json={
            "name": "Dra. Fictícia",
            "cpf": cpf,
            "council_number": f"{datetime.now(UTC).timestamp():.0f}",
            "council_state": "MG",
        },
        headers=cabecalho,
    )
    assert criado.status_code == 201, criado.text
    assert cpf not in criado.text

    detalhe = operador.get(
        f"/v1/livestock/veterinarians/{criado.json()['veterinarian_id']}", headers=cabecalho
    )
    assert detalhe.status_code == 200
    assert cpf not in detalhe.text


def test_o_auditor_le_mas_nao_escreve_nas_rotas_novas(
    ambiente: Ambiente, auditor: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)

    assert auditor.get("/v1/livestock/properties", headers=cabecalho).status_code == 200

    recusado = auditor.post(
        "/v1/livestock/properties",
        json={
            "code": "X-1",
            "name": "Não deve entrar",
            "municipality": "X",
            "state_code": "MG",
        },
        headers=cabecalho,
    )
    assert recusado.status_code == 403
    assert recusado.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_os_dossies_de_um_sujeito_sao_encontraveis_sem_saber_o_uuid(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    """Antes só se achava um dossiê sabendo o identificador dele."""
    cabecalho = _cabecalho(ambiente)
    animal = _criar_animais(ambiente, operador, 1)[0]
    elegibilidade = operador.post(
        f"/v1/livestock/animals/{animal}/eligibility", json={}, headers=cabecalho
    )
    assert elegibilidade.status_code == 201, elegibilidade.text

    encontrados = auditor.get(f"/v1/livestock/dossiers?subject_id={animal}", headers=cabecalho)

    assert encontrados.status_code == 200
    corpo = encontrados.json()
    assert corpo["subject_id"] == animal
    assert elegibilidade.json()["dossier_id"] in [i["dossier_id"] for i in corpo["items"]]
    assert all(item["dossier_hash"] for item in corpo["items"])


def test_matriz_de_mercado_mostra_destinos_e_regras_ausentes(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)
    animal = _criar_animais(ambiente, operador, 1)[0]
    _adotar_regra_de_carencia_para_mercados(
        operador,
        ambiente,
        (
            MarketEligibilityPurpose.EXPORTACAO_CHINA,
            MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS,
        ),
    )

    resposta = operador.post(
        f"/v1/livestock/animals/{animal}/eligibility/market-matrix",
        json={},
        headers=cabecalho,
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["animal_id"] == animal
    assert corpo["evaluation_id"]
    assert corpo["decision_id"]
    por_mercado = {item["market"]: item for item in corpo["markets"]}
    assert por_mercado["exportacao-china"]["status"] == "CONDICIONADO"
    assert por_mercado["exportacao-china"]["projection_status"] == "ATUAL"
    assert por_mercado["exportacao-estados-unidos"]["status"] == "ELEGIVEL"
    assert por_mercado["exportacao-uniao-europeia"]["status"] == "AUSENTE"
    assert por_mercado["exportacao-china"]["governed_rule"]["purpose"] == "exportacao-china"
    assert por_mercado["exportacao-china"]["adoption"]["purpose"] == "exportacao-china"
    assert por_mercado["exportacao-china"]["adoption"]["reason"] == (
        "Regra adotada para exportacao-china."
    )
    assert por_mercado["exportacao-china"]["execution"]["evaluation_id"]
    assert por_mercado["exportacao-china"]["execution"]["decision_id"]
    assert por_mercado["exportacao-china"]["rule_version"]["code"] == (
        "rule-carencia-farmacologica"
    )
    assert por_mercado["exportacao-china"]["rule_version"]["version"] == 1
    assert por_mercado["exportacao-china"]["rule_version"]["justification"] == (
        "Destino comercial exige carencia cumprida."
    )
    assert por_mercado["exportacao-china"]["rule_version"]["corrective_action"] == (
        "Aguardar fim da carencia."
    )
    assert por_mercado["exportacao-china"]["dependency"] == {
        "subject_key": "slaughterhouse",
        "subject_label": "estabelecimento",
        "selected_subject_id": None,
    }
    assert por_mercado["exportacao-china"]["gaps"][0]["code"] == (
        "DEPENDENCIA_DE_SUJEITO_NAO_ESCOLHIDO"
    )
    assert por_mercado["exportacao-china"]["reasons"][0]["code"] == "regra_atendida"
    assert (
        por_mercado["exportacao-china"]["reasons"][0]["rule_code"] == "rule-carencia-farmacologica"
    )
    assert [
        requisito["rule_code"] for requisito in por_mercado["exportacao-china"]["requirements"]
    ] == ["rule-carencia-farmacologica", "rule-habilitacao-estabelecimento"]
    assert por_mercado["exportacao-china"]["requirements"][0]["status"] == "ELEGIVEL"
    assert por_mercado["exportacao-china"]["requirements"][0]["projection_status"] == "ATUAL"
    assert por_mercado["exportacao-china"]["requirements"][0]["execution"]["evaluation_id"]
    assert por_mercado["exportacao-china"]["requirements"][0]["execution"]["decision_id"]
    assert por_mercado["exportacao-china"]["requirements"][0]["adoption"]["purpose"] == (
        "exportacao-china"
    )
    assert por_mercado["exportacao-china"]["requirements"][0]["rule_version"]["code"] == (
        "rule-carencia-farmacologica"
    )
    assert por_mercado["exportacao-china"]["requirements"][1]["status"] == "CONDICIONADO"
    assert por_mercado["exportacao-china"]["requirements"][1]["dependency"] == {
        "subject_key": "slaughterhouse",
        "subject_label": "estabelecimento",
        "selected_subject_id": None,
    }
    assert por_mercado["exportacao-china"]["requirements"][1]["gaps"][0]["code"] == (
        "DEPENDENCIA_DE_SUJEITO_NAO_ESCOLHIDO"
    )
    assert (
        por_mercado["exportacao-china"]["execution"]["decision_id"]
        != por_mercado["exportacao-estados-unidos"]["execution"]["decision_id"]
    )
    requisitos_europa = por_mercado["exportacao-uniao-europeia"]["requirements"]
    assert [requisito["rule_code"] for requisito in requisitos_europa] == [
        "rule-carencia-farmacologica",
        "rule-rastreabilidade-minima",
        "rule-embargo-ambiental-ibama",
    ]
    assert [requisito["status"] for requisito in requisitos_europa] == [
        "AUSENTE",
        "AUSENTE",
        "AUSENTE",
    ]
    assert all(requisito["adoption"] is None for requisito in requisitos_europa)
    assert all(requisito["rule_version"] is None for requisito in requisitos_europa)


def test_avaliacao_orientada_a_mercados_filtra_os_mercados_solicitados(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)
    animal = _criar_animais(ambiente, operador, 1)[0]
    _adotar_regra_de_carencia_para_mercados(
        operador,
        ambiente,
        (
            MarketEligibilityPurpose.EXPORTACAO_CHINA,
            MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS,
            MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA,
        ),
    )

    resposta = operador.post(
        "/v1/livestock/market-eligibility/evaluations",
        json={
            "animal_id": animal,
            "markets": [
                MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
            ],
        },
        headers=cabecalho,
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["animal_id"] == animal
    assert corpo["requested_markets"] == [
        MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
        MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
    ]
    assert corpo["commercial_outlook"] == "PARCIALMENTE_COMERCIALIZAVEL"
    assert corpo["can_sell_to_any_requested_market"] is True
    assert "ao menos um mercado solicitado elegivel" in corpo["executive_summary"]
    assert corpo["eligible_markets"] == [MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code]
    assert corpo["blocked_markets"] == []
    assert corpo["conditioned_markets"] == [MarketEligibilityPurpose.EXPORTACAO_CHINA.code]
    assert corpo["indeterminate_markets"] == []
    assert corpo["missing_markets"] == []
    assert corpo["required_subjects"] == [
        {
            "market": MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
            "subject_key": "slaughterhouse",
            "subject_label": "estabelecimento",
        }
    ]
    assert corpo["top_gaps"][0]["market"] == MarketEligibilityPurpose.EXPORTACAO_CHINA.code
    assert corpo["top_gaps"][0]["code"] == "DEPENDENCIA_DE_SUJEITO_NAO_ESCOLHIDO"
    por_mercado = {item["market"]: item for item in corpo["markets"]}
    assert set(por_mercado) == {
        MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
        MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
    }
    assert por_mercado["exportacao-china"]["status"] == "CONDICIONADO"
    assert "selecione o estabelecimento exigido" in por_mercado["exportacao-china"]["summary"]
    assert por_mercado["exportacao-estados-unidos"]["status"] == "ELEGIVEL"
    assert por_mercado["exportacao-estados-unidos"]["summary"] == (
        "Mercado elegivel para comercializacao."
    )


def test_avaliacao_orientada_a_mercados_recusa_mercado_desconhecido(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)
    animal = _criar_animais(ambiente, operador, 1)[0]

    resposta = operador.post(
        "/v1/livestock/market-eligibility/evaluations",
        json={
            "animal_id": animal,
            "markets": ["exportacao-marte"],
        },
        headers=cabecalho,
    )

    assert resposta.status_code == 422, resposta.text
    assert resposta.json()["reason_code"] == "ENTRADA_INVALIDA"


def test_explicacao_comercial_do_animal_resume_mercados_e_proxima_acao(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)
    animal = _criar_animais(ambiente, operador, 1)[0]
    _adotar_regra_de_carencia_para_mercados(
        operador,
        ambiente,
        (
            MarketEligibilityPurpose.EXPORTACAO_CHINA,
            MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS,
        ),
    )

    resposta = operador.post(
        "/v1/livestock/market-eligibility/commercial-explanations",
        json={
            "animal_id": animal,
            "markets": [
                MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
            ],
        },
        headers=cabecalho,
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["subject_type"] == "animal"
    assert corpo["subject_id"] == animal
    assert corpo["commercial_outlook"] == "PARCIALMENTE_COMERCIALIZAVEL"
    assert "Estados Unidos" in corpo["narrative"]
    assert "China" in corpo["narrative"]
    assert corpo["recommended_next_action"] == (
        "Selecionar e qualificar o estabelecimento exigido para os mercados condicionados."
    )
    por_mercado = {item["market"]: item for item in corpo["markets"]}
    assert por_mercado["exportacao-china"]["status"] == "CONDICIONADO"
    assert por_mercado["exportacao-china"]["next_action"] == (
        "Selecionar o estabelecimento exigido e repetir a avaliacao deste mercado."
    )
    assert por_mercado["exportacao-china"]["affected_animal_ids"] == []
    assert any("estabelecimento exigido" in why for why in por_mercado["exportacao-china"]["why"])


def test_listar_perfis_de_mercado_publica_requisitos_e_dependencias(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)

    resposta = operador.get(
        "/v1/livestock/market-eligibility/profiles",
        headers=cabecalho,
    )

    assert resposta.status_code == 200, resposta.text
    perfis = {item["market"]: item for item in resposta.json()}
    assert set(perfis) == {
        MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA.code,
        MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
        MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
    }
    assert perfis["exportacao-estados-unidos"]["declared_withdrawal_period_days"] == 30
    assert [req["rule_code"] for req in perfis["exportacao-uniao-europeia"]["requirements"]] == [
        ELIGIBILITY_RULE_CODE,
        TRACEABILITY_RULE_CODE,
        ENVIRONMENTAL_EMBARGO_RULE_CODE,
    ]
    assert perfis["exportacao-china"]["requirements"][1] == {
        "rule_code": ESTABLISHMENT_RULE_CODE,
        "scope": "livestock.slaughterhouse",
        "dependent_subject_key": "slaughterhouse",
        "dependent_subject_label": "estabelecimento",
    }


def test_avaliacao_orientada_a_mercados_para_lote_agrega_os_animais_vigentes(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)
    animais = _criar_animais(ambiente, operador, 2)
    _adotar_regra_de_carencia_para_mercados(
        operador,
        ambiente,
        (
            MarketEligibilityPurpose.EXPORTACAO_CHINA,
            MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS,
        ),
    )
    lote = operador.post(
        "/v1/livestock/lots",
        json={
            "property_id": str(ambiente.property_id.value),
            "code": f"L-{datetime.now(UTC).timestamp():.0f}",
            "name": "Lote mercado",
        },
        headers=cabecalho,
    ).json()["lot_id"]
    for animal_id in animais:
        resposta = operador.post(
            f"/v1/livestock/lots/{lote}/members",
            json={"animal_id": animal_id},
            headers=cabecalho,
        )
        assert resposta.status_code == 201, resposta.text

    resposta = operador.post(
        "/v1/livestock/market-eligibility/lots/evaluations",
        json={
            "lot_id": lote,
            "markets": [
                MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
            ],
        },
        headers=cabecalho,
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["lot_id"] == lote
    assert corpo["member_count"] == 2
    assert corpo["commercial_outlook"] == "PARCIALMENTE_COMERCIALIZAVEL"
    assert corpo["can_sell_to_any_requested_market"] is True
    assert corpo["eligible_markets"] == [MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code]
    assert corpo["conditioned_markets"] == [MarketEligibilityPurpose.EXPORTACAO_CHINA.code]
    assert corpo["required_subjects"] == [
        {
            "market": MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
            "subject_key": "slaughterhouse",
            "subject_label": "estabelecimento",
        }
    ]
    por_mercado = {item["market"]: item for item in corpo["markets"]}
    assert set(por_mercado) == {
        MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
        MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
    }
    assert por_mercado["exportacao-estados-unidos"]["status"] == "ELEGIVEL"
    assert (
        "Todos os 2 animais vigentes do lote estao elegiveis"
        in por_mercado["exportacao-estados-unidos"]["summary"]
    )
    assert sorted(por_mercado["exportacao-estados-unidos"]["eligible_animal_ids"]) == sorted(
        animais
    )
    assert por_mercado["exportacao-china"]["status"] == "CONDICIONADO"
    assert "depende da escolha do estabelecimento" in por_mercado["exportacao-china"]["summary"]
    assert sorted(por_mercado["exportacao-china"]["conditioned_animal_ids"]) == sorted(animais)


def test_avaliacao_orientada_a_mercados_para_lote_usa_frigorifico_escolhido(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)
    animais = _criar_animais(ambiente, operador, 2)
    slaughterhouse_id = _criar_contraparte_externa(
        operador,
        ambiente,
        name="Frigorifico Lote China",
        counterparty_type="SLAUGHTERHOUSE",
    )
    _adotar_regra_de_carencia_para_mercados(
        operador,
        ambiente,
        (
            MarketEligibilityPurpose.EXPORTACAO_CHINA,
            MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS,
        ),
    )
    _registrar_qualificacao_de_estabelecimento(
        operador,
        ambiente,
        counterparty_id=slaughterhouse_id,
        market_purpose=MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
    )
    lote = operador.post(
        "/v1/livestock/lots",
        json={
            "property_id": str(ambiente.property_id.value),
            "code": f"L-{datetime.now(UTC).timestamp():.0f}",
            "name": "Lote China habilitado",
        },
        headers=cabecalho,
    ).json()["lot_id"]
    for animal_id in animais:
        resposta = operador.post(
            f"/v1/livestock/lots/{lote}/members",
            json={"animal_id": animal_id},
            headers=cabecalho,
        )
        assert resposta.status_code == 201, resposta.text

    resposta = operador.post(
        "/v1/livestock/market-eligibility/lots/evaluations",
        json={
            "lot_id": lote,
            "markets": [
                MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
            ],
            "slaughterhouse_counterparty_id": slaughterhouse_id,
        },
        headers=cabecalho,
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["commercial_outlook"] == "TOTALMENTE_COMERCIALIZAVEL"
    assert corpo["can_sell_to_any_requested_market"] is True
    assert corpo["eligible_markets"] == [
        MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
        MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
    ]
    assert corpo["conditioned_markets"] == []
    assert corpo["required_subjects"] == []
    por_mercado = {item["market"]: item for item in corpo["markets"]}
    china = por_mercado[MarketEligibilityPurpose.EXPORTACAO_CHINA.code]
    assert china["status"] == "ELEGIVEL"
    assert china["dependency"] == {
        "subject_key": "slaughterhouse",
        "subject_label": "estabelecimento",
        "selected_subject_id": slaughterhouse_id,
    }
    assert "Todos os 2 animais vigentes do lote estao elegiveis" in china["summary"]
    assert sorted(china["eligible_animal_ids"]) == sorted(animais)
    for animal in china["animals"]:
        assert animal["status"] == "ELEGIVEL"
        assert animal["dependency"] == {
            "subject_key": "slaughterhouse",
            "subject_label": "estabelecimento",
            "selected_subject_id": slaughterhouse_id,
        }
        assert animal["summary"] == "Mercado elegivel com o estabelecimento selecionado."


def test_explicacao_comercial_do_lote_resume_animais_afetados(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)
    animais = _criar_animais(ambiente, operador, 2)
    _adotar_regra_de_carencia_para_mercados(
        operador,
        ambiente,
        (
            MarketEligibilityPurpose.EXPORTACAO_CHINA,
            MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS,
        ),
    )
    lote = operador.post(
        "/v1/livestock/lots",
        json={
            "property_id": str(ambiente.property_id.value),
            "code": f"L-{datetime.now(UTC).timestamp():.0f}",
            "name": "Lote explicacao comercial",
        },
        headers=cabecalho,
    ).json()["lot_id"]
    for animal_id in animais:
        resposta = operador.post(
            f"/v1/livestock/lots/{lote}/members",
            json={"animal_id": animal_id},
            headers=cabecalho,
        )
        assert resposta.status_code == 201, resposta.text

    resposta = operador.post(
        "/v1/livestock/market-eligibility/commercial-explanations",
        json={
            "lot_id": lote,
            "markets": [
                MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
            ],
        },
        headers=cabecalho,
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["subject_type"] == "lot"
    assert corpo["subject_id"] == lote
    assert corpo["commercial_outlook"] == "PARCIALMENTE_COMERCIALIZAVEL"
    assert "O lote pode ser comercializado" in corpo["narrative"]
    assert corpo["recommended_next_action"] == (
        "Selecionar e qualificar o estabelecimento exigido para os mercados condicionados."
    )
    por_mercado = {item["market"]: item for item in corpo["markets"]}
    china = por_mercado["exportacao-china"]
    assert china["status"] == "CONDICIONADO"
    assert china["affected_animal_ids"] == []
    assert china["next_action"] == (
        "Selecionar o estabelecimento exigido e repetir a avaliacao deste mercado."
    )
    assert any("selecione o estabelecimento exigido" in why for why in china["why"])
    estados_unidos = por_mercado["exportacao-estados-unidos"]
    assert estados_unidos["status"] == "ELEGIVEL"
    assert estados_unidos["why"] == [
        "Todos os animais vigentes apareceram elegiveis neste mercado."
    ]


def test_explicacao_comercial_recusa_quando_sujeito_nao_e_unico(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)

    resposta = operador.post(
        "/v1/livestock/market-eligibility/commercial-explanations",
        json={},
        headers=cabecalho,
    )

    assert resposta.status_code == 422, resposta.text
    assert resposta.json()["reason_code"] == "ENTRADA_INVALIDA"


def test_matriz_de_mercado_falha_fechado_sem_carencia_declarada_por_mercado(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)
    animal = _criar_animais(ambiente, operador, 1)[0]
    _adotar_regra_de_carencia_para_mercados(
        operador,
        ambiente,
        (MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA,),
    )

    resposta = operador.post(
        f"/v1/livestock/animals/{animal}/eligibility/market-matrix",
        json={},
        headers=cabecalho,
    )

    assert resposta.status_code == 201, resposta.text
    europa = {item["market"]: item for item in resposta.json()["markets"]}[
        "exportacao-uniao-europeia"
    ]
    assert europa["status"] == "INDETERMINADO"
    assert europa["adoption"]["purpose"] == "exportacao-uniao-europeia"
    assert europa["rule_version"]["code"] == "rule-carencia-farmacologica"
    assert europa["requirements"][0]["status"] == "INDETERMINADO"
    assert europa["requirements"][0]["gaps"][0]["code"] == "CARENCIA_POR_MERCADO_AUSENTE"
    # requirements[0] (carencia) e curto-circuitado pela lacuna acima, sem
    # reasons proprias. requirements[1] (rastreabilidade) e [2] (embargo
    # ambiental) sao adotados e executados normalmente, entao as reasons
    # agregadas do mercado vem deles -- nao ha reasons "fantasma" nem
    # confusao entre os tres requisitos.
    assert [reason["rule_code"] for reason in europa["reasons"]] == [
        "rule-rastreabilidade-minima",
        "rule-embargo-ambiental-ibama",
    ]
    assert europa["requirements"][1]["rule_code"] == "rule-rastreabilidade-minima"
    assert europa["requirements"][1]["status"] == "ELEGIVEL"
    assert europa["requirements"][2]["rule_code"] == "rule-embargo-ambiental-ibama"
    assert europa["requirements"][2]["status"] == "ELEGIVEL"


def test_matriz_de_mercado_bloqueia_ue_por_regra_governada_de_embargo_ambiental(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)
    animal = _criar_animais(ambiente, operador, 1)[0]
    _adotar_regra_de_carencia_para_mercados(
        operador,
        ambiente,
        (MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA,),
    )
    _registrar_assertion_embargo_ambiental(
        ambiente,
        status=EnvironmentalEmbargoAssertionStatus.COM_RESTRICAO,
    )

    resposta = operador.post(
        f"/v1/livestock/animals/{animal}/eligibility/market-matrix",
        json={},
        headers=cabecalho,
    )

    assert resposta.status_code == 201, resposta.text
    europa = {item["market"]: item for item in resposta.json()["markets"]}[
        "exportacao-uniao-europeia"
    ]
    assert europa["status"] == "NAO_ELEGIVEL"
    assert europa["requirements"][2]["rule_code"] == "rule-embargo-ambiental-ibama"
    assert europa["requirements"][2]["status"] == "NAO_ELEGIVEL"
    assert europa["requirements"][2]["rule_version"]["code"] == "rule-embargo-ambiental-ibama"
    assert europa["requirements"][2]["adoption"]["purpose"] == "exportacao-uniao-europeia"
    assert europa["requirements"][2]["reasons"][0]["rule_code"] == "rule-embargo-ambiental-ibama"


def test_matriz_de_mercado_mostra_sujeito_escolhido_e_falha_fechado_sem_avaliador(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    cabecalho = _cabecalho(ambiente)
    animal = _criar_animais(ambiente, operador, 1)[0]
    slaughterhouse_id = _criar_contraparte_externa(
        operador,
        ambiente,
        name="Frigorifico Escolhido",
        counterparty_type="SLAUGHTERHOUSE",
    )
    _adotar_regra_de_carencia_para_mercados(
        operador,
        ambiente,
        (
            MarketEligibilityPurpose.EXPORTACAO_CHINA,
            MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS,
        ),
    )
    _registrar_qualificacao_de_estabelecimento(
        operador,
        ambiente,
        counterparty_id=slaughterhouse_id,
        market_purpose=MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
    )

    resposta = operador.post(
        f"/v1/livestock/animals/{animal}/eligibility/market-matrix",
        json={"slaughterhouse_counterparty_id": slaughterhouse_id},
        headers=cabecalho,
    )

    assert resposta.status_code == 201, resposta.text
    china = {item["market"]: item for item in resposta.json()["markets"]}["exportacao-china"]
    assert china["status"] == "ELEGIVEL"
    assert china["dependency"] == {
        "subject_key": "slaughterhouse",
        "subject_label": "estabelecimento",
        "selected_subject_id": slaughterhouse_id,
    }
    assert china["gaps"] == []
    assert china["requirements"][0]["status"] == "ELEGIVEL"
    assert china["requirements"][1]["rule_code"] == "rule-habilitacao-estabelecimento"
    assert china["requirements"][1]["status"] == "ELEGIVEL"
    assert china["requirements"][1]["dependency"] == {
        "subject_key": "slaughterhouse",
        "subject_label": "estabelecimento",
        "selected_subject_id": slaughterhouse_id,
    }
    assert china["requirements"][1]["gaps"] == []


def test_listar_dossies_sem_sujeito_e_recusado(
    ambiente: Ambiente, auditor: ClienteAutenticado
) -> None:
    """Devolver toda a prova da organização de uma vez não é pergunta que se faça."""
    resposta = auditor.get("/v1/livestock/dossiers", headers=_cabecalho(ambiente))

    assert resposta.status_code == 422
