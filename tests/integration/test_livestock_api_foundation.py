"""Prova ponta a ponta da fundação HTTP da vertical (Passo 10.4a).

A travessia exercitada aqui, do socket ao banco:

    HTTP → OIDC → AuthenticatedPrincipal → OrganizationContext → Permission
         → Application Service → transação → contexto RLS → repositório → PostgreSQL

O endpoint-prova é `POST /v1/livestock/animals`, simples o bastante para não
misturar motor de regras, avaliação, decisão e dossiê na prova do encanamento.
O ambiente e o cliente vêm de `tests/livestock_api_support.py`.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from tests.livestock_api_support import DATABASE_URL, Ambiente, _cliente

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)


def _corpo(ambiente: Ambiente) -> dict[str, object]:
    return {
        "birth_property_id": str(ambiente.property_id.value),
        "sex": "MALE",
        "breed": "Nelore",
    }


def test_operador_autorizado_cria_o_animal(ambiente: Ambiente) -> None:
    cliente = _cliente(ambiente, ambiente.operador)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json=_corpo(ambiente),
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["organization_id"] == str(ambiente.org_a.organization_id.value)
    assert corpo["animal_id"]


def test_sem_token_a_resposta_e_401(ambiente: Ambiente) -> None:
    """401 diz 'não sei quem você é' — e precisa dizer isso no corpo.

    Um `reason_code` genérico obrigaria o cliente a adivinhar se falta credencial
    ou se houve outra falha qualquer. Foi o que a validação manual encontrou: o
    handler genérico devolvia `ERRO_HTTP`.
    """
    cliente = _cliente(ambiente, None)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json=_corpo(ambiente),
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 401
    corpo = resposta.json()
    assert corpo["reason_code"] == "NAO_AUTENTICADO"
    # Mensagem própria e em português: o esquema OAuth2 do FastAPI responde antes
    # da nossa dependência, e o texto dele destoaria do resto da API.
    assert corpo["detail"] == "Access Token ausente, inválido ou expirado."
    assert resposta.headers["www-authenticate"] == "Bearer"
    assert resposta.headers["content-type"].startswith("application/problem+json")


def test_sem_a_permissao_exigida_a_resposta_e_403(ambiente: Ambiente) -> None:
    """403 diz 'sei quem você é, e você não pode' — o auditor não escreve."""
    cliente = _cliente(ambiente, ambiente.auditor)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json=_corpo(ambiente),
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"
    assert resposta.headers["content-type"].startswith("application/problem+json")


def test_organizacao_sem_vinculo_e_negada(ambiente: Ambiente) -> None:
    """O operador da Org A não opera na Org B, e a negação não revela o porquê."""
    cliente = _cliente(ambiente, ambiente.operador)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json=_corpo(ambiente),
        headers={ORGANIZATION_HEADER: str(ambiente.org_b.organization_id.value)},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "CONTEXTO_ORGANIZACIONAL_NEGADO"


def test_cabecalho_de_organizacao_ausente_e_recusado(ambiente: Ambiente) -> None:
    cliente = _cliente(ambiente, ambiente.operador)

    resposta = cliente.post("/v1/livestock/animals", json=_corpo(ambiente))

    assert resposta.status_code == 400
    assert resposta.json()["reason_code"] == "ORGANIZACAO_NAO_INFORMADA"


def test_entrada_invalida_devolve_422_em_problem_json(ambiente: Ambiente) -> None:
    cliente = _cliente(ambiente, ambiente.operador)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json={"birth_property_id": str(ambiente.property_id.value), "sex": "INEXISTENTE"},
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 422
    corpo = resposta.json()
    assert corpo["reason_code"] == "ENTRADA_INVALIDA"
    assert corpo["errors"]


def test_conflito_de_dominio_devolve_409(ambiente: Ambiente) -> None:
    """Identificador oficial repetido é recusa do domínio, não erro do servidor."""
    cliente = _cliente(ambiente, ambiente.operador)
    corpo = _corpo(ambiente) | {
        "initial_identifier_type": "OFFICIAL_SISBOV",
        "initial_identifier_value": f"BR{uuid4().hex[:10]}",
    }
    cabecalho = {ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)}

    assert cliente.post("/v1/livestock/animals", json=corpo, headers=cabecalho).status_code == 201
    repetido = cliente.post("/v1/livestock/animals", json=corpo, headers=cabecalho)

    assert repetido.status_code == 409
    assert repetido.json()["reason_code"] == "CONFLITO_DE_DOMINIO"


def test_o_animal_criado_nasce_com_o_evento_no_log_do_core(ambiente: Ambiente) -> None:
    """Registro e prova nascem juntos: a transação cobre os dois."""
    cliente = _cliente(ambiente, ambiente.operador)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json=_corpo(ambiente),
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )
    animal_id = resposta.json()["animal_id"]

    eventos = (
        ambiente.connection.execute(
            text(
                "SELECT event_type FROM core_audit.domain_events "
                "WHERE aggregate_id = :id ORDER BY aggregate_version"
            ),
            {"id": animal_id},
        )
        .scalars()
        .all()
    )

    assert eventos == ["livestock.animal_registered"]
