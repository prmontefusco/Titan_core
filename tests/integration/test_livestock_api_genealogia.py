"""Genealogia pela API (Passo 13.2).

O que estes testes provam contra o PostgreSQL real: a maternidade grava dois
vínculos mesmo quando a doadora também gestou, a árvore sobe pela linhagem
genética e ignora a receptora, e o parto entra na linha do tempo da matriz.
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


def _registrar_maternidade(
    ambiente: Ambiente,
    cliente: ClienteAutenticado,
    cria: str,
    doadora: str,
    receptora: str | None = None,
) -> object:
    corpo: dict[str, object] = {
        "genetic_mother_id": doadora,
        "occurred_at": ONTEM,
        "confidence": "DECLARADO",
    }
    if receptora is not None:
        corpo["gestational_mother_id"] = receptora
    return cliente.post(
        f"/v1/livestock/animals/{cria}/maternity", json=corpo, headers=_cabecalho(ambiente)
    )


def test_a_maternidade_grava_os_dois_vinculos(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    bezerro = _criar_animal(ambiente, operador, "MALE")
    vaca = _criar_animal(ambiente, operador, "FEMALE")

    resposta = _registrar_maternidade(ambiente, operador, bezerro, vaca)

    assert resposta.status_code == 201, resposta.text  # type: ignore[attr-defined]
    papeis = {item["role"] for item in resposta.json()}  # type: ignore[attr-defined]
    assert papeis == {"MAE_GENETICA", "MAE_GESTACIONAL"}


def test_a_arvore_sobe_pela_doadora_e_ignora_a_receptora(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    bezerro = _criar_animal(ambiente, operador, "MALE")
    doadora = _criar_animal(ambiente, operador, "FEMALE")
    receptora = _criar_animal(ambiente, operador, "FEMALE")
    _registrar_maternidade(ambiente, operador, bezerro, doadora, receptora)

    arvore = operador.get(f"/v1/livestock/animals/{bezerro}/ancestry", headers=_cabecalho(ambiente))

    assert arvore.status_code == 200, arvore.text
    ascendentes = {ramo["link"]["parent_id"] for ramo in arvore.json()["parents"]}
    assert ascendentes == {doadora}


def test_a_receptora_responde_pelo_historico_reprodutivo(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Quem gestou não transmitiu genes: são duas perguntas e duas rotas."""
    bezerro = _criar_animal(ambiente, operador, "MALE")
    doadora = _criar_animal(ambiente, operador, "FEMALE")
    receptora = _criar_animal(ambiente, operador, "FEMALE")
    _registrar_maternidade(ambiente, operador, bezerro, doadora, receptora)

    gestadas = operador.get(
        f"/v1/livestock/animals/{receptora}/reproduction", headers=_cabecalho(ambiente)
    )
    crias = operador.get(
        f"/v1/livestock/animals/{receptora}/descendants", headers=_cabecalho(ambiente)
    )

    assert [item["offspring_id"] for item in gestadas.json()] == [bezerro]
    assert crias.json() == []


def test_o_touro_do_lote_admite_varios_pais_declarados(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    bezerro = _criar_animal(ambiente, operador, "MALE")
    touros = [_criar_animal(ambiente, operador, "MALE") for _ in range(3)]

    for touro in touros:
        resposta = operador.post(
            f"/v1/livestock/animals/{bezerro}/paternity",
            json={"father_id": touro, "occurred_at": ONTEM, "confidence": "DECLARADO"},
            headers=_cabecalho(ambiente),
        )
        assert resposta.status_code == 201, resposta.text

    arvore = operador.get(f"/v1/livestock/animals/{bezerro}/ancestry", headers=_cabecalho(ambiente))
    assert {ramo["link"]["parent_id"] for ramo in arvore.json()["parents"]} == set(touros)


def test_a_segunda_mae_genetica_e_recusada(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    bezerro = _criar_animal(ambiente, operador, "MALE")
    vaca = _criar_animal(ambiente, operador, "FEMALE")
    outra = _criar_animal(ambiente, operador, "FEMALE")
    _registrar_maternidade(ambiente, operador, bezerro, vaca)

    repetida = _registrar_maternidade(ambiente, operador, bezerro, outra)

    assert repetida.status_code == 409, repetida.text  # type: ignore[attr-defined]
    assert repetida.json()["reason_code"] == "CONFLITO_DE_DOMINIO"  # type: ignore[attr-defined]


def test_o_sexo_do_progenitor_precisa_caber_no_papel(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    bezerro = _criar_animal(ambiente, operador, "MALE")
    touro = _criar_animal(ambiente, operador, "MALE")

    recusada = _registrar_maternidade(ambiente, operador, bezerro, touro)

    assert recusada.status_code == 409, recusada.text  # type: ignore[attr-defined]


def test_o_parto_entra_na_linha_do_tempo_da_matriz(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    """É a pergunta que o responsável fez: a vaca precisa ver o parto na vida dela."""
    bezerro = _criar_animal(ambiente, operador, "MALE")
    vaca = _criar_animal(ambiente, operador, "FEMALE")
    _registrar_maternidade(ambiente, operador, bezerro, vaca)

    historia = auditor.get(f"/v1/livestock/animals/{vaca}/timeline", headers=_cabecalho(ambiente))

    assert historia.status_code == 200, historia.text
    tipos = [entrada["entry_type"] for entrada in historia.json()["entries"]]
    assert "livestock.parentage_registered" in tipos


def test_animal_inexistente_responde_404(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    vaca = _criar_animal(ambiente, operador, "FEMALE")

    resposta = _registrar_maternidade(
        ambiente, operador, "00000000-0000-4000-8000-000000000000", vaca
    )

    assert resposta.status_code == 404, resposta.text  # type: ignore[attr-defined]


def test_auditor_nao_registra_genealogia(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    """Declarar linhagem é escrita, e é ela que dá valor comercial ao registro."""
    bezerro = _criar_animal(ambiente, operador, "MALE")
    vaca = _criar_animal(ambiente, operador, "FEMALE")

    negada = _registrar_maternidade(ambiente, auditor, bezerro, vaca)

    assert negada.status_code == 403, negada.text  # type: ignore[attr-defined]


def test_auditor_le_a_genealogia(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    bezerro = _criar_animal(ambiente, operador, "MALE")

    arvore = auditor.get(f"/v1/livestock/animals/{bezerro}/ancestry", headers=_cabecalho(ambiente))

    assert arvore.status_code == 200, arvore.text
