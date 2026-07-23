"""Testes unitários para TreatmentApplicationService (Passo 9.3 - Titan Livestock)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.medication_service import (
    MedicationBatchRepositoryPort,
    PrescriptionRepositoryPort,
)
from packages.livestock_application.treatment_service import (
    TreatmentApplicationRepositoryPort,
    TreatmentApplicationService,
)
from packages.livestock_domain.animal import Animal, AnimalSex, IdentifierType
from packages.livestock_domain.medication import MedicationBatch
from packages.livestock_domain.prescription import Prescription
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId


class InMemoryApplicationRepo(TreatmentApplicationRepositoryPort):
    def __init__(self) -> None:
        self.apps: dict[str, TreatmentApplication] = {}

    def save(self, application: TreatmentApplication) -> None:
        self.apps[application.application_id.value.hex] = application

    def get_by_id(self, application_id: TypedId) -> TreatmentApplication | None:
        return self.apps.get(application_id.value.hex)

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[TreatmentApplication]:
        return [
            a
            for a in self.apps.values()
            if a.organization_id == organization_id and a.animal_id == animal_id
        ]

    def list_by_batch(
        self, organization_id: OrganizationId, medication_batch_id: TypedId
    ) -> list[TreatmentApplication]:
        return [
            a
            for a in self.apps.values()
            if a.organization_id == organization_id and a.medication_batch_id == medication_batch_id
        ]


class InMemoryAnimalRepo(AnimalRepositoryPort):
    def __init__(self, animals: dict[str, Animal]) -> None:
        self.animals = animals

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

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Animal]:
        return list(self.animals.values())


class InMemoryBatchRepo(MedicationBatchRepositoryPort):
    def __init__(self, batches: dict[str, MedicationBatch]) -> None:
        self.batches = batches

    def save(self, batch: MedicationBatch) -> None:
        self.batches[batch.batch_id.value.hex] = batch

    def get_by_id(self, batch_id: TypedId) -> MedicationBatch | None:
        return self.batches.get(batch_id.value.hex)

    def get_by_number(
        self, organization_id: OrganizationId, medication_id: TypedId, batch_number: str
    ) -> MedicationBatch | None:
        return None

    def list_by_medication(
        self, organization_id: OrganizationId, medication_id: TypedId
    ) -> list[MedicationBatch]:
        return list(self.batches.values())


class InMemoryPrescriptionRepo(PrescriptionRepositoryPort):
    def __init__(self) -> None:
        self.prescriptions: dict[str, Prescription] = {}

    def save(self, prescription: Prescription) -> None:
        self.prescriptions[prescription.prescription_id.value.hex] = prescription

    def get_by_id(self, prescription_id: TypedId) -> Prescription | None:
        return self.prescriptions.get(prescription_id.value.hex)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Prescription]:
        return list(self.prescriptions.values())


def _scenario() -> tuple[
    TreatmentApplicationService, OrganizationId, TypedId, TypedId, InMemoryApplicationRepo
]:
    org_id = OrganizationId(uuid4())
    animal = Animal(
        animal_id=TypedId.new("animal"),
        organization_id=org_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.FEMALE,
    )
    batch = MedicationBatch(
        batch_id=TypedId.new("medication_batch"),
        organization_id=org_id,
        medication_id=TypedId.new("medication"),
        batch_number="LOTE-1",
        expiry_date=datetime.now(UTC) + timedelta(days=200),
    )
    app_repo = InMemoryApplicationRepo()
    service = TreatmentApplicationService(
        application_repository=app_repo,
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        batch_repository=InMemoryBatchRepo({batch.batch_id.value.hex: batch}),
        prescription_repository=InMemoryPrescriptionRepo(),
    )
    return service, org_id, animal.animal_id, batch.batch_id, app_repo


def test_register_application_success() -> None:
    service, org_id, animal_id, batch_id, _ = _scenario()

    app = service.register_application(
        organization_id=org_id,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        actor_id=TypedId.new("actor"),
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        dose="1 mL",
        evidence_references=("evidence:foto",),
    )
    assert app.corrects_application_id is None
    assert app.animal_id == animal_id


def test_correction_creates_new_record_preserving_original() -> None:
    """O cenário do plano: não se edita; corrige-se por um novo evento."""
    service, org_id, animal_id, batch_id, app_repo = _scenario()

    original = service.register_application(
        organization_id=org_id,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        actor_id=TypedId.new("actor"),
        applied_at=datetime.now(UTC) - timedelta(hours=2),
        dose="1 mL",
    )

    correction = service.correct_application(
        organization_id=org_id,
        original_application_id=original.application_id,
        actor_id=TypedId.new("actor"),
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        dose="2 mL",  # a dose correta
    )

    # A correção é um NOVO registro que aponta para o original.
    assert correction.application_id != original.application_id
    assert correction.corrects_application_id == original.application_id
    assert correction.animal_id == original.animal_id
    assert correction.medication_batch_id == original.medication_batch_id

    # Ambos permanecem: o histórico só cresce, o original é imutável.
    assert app_repo.get_by_id(original.application_id) is not None
    assert app_repo.get_by_id(original.application_id).dose == "1 mL"  # type: ignore[union-attr]
    assert len(app_repo.apps) == 2


def test_register_application_rejects_future_time() -> None:
    service, org_id, animal_id, batch_id, _ = _scenario()

    with pytest.raises(ValueError, match="não pode ser no futuro"):
        service.register_application(
            organization_id=org_id,
            animal_id=animal_id,
            medication_batch_id=batch_id,
            actor_id=TypedId.new("actor"),
            applied_at=datetime.now(UTC) + timedelta(days=1),
        )


def test_register_application_rejects_unknown_batch() -> None:
    service, org_id, animal_id, _, _ = _scenario()

    with pytest.raises(KeyError, match="Lote"):
        service.register_application(
            organization_id=org_id,
            animal_id=animal_id,
            medication_batch_id=TypedId.new("medication_batch"),
            actor_id=TypedId.new("actor"),
            applied_at=datetime.now(UTC),
        )
