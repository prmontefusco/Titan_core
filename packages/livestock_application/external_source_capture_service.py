"""Registro append-only de captura simulada, sem produzir fatos ou coverage."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_application.sisbov_simulator import (
    SisbovSimulatorCapture,
    SisbovSimulatorParseResult,
)
from packages.livestock_domain.external_source_capture import ExternalSourceCaptureArtifact
from packages.shared_kernel import OrganizationId


class ExternalSourceCaptureArtifactRepositoryPort(Protocol):
    def save(self, artifact: ExternalSourceCaptureArtifact) -> None: ...

    def list_by_organization(
        self, organization_id: OrganizationId
    ) -> list[ExternalSourceCaptureArtifact]: ...


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
        )
        self.repository.save(artifact)
        return artifact
