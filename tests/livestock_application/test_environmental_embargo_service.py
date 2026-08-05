"""Avaliacao espacial de embargos ambientais sobre a geometria vigente."""

import json
from datetime import UTC, datetime

from packages.livestock_application.environmental_embargo_service import (
    EnvironmentalEmbargoGapCode,
    EnvironmentalEmbargoService,
    EnvironmentalEmbargoStatus,
)
from packages.livestock_domain.geometry import GeometrySource, PropertyGeometry, digest_de
from packages.livestock_domain.property import RuralProperty
from packages.livestock_infrastructure.geodata import (
    CarLayer,
    CarProperty,
    SpatialRestriction,
    SpatialRestrictionAssessment,
    TerritorialOverlapAssessment,
    TerritorialTimelineAssessment,
)
from packages.shared_kernel import OrganizationId, TypedId

QUADRADO = json.dumps(
    {
        "type": "Polygon",
        "coordinates": [
            [[-54.0, -22.0], [-54.0, -21.0], [-53.0, -21.0], [-53.0, -22.0], [-54.0, -22.0]]
        ],
    },
    separators=(",", ":"),
)

RESTRICAO = json.dumps(
    {
        "type": "MultiPolygon",
        "coordinates": [
            [[[-54.5, -21.5], [-54.5, -20.5], [-53.5, -20.5], [-53.5, -21.5], [-54.5, -21.5]]]
        ],
    },
    separators=(",", ":"),
)


class FakePropertyRepo:
    def __init__(self, property_found: RuralProperty | None) -> None:
        self.property_found = property_found

    def save(self, prop: RuralProperty) -> None: ...

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None:
        if self.property_found is None:
            return None
        return self.property_found if self.property_found.property_id == property_id else None

    def find_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        return None

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        return []


class FakeGeometryRepo:
    def __init__(self, geometry: PropertyGeometry | None) -> None:
        self.geometry = geometry

    def save(self, geometry: PropertyGeometry) -> None: ...

    def current_for(
        self, property_id: TypedId, layer: str = "AREA_IMOVEL"
    ) -> PropertyGeometry | None:
        if self.geometry is None:
            return None
        return self.geometry if self.geometry.property_id == property_id else None

    def current_layers_for(self, property_id: TypedId) -> list[PropertyGeometry]:
        return []

    def history_of(self, property_id: TypedId, layer: str | None = None) -> list[PropertyGeometry]:
        return []

    def next_version_for(self, property_id: TypedId, layer: str = "AREA_IMOVEL") -> int:
        return 1


class FakeGeodata:
    def __init__(self, assessment: SpatialRestrictionAssessment) -> None:
        self.assessment = assessment
        self.last_polygon_payload: str | None = None
        self.last_srid: int | None = None

    def fetch(self, cod_imovel: str, state: str) -> CarProperty:
        raise AssertionError("Nao deveria consultar o CAR nesta avaliacao.")

    def fetch_layers(self, cod_imovel: str, state: str) -> list[CarLayer]:
        raise AssertionError("Nao deveria consultar camadas do CAR nesta avaliacao.")

    def fetch_ibama_overlaps(
        self, *, polygon_payload: str, srid: int = 4326
    ) -> SpatialRestrictionAssessment:
        self.last_polygon_payload = polygon_payload
        self.last_srid = srid
        return self.assessment

    def fetch_prodes_timeline(
        self,
        *,
        cod_imovel: str,
        state: str,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> TerritorialTimelineAssessment:
        raise AssertionError("Nao deveria consultar a timeline PRODES nesta avaliacao.")

    def fetch_deter_timeline(
        self,
        *,
        cod_imovel: str,
        state: str,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> TerritorialTimelineAssessment:
        raise AssertionError("Nao deveria consultar a timeline DETER nesta avaliacao.")

    def fetch_funai_overlap(
        self,
        *,
        cod_imovel: str,
        state: str,
    ) -> TerritorialOverlapAssessment:
        raise AssertionError("Nao deveria consultar sobreposicao FUNAI nesta avaliacao.")


def _property(org_id: OrganizationId, property_id: TypedId) -> RuralProperty:
    return RuralProperty(
        property_id=property_id,
        organization_id=org_id,
        code="PROP-1",
        name="Fazenda Exemplo",
        municipality="Dourados",
        state_code="MS",
        created_at=datetime.now(UTC),
    )


def _geometry(org_id: OrganizationId, property_id: TypedId) -> PropertyGeometry:
    return PropertyGeometry(
        geometry_id=TypedId.new("property_geometry"),
        organization_id=org_id,
        property_id=property_id,
        source=GeometrySource.DECLARADA,
        layer="AREA_IMOVEL",
        srid=4326,
        source_payload=QUADRADO,
        source_digest=digest_de(QUADRADO),
        version=2,
        imported_at=datetime.now(UTC),
    )


def _restriction_assessment(with_restriction: bool) -> SpatialRestrictionAssessment:
    restrictions = (
        SpatialRestriction(
            source="IBAMA",
            layer="IBAMA_EMBARGOS",
            feature_id=10,
            polygon_payload=RESTRICAO,
            polygon_digest=digest_de(RESTRICAO),
            response_digest="a" * 64,
            version_id="ibama_v1",
            attributes={"nom_embarg": "Fazenda Exemplo", "area_ha": 150.5},
        ),
    )
    return SpatialRestrictionAssessment(
        source="IBAMA",
        layer="IBAMA_EMBARGOS",
        operation="intersects",
        version_ids=("ibama_v1",),
        restriction_count=1 if with_restriction else 0,
        restrictions=restrictions if with_restriction else (),
        response_digest="b" * 64,
    )


def test_avaliacao_retorna_restricoes_do_provider() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    geometry = _geometry(org_id, property_id)
    geodata = FakeGeodata(_restriction_assessment(with_restriction=True))
    service = EnvironmentalEmbargoService(
        property_repository=FakePropertyRepo(_property(org_id, property_id)),
        geometry_repository=FakeGeometryRepo(geometry),
        geodata_lookup=geodata,
    )

    assessment = service.assess_ibama_embargoes(org_id, property_id)

    assert assessment.status is EnvironmentalEmbargoStatus.COM_RESTRICAO
    assert assessment.geometry_id == geometry.geometry_id
    assert assessment.geometry_version == 2
    assert assessment.version_ids == ("ibama_v1",)
    assert assessment.restriction_count == 1
    assert assessment.restrictions[0].attributes["nom_embarg"] == "Fazenda Exemplo"
    assert geodata.last_polygon_payload == geometry.source_payload
    assert geodata.last_srid == 4326


def test_avaliacao_sem_geometria_declara_lacuna() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    service = EnvironmentalEmbargoService(
        property_repository=FakePropertyRepo(_property(org_id, property_id)),
        geometry_repository=FakeGeometryRepo(None),
        geodata_lookup=FakeGeodata(_restriction_assessment(with_restriction=False)),
    )

    assessment = service.assess_ibama_embargoes(org_id, property_id)

    assert assessment.status is EnvironmentalEmbargoStatus.INDETERMINADA
    assert assessment.geometry_id is None
    assert assessment.restriction_count == 0
    assert assessment.gaps[0].code is EnvironmentalEmbargoGapCode.GEOMETRIA_AUSENTE


def test_avaliacao_sem_restricao_nao_inventa_bloqueio() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    service = EnvironmentalEmbargoService(
        property_repository=FakePropertyRepo(_property(org_id, property_id)),
        geometry_repository=FakeGeometryRepo(_geometry(org_id, property_id)),
        geodata_lookup=FakeGeodata(_restriction_assessment(with_restriction=False)),
    )

    assessment = service.assess_ibama_embargoes(org_id, property_id)

    assert assessment.status is EnvironmentalEmbargoStatus.SEM_RESTRICAO
    assert assessment.restrictions == ()


def test_propriedade_inexistente_e_recusada() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    service = EnvironmentalEmbargoService(
        property_repository=FakePropertyRepo(None),
        geometry_repository=FakeGeometryRepo(None),
        geodata_lookup=FakeGeodata(_restriction_assessment(with_restriction=False)),
    )

    try:
        service.assess_ibama_embargoes(org_id, property_id)
    except KeyError as error:
        assert "nao encontrada" in str(error)
    else:
        raise AssertionError("Esperava KeyError para propriedade inexistente.")
