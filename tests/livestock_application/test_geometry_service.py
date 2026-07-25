"""Importação do CAR (Passo 17.2, ADR-0026).

O que estes testes protegem é uma descoberta de campo: **dado oficial real contém
geometria inválida**. O SICAR entrega camadas com componentes degenerados, e duas
das três fazendas usadas na validação tinham uma. Recusar tudo por causa disso
perderia o perímetro — que é o que responde onde fica a fazenda.
"""

import json
from datetime import UTC, datetime

import pytest

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.geometry_service import (
    PropertyGeometryService,
)
from packages.livestock_domain.geometry import (
    CAMADA_PERIMETRO,
    GeometriaInvalida,
    PropertyGeometry,
    digest_de,
)
from packages.livestock_domain.property import RuralProperty
from packages.livestock_infrastructure.geodata import CarLayer, CarProperty
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog

VALIDO = json.dumps(
    {
        "type": "Polygon",
        "coordinates": [
            [[-47.9, -15.8], [-47.8, -15.8], [-47.8, -15.7], [-47.9, -15.7], [-47.9, -15.8]]
        ],
    }
)

# Um anel com dois pontos: exatamente o "Too few points in geometry component"
# que o SICAR devolve de verdade.
DEGENERADO = json.dumps({"type": "Polygon", "coordinates": [[[-47.9, -15.8], [-47.8, -15.8]]]})


class FakeGeometryRepo:
    def __init__(self) -> None:
        self.gravadas: list[PropertyGeometry] = []

    def save(self, geometry: PropertyGeometry) -> None:
        self.gravadas.append(geometry)

    def current_for(
        self, property_id: TypedId, layer: str = CAMADA_PERIMETRO
    ) -> PropertyGeometry | None:
        candidatas = [g for g in self.gravadas if g.layer == layer]
        return max(candidatas, key=lambda g: g.version) if candidatas else None

    def current_layers_for(self, property_id: TypedId) -> list[PropertyGeometry]:
        return list(self.gravadas)

    def history_of(self, property_id: TypedId, layer: str | None = None) -> list[PropertyGeometry]:
        return [g for g in self.gravadas if layer is None or g.layer == layer]

    def next_version_for(self, property_id: TypedId, layer: str = CAMADA_PERIMETRO) -> int:
        return len([g for g in self.gravadas if g.layer == layer]) + 1


class FakePropertyRepo:
    def __init__(self, propriedade: RuralProperty) -> None:
        self.propriedade = propriedade

    def save(self, prop: RuralProperty) -> None: ...

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None:
        return self.propriedade if property_id == self.propriedade.property_id else None

    def find_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        return None

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        return [self.propriedade]


class FakeCarLookup:
    """O provider, com o perímetro e as camadas que se quiser exercitar."""

    def __init__(self, perimetro: str = VALIDO, camadas: tuple[CarLayer, ...] = ()) -> None:
        self.perimetro = perimetro
        self.camadas = camadas

    def fetch(self, cod_imovel: str, state: str) -> CarProperty:
        return CarProperty(
            cod_imovel=cod_imovel,
            state=state,
            layer=CAMADA_PERIMETRO,
            polygon_payload=self.perimetro,
            polygon_digest=digest_de(self.perimetro),
            response_digest="b" * 64,
            attributes={"municipio": "Ponta Pora", "dat_atuali": "2023-07-06T00:00:00"},
        )

    def fetch_layers(self, cod_imovel: str, state: str) -> list[CarLayer]:
        return list(self.camadas)


def _camada(nome: str, payload: str) -> CarLayer:
    return CarLayer(
        layer=nome,
        label=nome.title(),
        polygon_payload=payload,
        polygon_digest=digest_de(payload),
        area_hectares=10.0,
        feature_count=1,
    )


def _servico(
    recorder: LivestockEventRecorder,
    organization_id: OrganizationId,
    property_id: TypedId,
    lookup: FakeCarLookup,
) -> tuple[PropertyGeometryService, FakeGeometryRepo]:
    repositorio = FakeGeometryRepo()
    propriedade = RuralProperty(
        property_id=property_id,
        organization_id=organization_id,
        code="P-1",
        name="Fazenda",
        municipality="Ponta Pora",
        state_code="MS",
        created_at=datetime.now(UTC),
    )
    servico = PropertyGeometryService(
        geometry_repository=repositorio,
        property_repository=FakePropertyRepo(propriedade),
        recorder=recorder,
        car_lookup=lookup,
    )
    return servico, repositorio


def test_camada_invalida_nao_derruba_as_boas(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """Perder o perímetro porque a hidrografia está quebrada seria trocar o
    essencial pelo acessório."""
    property_id = TypedId.new("rural_property")
    lookup = FakeCarLookup(
        camadas=(
            _camada("RESERVA_LEGAL", VALIDO),
            _camada("HIDROGRAFIA", DEGENERADO),
            _camada("APPS", VALIDO),
        )
    )
    servico, _ = _servico(recorder, context.organization_id, property_id, lookup)

    resultado = servico.import_from_car(
        context=context, property_id=property_id, cod_imovel="MS-1", state="MS"
    )

    assert {g.layer for g in resultado.gravadas} == {CAMADA_PERIMETRO, "RESERVA_LEGAL", "APPS"}
    assert [r.layer for r in resultado.recusadas] == ["HIDROGRAFIA"]
    # A recusa carrega o motivo: sem ele, ninguém sabe o que houve.
    assert "coordenada" in resultado.recusadas[0].motivo.lower() or resultado.recusadas[0].motivo


def test_perimetro_invalido_faz_a_importacao_falhar(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """Sem o perímetro não há o que importar: ele não é acessório."""
    property_id = TypedId.new("rural_property")
    lookup = FakeCarLookup(perimetro=DEGENERADO, camadas=(_camada("APPS", VALIDO),))
    servico, _ = _servico(recorder, context.organization_id, property_id, lookup)

    with pytest.raises(GeometriaInvalida):
        servico.import_from_car(
            context=context, property_id=property_id, cod_imovel="MS-1", state="MS"
        )


def test_cada_camada_tem_versao_propria(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """A camada é dimensão: a reserva legal não é versão 2 do perímetro."""
    property_id = TypedId.new("rural_property")
    lookup = FakeCarLookup(camadas=(_camada("RESERVA_LEGAL", VALIDO),))
    servico, repositorio = _servico(recorder, context.organization_id, property_id, lookup)

    servico.import_from_car(context=context, property_id=property_id, cod_imovel="MS-1", state="MS")

    assert {(g.layer, g.version) for g in repositorio.gravadas} == {
        (CAMADA_PERIMETRO, 1),
        ("RESERVA_LEGAL", 1),
    }


def test_importar_de_novo_versiona_cada_camada_em_separado(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    property_id = TypedId.new("rural_property")
    lookup = FakeCarLookup(camadas=(_camada("RESERVA_LEGAL", VALIDO),))
    servico, repositorio = _servico(recorder, context.organization_id, property_id, lookup)

    servico.import_from_car(context=context, property_id=property_id, cod_imovel="MS-1", state="MS")
    servico.import_from_car(context=context, property_id=property_id, cod_imovel="MS-1", state="MS")

    assert repositorio.next_version_for(property_id, CAMADA_PERIMETRO) == 3
    assert repositorio.next_version_for(property_id, "RESERVA_LEGAL") == 3


def test_sem_camadas_importa_so_o_perimetro(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    property_id = TypedId.new("rural_property")
    lookup = FakeCarLookup(camadas=(_camada("APPS", VALIDO),))
    servico, repositorio = _servico(recorder, context.organization_id, property_id, lookup)

    resultado = servico.import_from_car(
        context=context,
        property_id=property_id,
        cod_imovel="MS-1",
        state="MS",
        incluir_camadas=False,
    )

    assert [g.layer for g in resultado.gravadas] == [CAMADA_PERIMETRO]


def test_a_data_do_car_viaja_para_todas_as_camadas(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """Todas vieram da mesma consulta, e a defasagem vale para todas."""
    property_id = TypedId.new("rural_property")
    lookup = FakeCarLookup(camadas=(_camada("APPS", VALIDO),))
    servico, repositorio = _servico(recorder, context.organization_id, property_id, lookup)

    servico.import_from_car(context=context, property_id=property_id, cod_imovel="MS-1", state="MS")

    assert {g.captured_at for g in repositorio.gravadas} == {datetime(2023, 7, 6, tzinfo=UTC)}


def test_a_previa_nao_grava_nada(
    recorder: LivestockEventRecorder,
    context: LivestockOperationContext,
    event_log: FakeEventLog,
) -> None:
    """Ela ajuda o cadastro; quem confirma é o operador."""
    property_id = TypedId.new("rural_property")
    servico, repositorio = _servico(recorder, context.organization_id, property_id, FakeCarLookup())

    imovel = servico.preview_car("MS-1", "MS")

    assert imovel.municipality == "Ponta Pora"
    assert repositorio.gravadas == []
    assert event_log.events == []
