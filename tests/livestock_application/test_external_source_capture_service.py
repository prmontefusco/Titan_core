"""Corte 2 do POST-LIV-03: persistível, mas sem efeitos de compliance."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_application.external_source_capture_service import (
    ExternalSourceCaptureService,
)
from packages.livestock_application.sisbov_simulator import (
    SisbovSimulatorCaptureService,
    SisbovSimulatorParser,
    SisbovSimulatorRequest,
    SisbovSimulatorTransportResponse,
)
from packages.livestock_domain.external_source_capture import ExternalSourceCaptureArtifact
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

NOW = datetime(2026, 8, 12, tzinfo=UTC)


@dataclass
class Transport:
    def get(self, request: SisbovSimulatorRequest) -> SisbovSimulatorTransportResponse:
        return SisbovSimulatorTransportResponse(200, b'{"id":"e","numero":"BR1"}', NOW)


@dataclass
class Repo:
    items: list[ExternalSourceCaptureArtifact] = field(default_factory=list)

    def save(self, artifact: ExternalSourceCaptureArtifact) -> None:
        self.items.append(artifact)

    def list_by_organization(
        self, organization_id: OrganizationId
    ) -> list[ExternalSourceCaptureArtifact]:
        return [item for item in self.items if item.organization_id == organization_id]


def test_registro_preserva_captura_simulada_sem_produzir_fato() -> None:
    organization_id, actor_id = OrganizationId.new(), TypedId.new("actor")
    context = LivestockOperationContext(
        organization_id=organization_id,
        actor_reference=UniversalReference(actor_id, organization_id, 1),
        source_reference=UniversalReference(actor_id, organization_id, 1),
        correlation_id=TypedId.new("correlation"),
    )
    capture = SisbovSimulatorCaptureService(Transport()).capture(
        SisbovSimulatorRequest.animal("BR1")
    )
    parsed = SisbovSimulatorParser().parse(capture)
    repo = Repo()

    artifact = ExternalSourceCaptureService(repo).record_simulated_capture(
        context=context, capture=capture, parsing=parsed
    )

    assert repo.items == [artifact]
    assert artifact.source_environment.value == "SIMULATED"
    assert artifact.response_digest == capture.response_digest
    assert artifact.resource_kind == "ANIMAL"
