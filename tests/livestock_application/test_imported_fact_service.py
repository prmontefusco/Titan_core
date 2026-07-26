from datetime import UTC, datetime, timedelta

import pytest

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.imported_fact_service import (
    ImportedLivestockFactRepositoryPort,
    ImportedLivestockFactService,
)
from packages.livestock_domain.events import IMPORTED_FACT_RECORDED
from packages.livestock_domain.imported_fact import FactOrigin, ImportedLivestockFact
from packages.livestock_domain.transfer_artifact import (
    HistoryCoverage,
    ReceivedTransferArtifact,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog
from tests.livestock_application.test_transfer_artifact_service import (
    InMemoryAnimalRepo,
    InMemoryArtifactRepo,
)
from tests.livestock_application.test_transfer_artifact_service import (
    _service as transfer_service,
)


class InMemoryImportedFactRepo(ImportedLivestockFactRepositoryPort):
    def __init__(self) -> None:
        self.facts: list[ImportedLivestockFact] = []

    def save(self, fact: ImportedLivestockFact) -> None:
        self.facts.append(fact)

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[ImportedLivestockFact]:
        return [
            fact
            for fact in self.facts
            if fact.organization_id == organization_id and fact.animal_id == animal_id
        ]


def test_registra_fato_importado_preservando_artefato_origem_e_confianca(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service_artifact, animal_id, counterparty_id = transfer_service(recorder, context)
    transferencia = datetime.now(UTC) - timedelta(days=1)
    artifact = service_artifact.register_received_artifact(
        context=context,
        animal_id=animal_id,
        source_counterparty_id=counterparty_id,
        bundle_digest="a" * 64,
        bundle_issued_at=transferencia,
        transfer_effective_at=transferencia,
        coverage_known_from=transferencia - timedelta(days=200),
        coverage_known_until=transferencia,
    )
    imported_repo = InMemoryImportedFactRepo()
    service = ImportedLivestockFactService(
        repository=imported_repo,
        artifact_repository=service_artifact.repository,
        animal_repository=service_artifact.animal_repository,
        recorder=recorder,
    )

    fact = service.record_imported_fact(
        context=context,
        animal_id=animal_id,
        source_artifact_id=artifact.artifact_id,
        fact_type="livestock.treatment_applied",
        occurred_at=transferencia - timedelta(days=30),
        asserted_by="Fazenda Origem",
        confidence_tier=ConfidenceTier.CRYPTOGRAPHICALLY_ATTESTED,
        payload={"withdrawal_period_days": 45},
    )

    assert fact.origin is FactOrigin.IMPORTED_ASSERTION
    assert fact.source_artifact_id == artifact.artifact_id
    assert event_log.only(IMPORTED_FACT_RECORDED).aggregate_reference.target_id == (
        fact.imported_fact_id
    )


def test_fato_importado_exige_artefato_do_mesmo_animal(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    animal_repo = InMemoryAnimalRepo()
    artifact_repo = InMemoryArtifactRepo()
    animal = TypedId.new("animal")
    outro_animal = TypedId.new("animal")
    from packages.livestock_domain.animal import Animal, AnimalSex

    animal_repo.save(
        Animal(
            animal_id=animal,
            organization_id=context.organization_id,
            birth_property_id=TypedId.new("rural_property"),
            sex=AnimalSex.MALE,
        )
    )
    artifact_repo.save(
        ReceivedTransferArtifact(
            artifact_id=TypedId.new("received_transfer_artifact"),
            organization_id=context.organization_id,
            animal_id=outro_animal,
            source_counterparty_id=TypedId.new("external_counterparty"),
            bundle_digest="b" * 64,
            bundle_issued_at=datetime.now(UTC) - timedelta(days=2),
            transfer_effective_at=datetime.now(UTC) - timedelta(days=1),
            coverage=HistoryCoverage.from_transfer(
                known_from=None,
                known_until=None,
                transfer_effective_at=datetime.now(UTC) - timedelta(days=1),
            ),
        )
    )
    service = ImportedLivestockFactService(
        repository=InMemoryImportedFactRepo(),
        artifact_repository=artifact_repo,
        animal_repository=animal_repo,
        recorder=recorder,
    )

    with pytest.raises(KeyError, match="Artefato"):
        service.record_imported_fact(
            context=context,
            animal_id=animal,
            source_artifact_id=artifact_repo.artifacts[0].artifact_id,
            fact_type="livestock.treatment_applied",
            occurred_at=datetime.now(UTC) - timedelta(days=3),
            asserted_by="Fazenda Origem",
            confidence_tier=ConfidenceTier.DOCUMENTED,
            payload={},
        )
