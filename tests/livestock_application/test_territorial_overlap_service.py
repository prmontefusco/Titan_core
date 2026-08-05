"""Leitura territorial atual por propriedade."""

from datetime import UTC, datetime

from packages.livestock_application.territorial_overlap_service import (
    TerritorialOverlapGapCode,
    TerritorialOverlapService,
    TerritorialOverlapStatus,
)
from packages.livestock_domain.geometry import GeometrySource, PropertyGeometry, digest_de
from packages.livestock_domain.property import RuralProperty
from packages.livestock_infrastructure.geodata import TerritorialOverlapAssessment
from packages.shared_kernel import OrganizationId, TypedId

QUADRADO = (
    '{"coordinates":[[[-54.0,-22.0],[-54.0,-21.0],[-53.0,-21.0],'
    '[-53.0,-22.0],[-54.0,-22.0]]],"type":"Polygon"}'
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
    def __init__(self, assessment: TerritorialOverlapAssessment) -> None:
        self.assessment = assessment
        self.last_cod_imovel: str | None = None
        self.last_state: str | None = None

    def fetch_funai_overlap(
        self,
        *,
        cod_imovel: str,
        state: str,
    ) -> TerritorialOverlapAssessment:
        self.last_cod_imovel = cod_imovel
        self.last_state = state
        return self.assessment


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


def _geometry(
    org_id: OrganizationId, property_id: TypedId, *, external_reference: str | None
) -> PropertyGeometry:
    return PropertyGeometry(
        geometry_id=TypedId.new("property_geometry"),
        organization_id=org_id,
        property_id=property_id,
        source=GeometrySource.SICAR_CAR,
        layer="AREA_IMOVEL",
        srid=4326,
        source_payload=QUADRADO,
        source_digest=digest_de(QUADRADO),
        external_reference=external_reference,
        version=2,
        imported_at=datetime.now(UTC),
    )


def test_avaliacao_funai_retorna_sobreposicao_do_provider() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    geometry = _geometry(org_id, property_id, external_reference="MS-REF-1")
    geodata = FakeGeodata(
        TerritorialOverlapAssessment(
            source="FUNAI",
            layer="FUNAI_TI",
            label="Terras Indigenas (FUNAI)",
            feature_count=1,
            area_hectares=12.5,
            source_area_hectares=80.0,
            version_ids=("funai_v1",),
            response_digest="a" * 64,
        )
    )
    service = TerritorialOverlapService(
        property_repository=FakePropertyRepo(_property(org_id, property_id)),
        geometry_repository=FakeGeometryRepo(geometry),
        geodata_lookup=geodata,
    )

    assessment = service.assess_funai_overlap(org_id, property_id)

    assert assessment.status is TerritorialOverlapStatus.COM_RESTRICAO
    assert assessment.feature_count == 1
    assert assessment.geometry_id == geometry.geometry_id
    assert geodata.last_cod_imovel == "MS-REF-1"
    assert geodata.last_state == "MS"


def test_avaliacao_funai_sem_geometria_declara_lacuna() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    service = TerritorialOverlapService(
        property_repository=FakePropertyRepo(_property(org_id, property_id)),
        geometry_repository=FakeGeometryRepo(None),
        geodata_lookup=FakeGeodata(
            TerritorialOverlapAssessment(
                source="FUNAI",
                layer="FUNAI_TI",
                label="Terras Indigenas (FUNAI)",
                feature_count=0,
                area_hectares=None,
                source_area_hectares=None,
                version_ids=(),
                response_digest="b" * 64,
            )
        ),
    )

    assessment = service.assess_funai_overlap(org_id, property_id)

    assert assessment.status is TerritorialOverlapStatus.INDETERMINADA
    assert assessment.gaps[0].code is TerritorialOverlapGapCode.GEOMETRIA_AUSENTE


def test_avaliacao_funai_sem_referencia_externa_declara_lacuna() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    service = TerritorialOverlapService(
        property_repository=FakePropertyRepo(_property(org_id, property_id)),
        geometry_repository=FakeGeometryRepo(
            PropertyGeometry(
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
        ),
        geodata_lookup=FakeGeodata(
            TerritorialOverlapAssessment(
                source="FUNAI",
                layer="FUNAI_TI",
                label="Terras Indigenas (FUNAI)",
                feature_count=0,
                area_hectares=None,
                source_area_hectares=None,
                version_ids=(),
                response_digest="c" * 64,
            )
        ),
    )

    assessment = service.assess_funai_overlap(org_id, property_id)

    assert assessment.status is TerritorialOverlapStatus.INDETERMINADA
    assert assessment.gaps[0].code is TerritorialOverlapGapCode.REFERENCIA_EXTERNA_AUSENTE
