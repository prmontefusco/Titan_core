"""Leitura temporal territorial por propriedade."""

from datetime import UTC, datetime

from packages.livestock_application.territorial_timeline_service import (
    TerritorialTimelineGapCode,
    TerritorialTimelineService,
    TerritorialTimelineStatus,
)
from packages.livestock_domain.geometry import GeometrySource, PropertyGeometry, digest_de
from packages.livestock_domain.property import RuralProperty
from packages.livestock_infrastructure.geodata import (
    TerritorialTimelineAssessment,
    TerritorialTimelineYear,
)
from packages.shared_kernel import OrganizationId, TypedId

QUADRADO = (
    '{"type":"Polygon","coordinates":[[[-54.0,-22.0],[-54.0,-21.0],'
    "[-53.0,-21.0],[-53.0,-22.0],[-54.0,-22.0]]]}"
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


class FakeTimelineLookup:
    def __init__(self, timeline: TerritorialTimelineAssessment) -> None:
        self.timeline = timeline
        self.last_cod_imovel: str | None = None
        self.last_state: str | None = None
        self.last_year_from: int | None = None
        self.last_year_to: int | None = None
        self.last_layer: str | None = None

    def fetch_prodes_timeline(
        self,
        *,
        cod_imovel: str,
        state: str,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> TerritorialTimelineAssessment:
        self.last_cod_imovel = cod_imovel
        self.last_state = state
        self.last_year_from = year_from
        self.last_year_to = year_to
        self.last_layer = "TB_PRODES"
        return self.timeline

    def fetch_deter_timeline(
        self,
        *,
        cod_imovel: str,
        state: str,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> TerritorialTimelineAssessment:
        self.last_cod_imovel = cod_imovel
        self.last_state = state
        self.last_year_from = year_from
        self.last_year_to = year_to
        self.last_layer = "TB_DETER"
        return self.timeline


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
        source=GeometrySource.SICAR_CAR,
        layer="AREA_IMOVEL",
        srid=4326,
        source_payload=QUADRADO,
        source_digest=digest_de(QUADRADO),
        version=2,
        external_reference="MS-5006606-3DCF573FEF1E44B9972057BD4C932A9E",
        imported_at=datetime.now(UTC),
    )


def _declared_geometry_without_reference(
    org_id: OrganizationId, property_id: TypedId
) -> PropertyGeometry:
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


def _timeline() -> TerritorialTimelineAssessment:
    return TerritorialTimelineAssessment(
        source="INPE/TerraBrasilis",
        layer="TB_PRODES",
        property_area_hectares=1363.93,
        year_from=2020,
        year_to=2021,
        years=(
            TerritorialTimelineYear(
                year=2020,
                feature_count=1,
                overlap_area_hectares=8.25,
                source_area_hectares=12.5,
                version_ids=("tb_prodes_ms_2020",),
            ),
            TerritorialTimelineYear(
                year=2021,
                feature_count=2,
                overlap_area_hectares=11.0,
                source_area_hectares=20.0,
                version_ids=("tb_prodes_ms_2021",),
            ),
        ),
        response_digest="a" * 64,
    )


def test_assess_prodes_timeline_usa_referencia_externa_da_geometria() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    geometry = _geometry(org_id, property_id)
    lookup = FakeTimelineLookup(_timeline())
    service = TerritorialTimelineService(
        property_repository=FakePropertyRepo(_property(org_id, property_id)),
        geometry_repository=FakeGeometryRepo(geometry),
        geodata_lookup=lookup,
    )

    assessment = service.assess_prodes_timeline(
        org_id,
        property_id,
        year_from=2020,
        year_to=2021,
    )

    assert assessment.status is TerritorialTimelineStatus.DISPONIVEL
    assert assessment.geometry_id == geometry.geometry_id
    assert assessment.geometry_version == 2
    assert assessment.external_reference == geometry.external_reference
    assert assessment.layer == "TB_PRODES"
    assert assessment.source == "INPE/TerraBrasilis"
    assert assessment.years[0]["year"] == 2020
    assert assessment.years[1]["feature_count"] == 2
    assert lookup.last_cod_imovel == geometry.external_reference
    assert lookup.last_state == "MS"
    assert lookup.last_year_from == 2020
    assert lookup.last_year_to == 2021
    assert lookup.last_layer == "TB_PRODES"


def test_assess_deter_timeline_usa_referencia_externa_da_geometria() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    geometry = _geometry(org_id, property_id)
    timeline = TerritorialTimelineAssessment(
        source="INPE/TerraBrasilis",
        layer="TB_DETER",
        property_area_hectares=1363.93,
        year_from=2026,
        year_to=2026,
        years=(
            TerritorialTimelineYear(
                year=2026,
                feature_count=1,
                overlap_area_hectares=3.25,
                source_area_hectares=3.25,
                version_ids=("tb_deter_ms_2026",),
            ),
        ),
        response_digest="b" * 64,
    )
    lookup = FakeTimelineLookup(timeline)
    service = TerritorialTimelineService(
        property_repository=FakePropertyRepo(_property(org_id, property_id)),
        geometry_repository=FakeGeometryRepo(geometry),
        geodata_lookup=lookup,
    )

    assessment = service.assess_deter_timeline(
        org_id,
        property_id,
        year_from=2026,
        year_to=2026,
    )

    assert assessment.status is TerritorialTimelineStatus.DISPONIVEL
    assert assessment.layer == "TB_DETER"
    assert assessment.years[0]["year"] == 2026
    assert assessment.years[0]["feature_count"] == 1
    assert lookup.last_layer == "TB_DETER"


def test_assess_prodes_timeline_sem_geometria_declara_lacuna() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    service = TerritorialTimelineService(
        property_repository=FakePropertyRepo(_property(org_id, property_id)),
        geometry_repository=FakeGeometryRepo(None),
        geodata_lookup=FakeTimelineLookup(_timeline()),
    )

    assessment = service.assess_prodes_timeline(org_id, property_id)

    assert assessment.status is TerritorialTimelineStatus.INDETERMINADA
    assert assessment.geometry_id is None
    assert assessment.years == ()
    assert assessment.gaps[0].code is TerritorialTimelineGapCode.GEOMETRIA_AUSENTE


def test_assess_prodes_timeline_sem_referencia_externa_declara_lacuna() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    geometry = _declared_geometry_without_reference(org_id, property_id)
    service = TerritorialTimelineService(
        property_repository=FakePropertyRepo(_property(org_id, property_id)),
        geometry_repository=FakeGeometryRepo(geometry),
        geodata_lookup=FakeTimelineLookup(_timeline()),
    )

    assessment = service.assess_prodes_timeline(org_id, property_id)

    assert assessment.status is TerritorialTimelineStatus.INDETERMINADA
    assert assessment.geometry_id == geometry.geometry_id
    assert assessment.external_reference is None
    assert assessment.years == ()
    assert assessment.gaps[0].code is TerritorialTimelineGapCode.REFERENCIA_EXTERNA_AUSENTE


def test_assess_deter_timeline_sem_geometria_declara_lacuna() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    service = TerritorialTimelineService(
        property_repository=FakePropertyRepo(_property(org_id, property_id)),
        geometry_repository=FakeGeometryRepo(None),
        geodata_lookup=FakeTimelineLookup(_timeline()),
    )

    assessment = service.assess_deter_timeline(org_id, property_id)

    assert assessment.status is TerritorialTimelineStatus.INDETERMINADA
    assert assessment.geometry_id is None
    assert assessment.layer == "TB_DETER"
    assert assessment.gaps[0].code is TerritorialTimelineGapCode.GEOMETRIA_AUSENTE
