"""API controlada de captura territorial sintética (T-05D Corte 4)."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from packages.core_infrastructure.persistence import set_local_organization_context
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


@pytest.fixture
def operador(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.operador)


def _cabecalho(ambiente: Ambiente) -> dict[str, str]:
    return {ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)}


def _propriedade(ambiente: Ambiente, operador: ClienteAutenticado) -> str:
    resposta = operador.post(
        "/v1/livestock/properties",
        json={
            "code": f"TERR-CAP-{uuid4().hex[:10]}",
            "name": "Fazenda Captura Territorial",
            "municipality": "Cuiaba",
            "state_code": "MT",
        },
        headers=_cabecalho(ambiente),
    )
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["property_id"])


def _geometria(
    ambiente: Ambiente, operador: ClienteAutenticado, property_id: str
) -> dict[str, object]:
    resposta = operador.post(
        f"/v1/livestock/properties/{property_id}/geometry",
        json={"source": "DECLARADA", "geojson": QUADRADO},
        headers=_cabecalho(ambiente),
    )
    assert resposta.status_code == 201, resposta.text
    return dict(resposta.json())


def _funai_payload(
    geometry: dict[str, object], *, versions: list[str] | None = None
) -> dict[str, object]:
    return {
        "geometry_id": geometry["geometry_id"],
        "geometry_version": geometry["version"],
        "profile": "FUNAI_LIKE_OVERLAP",
        "request_scope": {
            "geometry_id": geometry["geometry_id"],
            "geometry_version": geometry["version"],
            "layer": "FUNAI_LIKE",
            "operation": "OVERLAP",
        },
        "response_payload": {
            "feature_count": 1,
            "property_area_hectares": 1000.0,
            "overlap_area_hectares": 42.0,
            **({} if versions is None else {"source_version_ids": versions}),
        },
        "captured_at": "2026-03-01T00:00:00Z",
        "known_at": "2026-03-02T00:00:00Z",
        "source_valid_from": None,
        "source_valid_to": None,
        "limitations": [],
    }


def test_registrar_e_listar_captura_territorial_sintetica(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)
    geometry = _geometria(ambiente, operador, property_id)

    resposta = operador.post(
        f"/v1/livestock/properties/{property_id}/territorial-captures/synthetic",
        json=_funai_payload(geometry, versions=["FUNAI_TEST_2026_V1"]),
        headers=_cabecalho(ambiente),
    )
    assert resposta.status_code == 201, resposta.text
    body = resposta.json()
    assert body["source_profile_code"] == "TERRITORIAL_TEST_SOURCE"
    assert body["source_environment"] == "SYNTHETIC"
    assert body["source_layer"] == "TERRITORIAL_TEST_OVERLAP"
    assert body["operation"] == "OVERLAP"
    assert body["source_version_ids"] == ["FUNAI_TEST_2026_V1"]
    assert body["response_summary"]["profile"] == "FUNAI_LIKE_OVERLAP"
    assert "response_payload" not in body
    assert "NO_EXTERNAL_RECOGNITION_ASSERTED" in body["limitations"]

    listagem = operador.get(
        f"/v1/livestock/properties/{property_id}/territorial-captures?limit=50&offset=0",
        headers=_cabecalho(ambiente),
    )
    assert listagem.status_code == 200, listagem.text
    itens = listagem.json()["items"]
    assert [item["capture_id"] for item in itens] == [body["capture_id"]]
    assert "response_payload" not in itens[0]


def test_capturas_com_mesmo_conteudo_tem_mesmo_digest_e_identidades_distintas(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)
    geometry = _geometria(ambiente, operador, property_id)
    payload = _funai_payload(geometry, versions=["FUNAI_TEST_2026_V1"])

    primeira = operador.post(
        f"/v1/livestock/properties/{property_id}/territorial-captures/synthetic",
        json=payload,
        headers=_cabecalho(ambiente),
    )
    segunda = operador.post(
        f"/v1/livestock/properties/{property_id}/territorial-captures/synthetic",
        json={**payload, "known_at": "2026-03-03T00:00:00Z"},
        headers=_cabecalho(ambiente),
    )

    assert primeira.status_code == 201, primeira.text
    assert segunda.status_code == 201, segunda.text
    assert primeira.json()["response_digest"] == segunda.json()["response_digest"]
    assert primeira.json()["capture_id"] != segunda.json()["capture_id"]


def test_registrar_timeline_sem_versao_nao_inventa_source_version(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)
    geometry = _geometria(ambiente, operador, property_id)
    resposta = operador.post(
        f"/v1/livestock/properties/{property_id}/territorial-captures/synthetic",
        json={
            "geometry_id": geometry["geometry_id"],
            "geometry_version": geometry["version"],
            "profile": "PRODES_LIKE_TIMELINE",
            "request_scope": {"layer": "PRODES_LIKE", "operation": "TIMELINE"},
            "response_payload": {
                "property_area_hectares": 1000.0,
                "years": [
                    {
                        "year": 2024,
                        "feature_count": 1,
                        "source_area_hectares": 12.5,
                        "overlap_area_hectares": 4.2,
                    }
                ],
            },
            "captured_at": "2026-03-01T00:00:00Z",
            "known_at": "2026-03-02T00:00:00Z",
            "source_valid_from": "2024-01-01T00:00:00Z",
            "source_valid_to": "2025-01-01T00:00:00Z",
        },
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 201, resposta.text
    body = resposta.json()
    assert body["source_version_ids"] == []
    assert "SOURCE_VERSION_DECLARED_BY_TEST_FIXTURE" in body["limitations"]


def test_geometry_version_divergente_retorna_409(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)
    geometry = _geometria(ambiente, operador, property_id)
    payload = _funai_payload(geometry, versions=["FUNAI_TEST_2026_V1"])
    payload["geometry_version"] = 999

    resposta = operador.post(
        f"/v1/livestock/properties/{property_id}/territorial-captures/synthetic",
        json=payload,
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 409, resposta.text
    assert resposta.json()["reason_code"] == "CONFLITO_DE_REFERENCIA"


def test_known_at_ausente_retorna_422(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    property_id = _propriedade(ambiente, operador)
    geometry = _geometria(ambiente, operador, property_id)
    payload = _funai_payload(geometry, versions=["FUNAI_TEST_2026_V1"])
    payload.pop("known_at")

    resposta = operador.post(
        f"/v1/livestock/properties/{property_id}/territorial-captures/synthetic",
        json=payload,
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 422, resposta.text


def test_geometria_inexistente_retorna_404(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)
    geometry = _geometria(ambiente, operador, property_id)
    payload = _funai_payload(geometry, versions=["FUNAI_TEST_2026_V1"])
    payload["geometry_id"] = str(uuid4())

    resposta = operador.post(
        f"/v1/livestock/properties/{property_id}/territorial-captures/synthetic",
        json=payload,
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 404, resposta.text


def test_geometria_de_outra_organization_retorna_404_sem_vazar_existencia(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)
    geometry_a = _geometria(ambiente, operador, property_id)
    connection = ambiente.connection
    set_local_organization_context(connection, ambiente.org_b.organization_id)
    property_b = uuid4()
    geometry_b = uuid4()
    connection.execute(
        text(
            "INSERT INTO core_audit.rural_properties ("
            "property_id, record_owner_organization_id, code, name, municipality, "
            "state_code, status, version, created_at) VALUES ("
            ":property_id, :organization_id, :code, 'Fazenda B', "
            "'Cuiaba', 'MT', 'ACTIVE', 1, NOW())"
        ),
        {
            "property_id": property_b,
            "organization_id": ambiente.org_b.organization_id.value,
            "code": f"TERR-B-{uuid4().hex[:10]}",
        },
    )
    connection.execute(
        text(
            "INSERT INTO core_audit.property_geometries ("
            "geometry_id, record_owner_organization_id, property_id, source, layer, "
            "source_srid, source_payload, source_digest, version, imported_at, geom) "
            "VALUES (:geometry_id, :organization_id, :property_id, 'DECLARADA', "
            "'PERIMETRO', 4326, :payload, :digest, 1, NOW(), "
            "ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:payload), 4326)))"
        ),
        {
            "geometry_id": geometry_b,
            "organization_id": ambiente.org_b.organization_id.value,
            "property_id": property_b,
            "payload": (
                '{"type":"Polygon","coordinates":[[[-47.9,-15.8],[-47.8,-15.8],'
                "[-47.8,-15.7],[-47.9,-15.7],[-47.9,-15.8]]]}"
            ),
            "digest": "0" * 64,
        },
    )
    payload = _funai_payload(geometry_a, versions=["FUNAI_TEST_2026_V1"])
    payload["geometry_id"] = str(geometry_b)

    resposta = operador.post(
        f"/v1/livestock/properties/{property_id}/territorial-captures/synthetic",
        json=payload,
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 404, resposta.text


def test_captura_sintetica_nao_cria_decisao_avaliacao_dossie_ou_coverage(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    property_id = _propriedade(ambiente, operador)
    geometry = _geometria(ambiente, operador, property_id)
    connection = ambiente.connection
    antes = _contagens_semanticas(connection, str(ambiente.org_a.organization_id.value))

    resposta = operador.post(
        f"/v1/livestock/properties/{property_id}/territorial-captures/synthetic",
        json=_funai_payload(geometry, versions=["FUNAI_TEST_2026_V1"]),
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 201, resposta.text
    depois = _contagens_semanticas(connection, str(ambiente.org_a.organization_id.value))
    assert depois == antes


def _contagens_semanticas(connection: object, organization_id: str) -> dict[str, int]:
    assert hasattr(connection, "execute")
    return {
        "evaluations": int(
            connection.execute(
                text(
                    "SELECT count(*) FROM core_audit.evaluations "
                    "WHERE record_owner_organization_id = :org"
                ),
                {"org": organization_id},
            ).scalar_one()
        ),
        "decisions": int(
            connection.execute(
                text(
                    "SELECT count(*) FROM core_audit.decisions "
                    "WHERE record_owner_organization_id = :org"
                ),
                {"org": organization_id},
            ).scalar_one()
        ),
        "dossiers": int(
            connection.execute(
                text(
                    "SELECT count(*) FROM core_audit.dossiers "
                    "WHERE record_owner_organization_id = :org"
                ),
                {"org": organization_id},
            ).scalar_one()
        ),
        "coverage": int(
            connection.execute(
                text(
                    "SELECT count(*) FROM core_audit.coverage_contributions "
                    "WHERE record_owner_organization_id = :org"
                ),
                {"org": organization_id},
            ).scalar_one()
        ),
    }
