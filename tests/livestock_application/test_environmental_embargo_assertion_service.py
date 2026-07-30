"""Congelamento da avaliacao espacial em assercao auditavel."""

from datetime import UTC, datetime

from packages.livestock_application.environmental_embargo_assertion_service import (
    EnvironmentalEmbargoAssertionService,
)
from packages.livestock_application.environmental_embargo_service import (
    EnvironmentalEmbargoAssessment,
    EnvironmentalEmbargoGap,
    EnvironmentalEmbargoGapCode,
    EnvironmentalEmbargoStatus,
)
from packages.livestock_application.event_recorder import LivestockEventRecorder
from packages.livestock_domain.environmental_embargo_assertion import (
    EnvironmentalEmbargoAssertionStatus,
    PropertyEnvironmentalEmbargoAssertion,
)
from packages.livestock_infrastructure.geodata import SpatialRestriction
from packages.shared_kernel import FixedClock, OrganizationId, TypedId
from tests.livestock_support import FakeEventLog, operation_context


class FakeAssessmentService:
    def __init__(self, assessment: EnvironmentalEmbargoAssessment) -> None:
        self.assessment = assessment

    def assess_ibama_embargoes(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> EnvironmentalEmbargoAssessment:
        assert self.assessment.property_id == property_id
        return self.assessment


class FakeAssertionRepo:
    def __init__(self) -> None:
        self.saved: list[PropertyEnvironmentalEmbargoAssertion] = []

    def save(self, assertion: PropertyEnvironmentalEmbargoAssertion) -> None:
        self.saved.append(assertion)

    def list_by_property(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> list[PropertyEnvironmentalEmbargoAssertion]:
        return [
            item
            for item in self.saved
            if item.organization_id == organization_id and item.property_id == property_id
        ]


def _assessment(
    *,
    property_id: TypedId,
    geometry_id: TypedId | None,
    status: EnvironmentalEmbargoStatus,
) -> EnvironmentalEmbargoAssessment:
    restrictions = (
        SpatialRestriction(
            source="IBAMA",
            layer="IBAMA_EMBARGOS",
            feature_id=10,
            polygon_payload='{"type":"Polygon","coordinates":[]}',
            polygon_digest="a" * 64,
            response_digest="b" * 64,
            version_id="ibama_v1",
            attributes={"nom_embarg": "Fazenda Exemplo"},
        ),
    )
    return EnvironmentalEmbargoAssessment(
        property_id=property_id,
        geometry_id=geometry_id,
        source="IBAMA",
        layer="IBAMA_EMBARGOS",
        operation="intersects",
        status=status,
        geometry_version=None if geometry_id is None else 2,
        source_digest=None if geometry_id is None else "c" * 64,
        version_ids=("ibama_v1",),
        restrictions=restrictions if status is EnvironmentalEmbargoStatus.COM_RESTRICAO else (),
        response_digest=None if status is EnvironmentalEmbargoStatus.INDETERMINADA else "d" * 64,
        gaps=(
            (
                EnvironmentalEmbargoGap(
                    code=EnvironmentalEmbargoGapCode.GEOMETRIA_AUSENTE,
                    message="Sem geometria.",
                ),
            )
            if status is EnvironmentalEmbargoStatus.INDETERMINADA
            else ()
        ),
    )


def test_record_ibama_assertion_congela_a_observacao() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    geometry_id = TypedId.new("property_geometry")
    recorder = LivestockEventRecorder(
        event_log=FakeEventLog(),
        clock=FixedClock(datetime(2026, 7, 29, 15, 0, tzinfo=UTC)),
    )
    repo = FakeAssertionRepo()
    service = EnvironmentalEmbargoAssertionService(
        assessment_service=FakeAssessmentService(
            _assessment(
                property_id=property_id,
                geometry_id=geometry_id,
                status=EnvironmentalEmbargoStatus.COM_RESTRICAO,
            )
        ),
        repository=repo,
        recorder=recorder,
    )

    assertion = service.record_ibama_assertion(operation_context(org_id), property_id)

    assert assertion.status is EnvironmentalEmbargoAssertionStatus.COM_RESTRICAO
    assert assertion.geometry_id == geometry_id
    assert assertion.geometry_version == 2
    assert assertion.version_ids == ("ibama_v1",)
    assert assertion.restriction_count == 1
    assert repo.saved == [assertion]


def test_record_ibama_assertion_preserva_lacuna_sem_geometria() -> None:
    org_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    service = EnvironmentalEmbargoAssertionService(
        assessment_service=FakeAssessmentService(
            _assessment(
                property_id=property_id,
                geometry_id=None,
                status=EnvironmentalEmbargoStatus.INDETERMINADA,
            )
        ),
        repository=FakeAssertionRepo(),
        recorder=LivestockEventRecorder(
            event_log=FakeEventLog(),
            clock=FixedClock(datetime(2026, 7, 29, 15, 0, tzinfo=UTC)),
        ),
    )

    assertion = service.record_ibama_assertion(operation_context(org_id), property_id)

    assert assertion.status is EnvironmentalEmbargoAssertionStatus.INDETERMINADA
    assert assertion.geometry_id is None
    assert assertion.restriction_count == 0
