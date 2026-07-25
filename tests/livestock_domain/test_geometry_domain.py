"""Geometria da propriedade (Passo 17.1, ADR-0026).

O que estes testes protegem: material recebido não é reinterpretado, SRID é
obrigatório, ponto não vira limite de propriedade, e eixo invertido é detectado
antes de virar uma fazenda no meio do oceano.
"""

import json

import pytest

from packages.livestock_domain.geometry import (
    CAMADA_PERIMETRO,
    SRID_CANONICO,
    GeometriaInvalida,
    GeometrySource,
    PropertyGeometry,
    digest_de,
    validar_geojson,
)
from packages.shared_kernel import OrganizationId, TypedId

POLIGONO = json.dumps(
    {
        "type": "Polygon",
        "coordinates": [
            [[-47.9, -15.8], [-47.8, -15.8], [-47.8, -15.7], [-47.9, -15.7], [-47.9, -15.8]]
        ],
    }
)


def _geometria(**ajustes: object) -> PropertyGeometry:
    padrao: dict[str, object] = {
        "geometry_id": TypedId.new("property_geometry"),
        "organization_id": OrganizationId.new(),
        "property_id": TypedId.new("rural_property"),
        "source": GeometrySource.DECLARADA,
        "layer": CAMADA_PERIMETRO,
        "srid": SRID_CANONICO,
        "source_payload": POLIGONO,
        "source_digest": digest_de(POLIGONO),
        "version": 1,
    }
    padrao.update(ajustes)
    return PropertyGeometry(**padrao)  # type: ignore[arg-type]


def test_a_geometria_declarada_e_admitida() -> None:
    geometria = _geometria()

    assert geometria.normalizada
    assert geometria.version == 1


def test_o_digest_precisa_conferir_com_o_material() -> None:
    """Digest que não bate faz o registro afirmar proveniência de outro conteúdo."""
    with pytest.raises(GeometriaInvalida, match="não confere"):
        _geometria(source_digest=digest_de("outra coisa"))


def test_o_digest_e_do_material_como_recebido() -> None:
    """Reserializar normalizaria espaços e ordem, e o digest deixaria de identificar."""
    espacado = '{"type":  "Polygon",  "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}'
    compacto = json.dumps(json.loads(espacado))

    assert digest_de(espacado) != digest_de(compacto)


def test_srid_ausente_e_recusado() -> None:
    """Coordenada sem sistema de referência não localiza nada."""
    with pytest.raises(GeometriaInvalida, match="srid"):
        _geometria(srid=0)


def test_srid_diferente_do_canonico_nao_e_normalizado() -> None:
    geometria = _geometria(srid=31983)

    assert not geometria.normalizada


def test_geometria_do_sicar_exige_a_referencia_externa() -> None:
    """Sem o código do imóvel, a importação não é reproduzível."""
    with pytest.raises(ValueError, match="referência externa"):
        _geometria(source=GeometrySource.SICAR_CAR)

    _geometria(source=GeometrySource.SICAR_CAR, external_reference="MG-3106200-ABC123")


def test_ponto_nao_e_limite_de_propriedade() -> None:
    """Ponto não é promovido a polígono nem interpretado como limite cadastral."""
    ponto = json.dumps({"type": "Point", "coordinates": [-47.9, -15.8]})

    with pytest.raises(GeometriaInvalida, match="não é admitido"):
        validar_geojson(ponto)


def test_material_que_nao_e_json_e_recusado() -> None:
    with pytest.raises(GeometriaInvalida, match="JSON válido"):
        validar_geojson("<xml>não é geojson</xml>")


def test_geometria_sem_coordenadas_e_recusada() -> None:
    vazio = json.dumps({"type": "Polygon", "coordinates": []})

    with pytest.raises(GeometriaInvalida, match="não declara coordenadas"):
        validar_geojson(vazio)


@pytest.mark.parametrize(
    ("coordenada", "esperado"),
    [
        ([-200.0, -15.8], "Longitude"),
        ([-47.9, -100.0], "Latitude"),
        # O engano mais comum: latitude e longitude trocadas de lugar.
        ([-15.8, -190.0], "Latitude"),
    ],
)
def test_coordenada_fora_de_faixa_e_recusada(coordenada: list[float], esperado: str) -> None:
    fora = json.dumps(
        {"type": "Polygon", "coordinates": [[coordenada, [0, 0], [1, 1], coordenada]]}
    )

    with pytest.raises(GeometriaInvalida, match=esperado):
        validar_geojson(fora)


def test_coordenada_com_um_valor_e_recusada() -> None:
    incompleta = json.dumps({"type": "Polygon", "coordinates": [[[-47.9], [0, 0], [1, 1]]]})

    with pytest.raises(GeometriaInvalida, match="longitude e latitude"):
        validar_geojson(incompleta)


def test_multipolygon_e_admitido() -> None:
    """Propriedade com áreas descontínuas é caso comum, e não exceção."""
    multi = json.dumps(
        {
            "type": "MultiPolygon",
            "coordinates": [
                [[[-47.9, -15.8], [-47.8, -15.8], [-47.8, -15.7], [-47.9, -15.8]]],
                [[[-47.5, -15.5], [-47.4, -15.5], [-47.4, -15.4], [-47.5, -15.5]]],
            ],
        }
    )

    assert validar_geojson(multi)["type"] == "MultiPolygon"


def test_versao_precisa_ser_positiva() -> None:
    with pytest.raises(ValueError, match="version"):
        _geometria(version=0)


def test_identificador_de_outro_tipo_e_recusado() -> None:
    with pytest.raises(ValueError, match="property_geometry"):
        _geometria(geometry_id=TypedId.new("animal"))


def test_a_camada_e_obrigatoria() -> None:
    """Sem ela nao se sabe se o poligono e o perimetro ou a reserva legal."""
    with pytest.raises(ValueError, match="layer"):
        _geometria(layer="  ")


def test_a_camada_distingue_perimetro_de_area_protegida() -> None:
    assert _geometria().e_perimetro
    assert not _geometria().e_area_protegida

    reserva = _geometria(layer="RESERVA_LEGAL")
    assert reserva.e_area_protegida
    assert not reserva.e_perimetro
