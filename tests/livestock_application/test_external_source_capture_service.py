"""Corte 2 do POST-LIV-03: persistível, mas sem efeitos de compliance."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

import pytest

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_application.external_source_capture_service import (
    ExternalSourceCaptureReviewService,
    ExternalSourceCaptureService,
    SisbovSimulatorIngestionService,
)
from packages.livestock_application.sisbov_simulator import (
    SisbovSimulatorCaptureService,
    SisbovSimulatorParser,
    SisbovSimulatorRequest,
    SisbovSimulatorTransportResponse,
)
from packages.livestock_domain.external_source_capture import (
    ExternalSourceCaptureArtifact,
    ExternalSourceCaptureAssociationReview,
    ExternalSourceCaptureAssociationReviewStatus,
)
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


@dataclass
class ReviewRepo:
    items: list[ExternalSourceCaptureAssociationReview] = field(default_factory=list)

    def save(self, review: ExternalSourceCaptureAssociationReview) -> None:
        self.items.append(review)

    def list_by_capture(
        self, organization_id: OrganizationId, capture_artifact_id: TypedId
    ) -> list[ExternalSourceCaptureAssociationReview]:
        return [item for item in self.items if item.capture_artifact_id == capture_artifact_id]


@dataclass(frozen=True)
class CandidateAnimal:
    organization_id: OrganizationId


@dataclass
class AnimalRepo:
    animal: CandidateAnimal | None

    def get_by_id(self, animal_id: TypedId) -> CandidateAnimal | None:
        return self.animal


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


def test_ingestao_interna_persiste_apenas_projecao_allowlisted() -> None:
    organization_id, actor_id = OrganizationId.new(), TypedId.new("actor")
    context = LivestockOperationContext(
        organization_id,
        UniversalReference(actor_id, organization_id, 1),
        UniversalReference(actor_id, organization_id, 1),
        TypedId.new("correlation"),
    )
    repo = Repo()
    artifact = SisbovSimulatorIngestionService(
        Transport(), ExternalSourceCaptureService(repo)
    ).capture_animal(context=context, numero="BR1")

    assert repo.items == [artifact]
    assert artifact.review_projection == {
        "resource_kind": "ANIMAL",
        "external_reference": "BR1",
        "declared_fields": {"statusAnimal": None, "ERASPropriedadeLocalizacao": None},
    }


def test_review_positiva_rejeita_captura_nao_parseada() -> None:
    organization_id, actor_id = OrganizationId.new(), TypedId.new("actor")
    context = LivestockOperationContext(
        organization_id,
        UniversalReference(actor_id, organization_id, 1),
        UniversalReference(actor_id, organization_id, 1),
        TypedId.new("correlation"),
    )
    artifact = ExternalSourceCaptureArtifact.create(
        organization_id=organization_id,
        contract_version="SISBOV_SIMULATOR_CAPTURE/v1",
        resource_kind="ANIMAL",
        request_scope_digest="a" * 64,
        transport_outcome="NOT_FOUND",
        response_status_code=404,
        response_digest=None,
        captured_at=NOW,
        parser_name="SisbovSimulatorParser",
        parser_version="1",
        parsing_diagnostic_code="CAPTURE_NOT_FOUND",
        recorded_by=actor_id,
    )
    candidate_animal_id = TypedId.new("animal")

    service = ExternalSourceCaptureReviewService(
        Repo([artifact]),
        ReviewRepo(),
        cast(AnimalRepositoryPort, AnimalRepo(CandidateAnimal(organization_id))),
    )

    with pytest.raises(ValueError, match="CONFIRMED_CANDIDATE"):
        service.review_candidate(
            context=context,
            capture_artifact_id=artifact.artifact_id,
            candidate_animal_id=candidate_animal_id,
            status=ExternalSourceCaptureAssociationReviewStatus.CONFIRMED_CANDIDATE,
            basis_code="OFFICIAL_SISBOV_MATCH",
        )


def test_review_negativa_permite_captura_nao_parseada() -> None:
    organization_id, actor_id = OrganizationId.new(), TypedId.new("actor")
    context = LivestockOperationContext(
        organization_id,
        UniversalReference(actor_id, organization_id, 1),
        UniversalReference(actor_id, organization_id, 1),
        TypedId.new("correlation"),
    )
    artifact = ExternalSourceCaptureArtifact.create(
        organization_id=organization_id,
        contract_version="SISBOV_SIMULATOR_CAPTURE/v1",
        resource_kind="ANIMAL",
        request_scope_digest="a" * 64,
        transport_outcome="NOT_FOUND",
        response_status_code=404,
        response_digest=None,
        captured_at=NOW,
        parser_name="SisbovSimulatorParser",
        parser_version="1",
        parsing_diagnostic_code="CAPTURE_NOT_FOUND",
        recorded_by=actor_id,
    )
    candidate_animal_id = TypedId.new("animal")
    reviews = ReviewRepo()

    result = ExternalSourceCaptureReviewService(
        Repo([artifact]),
        reviews,
        cast(AnimalRepositoryPort, AnimalRepo(CandidateAnimal(organization_id))),
    ).review_candidate(
        context=context,
        capture_artifact_id=artifact.artifact_id,
        candidate_animal_id=candidate_animal_id,
        status=ExternalSourceCaptureAssociationReviewStatus.NEEDS_MORE_EVIDENCE,
        basis_code="CAPTURE_NOT_FOUND",
    )

    assert reviews.items == [result]
