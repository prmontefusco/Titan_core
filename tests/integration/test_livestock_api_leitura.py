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
    policy = PolicyService(TransactionalPolicyRepository(ambiente.connection)).create_draft(
        organization_id=ambiente.org_a.organization_id,
        code=f"politica-mercado-{uuid4().hex[:8]}",
        name="Politica de elegibilidade por mercado",
        description="Policy ficticia para validar matriz comercial.",
    )
    return str(policy.policy_id.value)


def _adotar_regra_de_carencia_para_mercados(
    operador: ClienteAutenticado,
    ambiente: Ambiente,
    mercados: tuple[str, ...],
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
            "required_evidence_types": ["livestock.treatment_applied"],
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
                "purpose": mercado,
                "scope": ELIGIBILITY_RULE_ADOPTION_SCOPE,
                "reason": f"Regra adotada para {mercado}.",
            },
            headers=cabecalho,
        )
        assert adoption.status_code == 201, adoption.text


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
        ("exportacao-china", "exportacao-estados-unidos"),
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
    assert por_mercado["exportacao-china"]["status"] == "ELEGIVEL"
    assert por_mercado["exportacao-estados-unidos"]["status"] == "ELEGIVEL"
    assert por_mercado["exportacao-uniao-europeia"]["status"] == "AUSENTE"
    assert por_mercado["exportacao-uniao-europeia"]["governed_rule"] is None
    assert por_mercado["exportacao-uniao-europeia"]["reasons"] == []
    assert por_mercado["exportacao-uniao-europeia"]["gaps"][0]["code"] == (
        "REGRA_GOVERNADA_AUSENTE"
    )
    assert por_mercado["exportacao-china"]["governed_rule"]["purpose"] == "exportacao-china"
    assert por_mercado["exportacao-china"]["gaps"] == []
    assert por_mercado["exportacao-china"]["reasons"][0]["code"] == "regra_atendida"
    assert (
        por_mercado["exportacao-china"]["reasons"][0]["rule_code"] == "rule-carencia-farmacologica"
    )
    assert por_mercado["exportacao-china"]["requirements"][0]["rule_code"] == (
        "rule-carencia-farmacologica"
    )
    assert por_mercado["exportacao-china"]["requirements"][0]["status"] == "ELEGIVEL"
    assert por_mercado["exportacao-uniao-europeia"]["requirements"][0]["status"] == "AUSENTE"


def test_listar_dossies_sem_sujeito_e_recusado(
    ambiente: Ambiente, auditor: ClienteAutenticado
) -> None:
    """Devolver toda a prova da organização de uma vez não é pergunta que se faça."""
    resposta = auditor.get("/v1/livestock/dossiers", headers=_cabecalho(ambiente))

    assert resposta.status_code == 422
