"""Reprodução pela API (Passo 13.3, ADR-0040).

O que estes testes provam contra o PostgreSQL real: o parto cria as crias e a
linhagem numa transação só, o natimorto é rastreável mas fica fora do rebanho
ativo sem registro de saída, o gemelar é um evento com duas crias, e o aborto
encerra a gestação sem criar animal nenhum.
"""

from datetime import UTC, datetime, timedelta

import pytest

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from tests.livestock_api_support import DATABASE_URL, Ambiente, ClienteAutenticado, _cliente

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)

ONTEM = (datetime.now(UTC) - timedelta(days=1)).isoformat()


@pytest.fixture
def operador(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.operador)


@pytest.fixture
def auditor(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.auditor)


def _cabecalho(ambiente: Ambiente) -> dict[str, str]:
    return {ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)}


def _criar_animal(ambiente: Ambiente, operador: ClienteAutenticado, sexo: str) -> str:
    resposta = operador.post(
        "/v1/livestock/animals",
        json={"birth_property_id": str(ambiente.property_id.value), "sex": sexo},
        headers=_cabecalho(ambiente),
    )
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["animal_id"])


def _parir(
    ambiente: Ambiente,
    cliente: ClienteAutenticado,
    mae: str,
    crias: list[dict[str, str]],
    **extra: object,
) -> object:
    corpo: dict[str, object] = {"dam_id": mae, "occurred_at": ONTEM, "offspring": crias, **extra}
    return cliente.post(
        "/v1/livestock/reproductive-events/parturitions",
        json=corpo,
        headers=_cabecalho(ambiente),
    )


def test_o_parto_cria_a_cria_com_a_linhagem_pronta(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    vaca = _criar_animal(ambiente, operador, "FEMALE")

    resposta = _parir(ambiente, operador, vaca, [{"outcome": "NASCIDO_VIVO", "sex": "MALE"}])

    assert resposta.status_code == 201, resposta.text  # type: ignore[attr-defined]
    bezerro = resposta.json()["offspring"][0]["animal_id"]  # type: ignore[attr-defined]
    arvore = operador.get(f"/v1/livestock/animals/{bezerro}/ancestry", headers=_cabecalho(ambiente))
    assert {ramo["link"]["parent_id"] for ramo in arvore.json()["parents"]} == {vaca}


def test_o_gemelar_e_um_evento_com_duas_crias(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    vaca = _criar_animal(ambiente, operador, "FEMALE")

    resposta = _parir(
        ambiente,
        operador,
        vaca,
        [{"outcome": "NASCIDO_VIVO", "sex": "MALE"}, {"outcome": "NATIMORTO", "sex": "FEMALE"}],
    )

    corpo = resposta.json()  # type: ignore[attr-defined]
    assert len(corpo["offspring"]) == 2
    assert {cria["outcome"] for cria in corpo["offspring"]} == {"NASCIDO_VIVO", "NATIMORTO"}


def test_o_natimorto_fica_fora_do_rebanho_ativo_e_sem_saida(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Rastreável pela genealogia, ausente do rebanho — e sem registro de morte."""
    vaca = _criar_animal(ambiente, operador, "FEMALE")
    resposta = _parir(ambiente, operador, vaca, [{"outcome": "NATIMORTO", "sex": "MALE"}])
    natimorto = resposta.json()["offspring"][0]["animal_id"]  # type: ignore[attr-defined]

    listagem = operador.get("/v1/livestock/animals?limit=200", headers=_cabecalho(ambiente))
    detalhe = operador.get(f"/v1/livestock/animals/{natimorto}", headers=_cabecalho(ambiente))

    assert natimorto not in [item["animal_id"] for item in listagem.json()["items"]]
    assert detalhe.status_code == 200
    # Não houve saída: ele nunca entrou no rebanho ativo.
    assert detalhe.json()["saida"] is None


def test_o_natimorto_nao_aceita_tratamento(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    vaca = _criar_animal(ambiente, operador, "FEMALE")
    resposta = _parir(ambiente, operador, vaca, [{"outcome": "NATIMORTO", "sex": "MALE"}])
    natimorto = resposta.json()["offspring"][0]["animal_id"]  # type: ignore[attr-defined]

    medicamento = operador.post(
        "/v1/livestock/medications",
        json={
            "trade_name": "Ivomec",
            "active_ingredient": "Ivermectina",
            "manufacturer": "X",
            "withdrawal_period_days": 30,
        },
        headers=_cabecalho(ambiente),
    )
    lote = operador.post(
        "/v1/livestock/medication-batches",
        json={
            "medication_id": medicamento.json()["medication_id"],
            "batch_number": "L-13-3",
            "expiry_date": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
        },
        headers=_cabecalho(ambiente),
    )

    recusado = operador.post(
        "/v1/livestock/treatments",
        json={
            "animal_id": natimorto,
            "medication_batch_id": lote.json()["batch_id"],
            "applied_at": ONTEM,
            "dose": "1 mL",
        },
        headers=_cabecalho(ambiente),
    )

    assert recusado.status_code == 409, recusado.text


def test_o_aborto_nao_cria_animal(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    vaca = _criar_animal(ambiente, operador, "FEMALE")
    antes = len(
        operador.get("/v1/livestock/animals?limit=200", headers=_cabecalho(ambiente)).json()[
            "items"
        ]
    )

    resposta = operador.post(
        "/v1/livestock/reproductive-events/pregnancy-losses",
        json={
            "dam_id": vaca,
            "occurred_at": ONTEM,
            "gestational_age_days": 170,
            "gestational_age_basis": "ESTIMATED",
        },
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["offspring"] == []
    depois = len(
        operador.get("/v1/livestock/animals?limit=200", headers=_cabecalho(ambiente)).json()[
            "items"
        ]
    )
    assert depois == antes


def test_idade_gestacional_sem_base_e_recusada(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    vaca = _criar_animal(ambiente, operador, "FEMALE")

    recusado = operador.post(
        "/v1/livestock/reproductive-events/pregnancy-losses",
        json={"dam_id": vaca, "occurred_at": ONTEM, "gestational_age_days": 170},
        headers=_cabecalho(ambiente),
    )

    assert recusado.status_code == 409, recusado.text


def test_a_propriedade_de_nascimento_declarada_viaja_com_a_procedencia(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    vaca = _criar_animal(ambiente, operador, "FEMALE")

    resposta = _parir(
        ambiente,
        operador,
        vaca,
        [{"outcome": "NASCIDO_VIVO", "sex": "MALE"}],
        birth_property_id=str(ambiente.property_id.value),
    )

    cria = resposta.json()["offspring"][0]  # type: ignore[attr-defined]
    assert cria["birth_property_id"] == str(ambiente.property_id.value)
    assert cria["birth_property_source"] in {"DECLARED", "DERIVED_FROM_MATERNAL_STAY"}


def test_quem_pare_e_femea(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    touro = _criar_animal(ambiente, operador, "MALE")

    recusado = _parir(ambiente, operador, touro, [{"outcome": "NASCIDO_VIVO", "sex": "MALE"}])

    assert recusado.status_code == 409, recusado.text  # type: ignore[attr-defined]


def test_o_historico_reprodutivo_da_matriz(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    vaca = _criar_animal(ambiente, operador, "FEMALE")
    _parir(ambiente, operador, vaca, [{"outcome": "NASCIDO_VIVO", "sex": "MALE"}])

    historia = auditor.get(
        f"/v1/livestock/animals/{vaca}/reproductive-events", headers=_cabecalho(ambiente)
    )

    assert historia.status_code == 200, historia.text
    assert [evento["event_type"] for evento in historia.json()] == ["PARTO"]


def test_a_origem_do_animal_e_o_parto(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    vaca = _criar_animal(ambiente, operador, "FEMALE")
    parto = _parir(ambiente, operador, vaca, [{"outcome": "NASCIDO_VIVO", "sex": "MALE"}])
    bezerro = parto.json()["offspring"][0]["animal_id"]  # type: ignore[attr-defined]

    origem = auditor.get(f"/v1/livestock/animals/{bezerro}/origin", headers=_cabecalho(ambiente))

    assert origem.status_code == 200, origem.text
    assert origem.json()["event_id"] == parto.json()["event_id"]  # type: ignore[attr-defined]


def test_o_rebanho_legado_nao_tem_origem(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    """`null` é resposta honesta: ninguém registrou o parto dele."""
    animal = _criar_animal(ambiente, operador, "FEMALE")

    origem = auditor.get(f"/v1/livestock/animals/{animal}/origin", headers=_cabecalho(ambiente))

    assert origem.status_code == 200
    assert origem.json() is None


def test_auditor_nao_registra_parto(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    vaca = _criar_animal(ambiente, operador, "FEMALE")

    negado = _parir(ambiente, auditor, vaca, [{"outcome": "NASCIDO_VIVO", "sex": "MALE"}])

    assert negado.status_code == 403, negado.text  # type: ignore[attr-defined]
