from datetime import UTC, datetime, timedelta

import pytest

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.external_counterparty_service import (
    ExternalCounterpartyRepositoryPort,
)
from packages.livestock_application.transfer_artifact_service import (
    ReceivedTransferArtifactRepositoryPort,
    ReceivedTransferArtifactService,
)
from packages.livestock_domain.animal import Animal, AnimalSex, IdentifierType
from packages.livestock_domain.events import TRANSFER_ARTIFACT_RECEIVED
from packages.livestock_domain.exit import AnimalExit
from packages.livestock_domain.external_counterparty import CounterpartyType, ExternalCounterparty
from packages.livestock_domain.transfer_artifact import (
    ReceivedTransferArtifact,
    TransferArtifactGapCode,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog


class InMemoryAnimalRepo(AnimalRepositoryPort):
    def __init__(self) -> None:
        self.animals: dict[str, Animal] = {}

    def save(self, animal: Animal) -> None:
        self.animals[animal.animal_id.value.hex] = animal

    def update(self, animal: Animal) -> None:
        self.animals[animal.animal_id.value.hex] = animal

    def get_by_id(self, animal_id: TypedId) -> Animal | None:
        return self.animals.get(animal_id.value.hex)

    def find_by_identifier(
        self,
        organization_id: OrganizationId,
        identifier_type: IdentifierType,
        identifier_value: str,
    ) -> Animal | None:
        return None

    def get_exit(self, animal_id: TypedId) -> AnimalExit | None:
        return None

    def list_by_organization(
        self,
        organization_id: OrganizationId,
        limit: int = 50,
        offset: int = 0,
        identifier: str | None = None,
    ) -> list[Animal]:
        return list(self.animals.values())


class InMemoryCounterpartyRepo(ExternalCounterpartyRepositoryPort):
    def __init__(self) -> None:
        self.counterparties: dict[str, ExternalCounterparty] = {}

    def save(self, counterparty: ExternalCounterparty) -> None:
        self.counterparties[counterparty.counterparty_id.value.hex] = counterparty

    def get_by_id(self, counterparty_id: TypedId) -> ExternalCounterparty | None:
        return self.counterparties.get(counterparty_id.value.hex)

    def list_by_organization(self, organization_id: OrganizationId) -> list[ExternalCounterparty]:
        return [
            item for item in self.counterparties.values() if item.organization_id == organization_id
        ]


class InMemoryArtifactRepo(ReceivedTransferArtifactRepositoryPort):
    def __init__(self) -> None:
        self.artifacts: list[ReceivedTransferArtifact] = []

    def save(self, artifact: ReceivedTransferArtifact) -> None:
        self.artifacts.append(artifact)

    def get_by_id(self, artifact_id: TypedId) -> ReceivedTransferArtifact | None:
        return next(
            (item for item in self.artifacts if item.artifact_id == artifact_id),
            None,
        )

    def list_by_animal(self, animal_id: TypedId) -> list[ReceivedTransferArtifact]:
        return [item for item in self.artifacts if item.animal_id == animal_id]


def _service(
    recorder: LivestockEventRecorder,
    context: LivestockOperationContext,
) -> tuple[ReceivedTransferArtifactService, TypedId, TypedId]:
    animal_repo = InMemoryAnimalRepo()
    counterparty_repo = InMemoryCounterpartyRepo()
    artifact_repo = InMemoryArtifactRepo()
    animal = Animal(
        animal_id=TypedId.new("animal"),
        organization_id=context.organization_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.MALE,
    )
    animal_repo.save(animal)
    counterparty = ExternalCounterparty(
        counterparty_id=TypedId.new("external_counterparty"),
        organization_id=context.organization_id,
        name="Fazenda Origem",
        counterparty_type=CounterpartyType.FARM,
    )
    counterparty_repo.save(counterparty)
    return (
        ReceivedTransferArtifactService(
            repository=artifact_repo,
            animal_repository=animal_repo,
            counterparty_repository=counterparty_repo,
            recorder=recorder,
        ),
        animal.animal_id,
        counterparty.counterparty_id,
    )


def test_registra_artefato_recebido_com_lacuna_de_cobertura(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, counterparty_id = _service(recorder, context)
    transferencia = datetime.now(UTC) - timedelta(days=1)
    conhecido_ate = transferencia - timedelta(hours=8)

    artifact = service.register_received_artifact(
        context=context,
        animal_id=animal_id,
        source_counterparty_id=counterparty_id,
        bundle_digest="a" * 64,
        bundle_issued_at=conhecido_ate,
        transfer_effective_at=transferencia,
        coverage_known_from=transferencia - timedelta(days=100),
        coverage_known_until=conhecido_ate,
        issuer_name="Fazenda Origem",
    )

    assert artifact.coverage.gaps[0].code is TransferArtifactGapCode.COVERAGE_BEFORE_TRANSFER
    evento = event_log.only(TRANSFER_ARTIFACT_RECEIVED)
    assert evento.aggregate_reference.target_id == artifact.artifact_id


def test_artefato_nao_alcanca_contraparte_de_outra_organizacao(
    recorder: LivestockEventRecorder,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, _ = _service(recorder, context)
    intrusa = ExternalCounterparty(
        counterparty_id=TypedId.new("external_counterparty"),
        organization_id=OrganizationId.new(),
        name="Fazenda Fora",
        counterparty_type=CounterpartyType.FARM,
    )
    service.counterparty_repository.save(intrusa)

    with pytest.raises(KeyError, match="Contraparte"):
        service.register_received_artifact(
            context=context,
            animal_id=animal_id,
            source_counterparty_id=intrusa.counterparty_id,
            bundle_digest="b" * 64,
            bundle_issued_at=datetime.now(UTC) - timedelta(days=2),
            transfer_effective_at=datetime.now(UTC) - timedelta(days=1),
            coverage_known_from=None,
            coverage_known_until=None,
        )
