"""Registro append-only de captura simulada, sem produzir fatos ou coverage."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_application.sisbov_simulator import (
    SisbovSimulatorCapture,
    SisbovSimulatorParseResult,
    SisbovSimulatorTransportPort,
)
from packages.livestock_domain.external_source_capture import (
    ExternalSourceCaptureArtifact,
    ExternalSourceCaptureAssociationReview,
    ExternalSourceCaptureAssociationReviewStatus,
)
from packages.shared_kernel import OrganizationId, TypedId


class ExternalSourceCaptureArtifactRepositoryPort(Protocol):
    def save(self, artifact: ExternalSourceCaptureArtifact) -> None: ...

    def list_by_organization(
        self, organization_id: OrganizationId
    ) -> list[ExternalSourceCaptureArtifact]: ...


class ExternalSourceCaptureAssociationReviewRepositoryPort(Protocol):
    def save(self, review: ExternalSourceCaptureAssociationReview) -> None: ...

    def list_by_capture(
        self, organization_id: OrganizationId, capture_artifact_id: TypedId
    ) -> list[ExternalSourceCaptureAssociationReview]: ...


@dataclass(frozen=True, slots=True)
class ExternalSourceCaptureService:
    repository: ExternalSourceCaptureArtifactRepositoryPort

    def record_simulated_capture(
        self,
        *,
        context: LivestockOperationContext,
        capture: SisbovSimulatorCapture,
        parsing: SisbovSimulatorParseResult,
    ) -> ExternalSourceCaptureArtifact:
        request_scope_digest = sha256(
            f"{capture.request.resource.value}:{capture.request.lookup_value}".encode()
        ).hexdigest()
        artifact = ExternalSourceCaptureArtifact.create(
            organization_id=context.organization_id,
            contract_version="SISBOV_SIMULATOR_CAPTURE/v1",
            resource_kind=capture.request.resource.value,
            request_scope_digest=request_scope_digest,
            transport_outcome=capture.status.value,
            response_status_code=capture.response_status_code,
            response_digest=capture.response_digest,
            captured_at=capture.captured_at,
            parser_name="SisbovSimulatorParser",
            parser_version="1",
            parsing_diagnostic_code=parsing.diagnostic_code,
            recorded_by=context.actor_reference.target_id,
            review_projection=parsing.review_projection(),
        )
        self.repository.save(artifact)
        return artifact


@dataclass(frozen=True, slots=True)
class SisbovSimulatorIngestionService:
    transport: SisbovSimulatorTransportPort
    capture_service: ExternalSourceCaptureService

    def capture_animal(
        self, *, context: LivestockOperationContext, numero: str
    ) -> ExternalSourceCaptureArtifact:
        from packages.livestock_application.sisbov_simulator import (
            SisbovSimulatorCaptureService,
            SisbovSimulatorParser,
            SisbovSimulatorRequest,
        )

        capture = SisbovSimulatorCaptureService(self.transport).capture(
            SisbovSimulatorRequest.animal(numero)
        )
        return self.capture_service.record_simulated_capture(
            context=context, capture=capture, parsing=SisbovSimulatorParser().parse(capture)
        )


@dataclass(frozen=True, slots=True)
class ExternalSourceCaptureReviewService:
    artifact_repository: ExternalSourceCaptureArtifactRepositoryPort
    review_repository: ExternalSourceCaptureAssociationReviewRepositoryPort

    def review_candidate(
        self,
        *,
        context: LivestockOperationContext,
        capture_artifact_id: TypedId,
        candidate_animal_id: TypedId,
        status: ExternalSourceCaptureAssociationReviewStatus,
        basis_code: str,
    ) -> ExternalSourceCaptureAssociationReview:
        captures = self.artifact_repository.list_by_organization(context.organization_id)
        if not any(item.artifact_id == capture_artifact_id for item in captures):
            raise KeyError("Captura não encontrada na Organization ativa.")
        review = ExternalSourceCaptureAssociationReview(
            review_id=TypedId.new("external_source_capture_association_review"),
            organization_id=context.organization_id,
            capture_artifact_id=capture_artifact_id,
            candidate_animal_id=candidate_animal_id,
            status=status,
            basis_code=basis_code,
            reviewed_by=context.actor_reference.target_id,
        )
        self.review_repository.save(review)
        return review
