"""Congela a avaliacao espacial de embargo ambiental como assercao auditavel."""

from dataclasses import dataclass
from typing import Protocol

from packages.livestock_application.environmental_embargo_service import (
    EnvironmentalEmbargoAssessment,
    EnvironmentalEmbargoStatus,
)
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_domain.environmental_embargo_assertion import (
    EnvironmentalEmbargoAssertionStatus,
    PropertyEnvironmentalEmbargoAssertion,
)
from packages.livestock_domain.events import (
    PROPERTY_ENVIRONMENTAL_EMBARGO_ASSERTION_RECORDED,
    property_environmental_embargo_assertion_recorded_payload,
)
from packages.shared_kernel import OrganizationId, TypedId


class EnvironmentalEmbargoAssessmentPort(Protocol):
    def assess_ibama_embargoes(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> EnvironmentalEmbargoAssessment: ...


class PropertyEnvironmentalEmbargoAssertionRepositoryPort(Protocol):
    def save(self, assertion: PropertyEnvironmentalEmbargoAssertion) -> None: ...

    def list_by_property(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> list[PropertyEnvironmentalEmbargoAssertion]: ...


@dataclass(frozen=True, slots=True)
class EnvironmentalEmbargoAssertionService:
    assessment_service: EnvironmentalEmbargoAssessmentPort
    repository: PropertyEnvironmentalEmbargoAssertionRepositoryPort
    recorder: LivestockEventRecorder

    def record_ibama_assertion(
        self,
        context: LivestockOperationContext,
        property_id: TypedId,
    ) -> PropertyEnvironmentalEmbargoAssertion:
        assessment = self.assessment_service.assess_ibama_embargoes(
            context.organization_id,
            property_id,
        )
        assertion = PropertyEnvironmentalEmbargoAssertion.create(
            organization_id=context.organization_id,
            property_id=assessment.property_id,
            geometry_id=assessment.geometry_id,
            geometry_version=assessment.geometry_version,
            source_name=assessment.source,
            source_layer=assessment.layer,
            operation=assessment.operation,
            status=_status_from_assessment(assessment.status),
            source_digest=assessment.source_digest,
            response_digest=assessment.response_digest,
            version_ids=assessment.version_ids,
            restrictions_payload=tuple(
                {
                    "source": item.source,
                    "layer": item.layer,
                    "feature_id": item.feature_id,
                    "version_id": item.version_id,
                    "polygon_digest": item.polygon_digest,
                    "attributes": dict(item.attributes),
                }
                for item in assessment.restrictions
            ),
            observed_at=self.recorder.clock.now(),
        )
        self.repository.save(assertion)
        self.recorder.record(
            context=context,
            aggregate_id=assertion.assertion_id,
            event_type=PROPERTY_ENVIRONMENTAL_EMBARGO_ASSERTION_RECORDED,
            payload=property_environmental_embargo_assertion_recorded_payload(
                assertion_id=assertion.assertion_id,
                property_id=assertion.property_id,
                geometry_id=assertion.geometry_id,
                geometry_version=assertion.geometry_version,
                source_name=assertion.source_name,
                source_layer=assertion.source_layer,
                operation=assertion.operation,
                status=assertion.status.value,
                source_digest=assertion.source_digest,
                response_digest=assertion.response_digest,
                version_ids=assertion.version_ids,
                restriction_count=assertion.restriction_count,
                observed_at=assertion.observed_at,
            ),
            occurred_at=assertion.observed_at,
        )
        return assertion

    def list_for_property(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> list[PropertyEnvironmentalEmbargoAssertion]:
        return self.repository.list_by_property(organization_id, property_id)


def _status_from_assessment(
    status: EnvironmentalEmbargoStatus,
) -> EnvironmentalEmbargoAssertionStatus:
    if status is EnvironmentalEmbargoStatus.COM_RESTRICAO:
        return EnvironmentalEmbargoAssertionStatus.COM_RESTRICAO
    if status is EnvironmentalEmbargoStatus.SEM_RESTRICAO:
        return EnvironmentalEmbargoAssertionStatus.SEM_RESTRICAO
    return EnvironmentalEmbargoAssertionStatus.INDETERMINADA
