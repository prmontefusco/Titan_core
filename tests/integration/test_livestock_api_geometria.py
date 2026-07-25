"""Geometria da propriedade pela API (Passo 17.1, ADR-0026).

O que estes testes provam: o limite entra com proveniência, nunca é substituído,
geometria inválida é recusada com o motivo, e ler o cadastro da propriedade não
dá acesso ao polígono dela.
"""

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import pytest

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from tests.livestock_api_support import DATABASE_URL, Ambiente, ClienteAutenticado, _cliente

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)

QUADRADO = {
    "type": "Polygon",
    "coordinates": [
        [[-47.9, -15.8], [-47.8, -15.8], [-47.8, -15.7], [-47.9, -15.7], [-47.9, -15.8]]
    ],
}

MAIOR = {
    "type": "Polygon",
    "coordinates": [
        [[-47.95, -15.85], [-47.75, -15.85], [-47.75, -15.65], [-47.95, -15.65], [-47.95, -15.85]]
    ],
}

# Os lados se cruzam: sintaticamente perfeita, topologicamente inválida.
AMPULHETA = {
    "type": "Polygon",
    "coordinates": [
        [[-47.9, -15.8], [-47.8, -15.7], [-47.8, -15.8], [-47.9, -15.7], [-47.9, -15.8]]
    ],
}


@pytest.fixture
def operador(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.operador)


@pytest.fixture
def auditor(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.auditor)


def _cabecalho(ambiente: Ambiente) -> dict[str, str]:
    return {ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)}


def _propriedade(ambiente: Ambiente, operador: ClienteAutenticado) -> str:
    resposta = operador.post(
        "/v1/livestock/properties",
        json={
            "code": f"GEO-{datetime.now(UTC).timestamp()}",
            "name": "Fazenda com limite",
            "municipality": "Brasilia",
            "state_code": "DF",
        },
        headers=_cabecalho(ambiente),
    )
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["property_id"])


def _registrar(
    ambiente: Ambiente,
    cliente: ClienteAutenticado,
    property_id: str,
    geojson: Mapping[str, object] = QUADRADO,
    **extra: object,
) -> object:
    corpo: dict[str, object] = {"source": "DECLARADA", "geojson": geojson, **extra}
    return cliente.post(
        f"/v1/livestock/properties/{property_id}/geometry",
        json=corpo,
        headers=_cabecalho(ambiente),
    )


def test_a_geometria_entra_com_proveniencia(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)

    resposta = _registrar(ambiente, operador, property_id)

    assert resposta.status_code == 201, resposta.text  # type: ignore[attr-defined]
    corpo = resposta.json()  # type: ignore[attr-defined]
    assert corpo["version"] == 1
    assert corpo["srid"] == 4326
    assert len(corpo["source_digest"]) == 64


def test_a_geometria_invalida_e_recusada_com_o_motivo(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)

    recusada = _registrar(ambiente, operador, property_id, geojson=AMPULHETA)

    assert recusada.status_code == 409, recusada.text  # type: ignore[attr-defined]
    detalhe = recusada.json()["detail"]  # type: ignore[attr-defined]
    assert "ntersection" in detalhe
    assert "reparada" in detalhe


def test_ponto_nao_e_limite_de_propriedade(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)

    recusado = _registrar(
        ambiente, operador, property_id, geojson={"type": "Point", "coordinates": [-47.9, -15.8]}
    )

    assert recusado.status_code == 409, recusado.text  # type: ignore[attr-defined]


def test_registrar_de_novo_cria_versao_nova_e_preserva_a_anterior(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """É a versão antiga que faz uma avaliação passada continuar reproduzível."""
    property_id = _propriedade(ambiente, operador)
    _registrar(ambiente, operador, property_id)

    segunda = _registrar(ambiente, operador, property_id, geojson=MAIOR)

    assert segunda.json()["version"] == 2  # type: ignore[attr-defined]
    historico = operador.get(
        f"/v1/livestock/properties/{property_id}/geometry/history", headers=_cabecalho(ambiente)
    )
    versoes = historico.json()
    assert [item["version"] for item in versoes] == [1, 2]
    # A primeira continua inteira, com o polígono original.
    assert versoes[0]["geojson"]["coordinates"] == QUADRADO["coordinates"]


def test_a_vigente_e_a_ultima_registrada(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    property_id = _propriedade(ambiente, operador)
    _registrar(ambiente, operador, property_id)
    _registrar(ambiente, operador, property_id, geojson=MAIOR)

    vigente = operador.get(
        f"/v1/livestock/properties/{property_id}/geometry", headers=_cabecalho(ambiente)
    )

    assert vigente.json()["version"] == 2
    assert vigente.json()["geojson"]["coordinates"] == MAIOR["coordinates"]


def test_propriedade_sem_geometria_responde_nulo(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Lacuna declarada, e não erro: a propriedade continua operando sem limite."""
    property_id = _propriedade(ambiente, operador)

    vigente = operador.get(
        f"/v1/livestock/properties/{property_id}/geometry", headers=_cabecalho(ambiente)
    )

    assert vigente.status_code == 200
    assert vigente.json() is None


def test_o_geojson_devolvido_e_o_material_sobre_o_qual_o_digest_foi_calculado(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Devolver outra serialização quebraria a conferência do digest."""
    import hashlib

    property_id = _propriedade(ambiente, operador)
    registro = _registrar(ambiente, operador, property_id)
    digest = registro.json()["source_digest"]  # type: ignore[attr-defined]

    lido = operador.get(
        f"/v1/livestock/properties/{property_id}/geometry", headers=_cabecalho(ambiente)
    ).json()

    recalculado = hashlib.sha256(
        json.dumps(lido["geojson"], separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert recalculado == digest


def test_captura_no_futuro_e_recusada(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    property_id = _propriedade(ambiente, operador)

    recusada = _registrar(
        ambiente,
        operador,
        property_id,
        captured_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
    )

    assert recusada.status_code == 409, recusada.text  # type: ignore[attr-defined]


def test_geometria_do_sicar_exige_referencia_externa(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)

    recusada = _registrar(ambiente, operador, property_id, source="SICAR_CAR")

    assert recusada.status_code == 409, recusada.text  # type: ignore[attr-defined]

    aceita = _registrar(
        ambiente,
        operador,
        property_id,
        source="SICAR_CAR",
        external_reference="DF-5300108-ABC123",
    )
    assert aceita.status_code == 201, aceita.text  # type: ignore[attr-defined]


def test_propriedade_inexistente_responde_404(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    resposta = _registrar(ambiente, operador, "00000000-0000-4000-8000-000000000000")

    assert resposta.status_code == 404, resposta.text  # type: ignore[attr-defined]


def test_auditor_nao_registra_geometria(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)

    negada = _registrar(ambiente, auditor, property_id)

    assert negada.status_code == 403, negada.text  # type: ignore[attr-defined]


def test_auditor_le_a_geometria(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)
    _registrar(ambiente, operador, property_id)

    lida = auditor.get(
        f"/v1/livestock/properties/{property_id}/geometry", headers=_cabecalho(ambiente)
    )

    assert lida.status_code == 200, lida.text
    assert lida.json()["version"] == 1
