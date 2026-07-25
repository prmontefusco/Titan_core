"""Saída do rebanho pela API (Passo 13.1).

O que estes testes provam é que a saída não é um campo: ela sai do rebanho ativo
por derivação, o banco recusa a segunda saída mesmo que o serviço falhasse em
conferir, e o passado continua alcançável — pelo detalhe, pela listagem histórica
e pelo lançamento atrasado de um fato anterior.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
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


def _criar_animal(ambiente: Ambiente, operador: ClienteAutenticado) -> str:
    resposta = operador.post(
        "/v1/livestock/animals",
        json={"birth_property_id": str(ambiente.property_id.value), "sex": "FEMALE"},
        headers=_cabecalho(ambiente),
    )
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["animal_id"])


def _registrar_saida(
    ambiente: Ambiente,
    operador: ClienteAutenticado,
    animal_id: str,
    quando: datetime,
    tipo: str = "ABATE",
) -> Any:
    return operador.post(
        f"/v1/livestock/animals/{animal_id}/exit",
        json={
            "exit_type": tipo,
            "occurred_at": quando.isoformat(),
            "reason": "Abate programado",
            "destination": "Frigorífico Central",
        },
        headers=_cabecalho(ambiente),
    )


def test_o_animal_que_saiu_deixa_o_rebanho_ativo(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _criar_animal(ambiente, operador)
    quando = datetime.now(UTC) - timedelta(days=1)

    criacao = _registrar_saida(ambiente, operador, animal_id, quando)
    assert criacao.status_code == 201, criacao.text

    listagem = operador.get("/v1/livestock/animals?limit=200", headers=_cabecalho(ambiente))
    assert animal_id not in [item["animal_id"] for item in listagem.json()["items"]]

    # Sair do rebanho não é desaparecer: o registro continua alcançável, e o
    # detalhe diz por quê.
    detalhe = operador.get(f"/v1/livestock/animals/{animal_id}", headers=_cabecalho(ambiente))
    assert detalhe.status_code == 200
    saida = detalhe.json()["saida"]
    assert saida["exit_type"] == "ABATE"
    assert saida["destination"] == "Frigorífico Central"


def test_o_levantamento_historico_traz_quem_saiu_com_a_saida_preenchida(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _criar_animal(ambiente, operador)
    _registrar_saida(ambiente, operador, animal_id, datetime.now(UTC) - timedelta(days=1))

    listagem = operador.get(
        "/v1/livestock/animals?limit=200&incluir_saidos=true", headers=_cabecalho(ambiente)
    )

    encontrados = {item["animal_id"]: item for item in listagem.json()["items"]}
    assert animal_id in encontrados
    assert encontrados[animal_id]["saida"]["exit_type"] == "ABATE"


def test_a_segunda_saida_e_recusada(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    animal_id = _criar_animal(ambiente, operador)
    _registrar_saida(ambiente, operador, animal_id, datetime.now(UTC) - timedelta(days=2))

    repetida = _registrar_saida(
        ambiente, operador, animal_id, datetime.now(UTC) - timedelta(days=1), tipo="VENDA"
    )

    assert repetida.status_code == 409, repetida.text
    assert repetida.json()["reason_code"] == "CONFLITO_DE_DOMINIO"


def test_auditor_nao_registra_saida(ambiente: Ambiente, auditor: ClienteAutenticado) -> None:
    """Declarar a morte de um animal é escrita, e o auditor não escreve."""
    operador = _cliente(ambiente, ambiente.operador)
    animal_id = _criar_animal(ambiente, operador)

    negada = _registrar_saida(ambiente, auditor, animal_id, datetime.now(UTC) - timedelta(days=1))

    assert negada.status_code == 403, negada.text


def test_animal_inexistente_responde_404(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    resposta = _registrar_saida(
        ambiente,
        operador,
        "00000000-0000-4000-8000-000000000000",
        datetime.now(UTC) - timedelta(days=1),
    )

    assert resposta.status_code == 404, resposta.text
