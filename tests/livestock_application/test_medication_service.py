"""Testes unitários para MedicationService (Passo 9.1 - Titan Livestock)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.medication_service import (
    MedicationBatchRepositoryPort,
    MedicationBatchService,
    MedicationRepositoryPort,
    MedicationService,
    PrescriptionRepositoryPort,
)
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.veterinarian_service import VeterinarianRepositoryPort
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.events import (
    MEDICATION_BATCH_REGISTERED,
    MEDICATION_REGISTERED,
    PRESCRIPTION_ISSUED,
)
from packages.livestock_domain.medication import (
    Medication,
    MedicationBatch,
    MedicationProductClass,
)
from packages.livestock_domain.prescription import Prescription, PrescriptionTargetType
from packages.livestock_domain.property import RuralProperty
from packages.livestock_domain.veterinarian import Veterinarian
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog


class InMemoryMedicationRepo(MedicationRepositoryPort):
    def __init__(self) -> None:
        self.meds: dict[str, Medication] = {}

    def save(self, medication: Medication) -> None:
        self.meds[medication.medication_id.value.hex] = medication

    def get_by_id(self, medication_id: TypedId) -> Medication | None:
        return self.meds.get(medication_id.value.hex)

    def get_by_trade_name(
        self, organization_id: OrganizationId, trade_name: str
    ) -> Medication | None:
        for m in self.meds.values():
            if m.organization_id == organization_id and m.trade_name == trade_name:
                return m
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Medication]:
        return [m for m in self.meds.values() if m.organization_id == organization_id]


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
        return [p for p in self.prescriptions.values() if p.organization_id == organization_id]


class InMemoryVetRepo(VeterinarianRepositoryPort):
    def __init__(self) -> None:
        self.vets: dict[str, Veterinarian] = {}

    def save(self, vet: Veterinarian) -> None:
        self.vets[vet.veterinarian_id.value.hex] = vet

    def update(self, vet: Veterinarian) -> None:
        self.vets[vet.veterinarian_id.value.hex] = vet

    def get_by_id(self, vet_id: TypedId) -> Veterinarian | None:
        return self.vets.get(vet_id.value.hex)

    def get_by_cpf(self, organization_id: OrganizationId, cpf: str) -> Veterinarian | None:
        return None

    def get_by_council(
        self, organization_id: OrganizationId, state: str, number: str
    ) -> Veterinarian | None:
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Veterinarian]:
        return list(self.vets.values())


class InMemoryPropRepo(RuralPropertyRepositoryPort):
    def __init__(self) -> None:
        self.props: dict[str, RuralProperty] = {}

    def save(self, property: RuralProperty) -> None:
        self.props[property.property_id.value.hex] = property

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None:
        return self.props.get(property_id.value.hex)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        return list(self.props.values())


class InMemoryBatchRepo(MedicationBatchRepositoryPort):
    def __init__(self) -> None:
        self.batches: dict[str, MedicationBatch] = {}

    def save(self, batch: MedicationBatch) -> None:
        self.batches[batch.batch_id.value.hex] = batch

    def get_by_id(self, batch_id: TypedId) -> MedicationBatch | None:
        return self.batches.get(batch_id.value.hex)

    def get_by_number(
        self, organization_id: OrganizationId, medication_id: TypedId, batch_number: str
    ) -> MedicationBatch | None:
        for b in self.batches.values():
            if (
                b.organization_id == organization_id
                and b.medication_id == medication_id
                and b.batch_number == batch_number
            ):
                return b
        return None

    def list_by_medication(
        self, organization_id: OrganizationId, medication_id: TypedId
    ) -> list[MedicationBatch]:
        return [
            b
            for b in self.batches.values()
            if b.organization_id == organization_id and b.medication_id == medication_id
        ]


def _batch_scenario(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> tuple[MedicationBatchService, TypedId]:
    med_repo = InMemoryMedicationRepo()
    batch_repo = InMemoryBatchRepo()
    med = Medication(
        medication_id=TypedId.new("medication"),
        organization_id=context.organization_id,
        trade_name="Ivomec Gold",
        active_ingredient="Ivermectina",
        manufacturer="Boehringer",
        withdrawal_period_days=122,
    )
    med_repo.save(med)
    service = MedicationBatchService(
        batch_repository=batch_repo, medication_repository=med_repo, recorder=recorder
    )
    return service, med.medication_id


def test_register_batch_and_rejects_duplicate(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, med_id = _batch_scenario(recorder, context)

    batch = service.register_batch(
        context=context,
        medication_id=med_id,
        batch_number="LOTE-2026-001",
        expiry_date=datetime.now(UTC) + timedelta(days=365),
        manufacturing_date=datetime.now(UTC) - timedelta(days=30),
    )
    assert batch.batch_number == "LOTE-2026-001"

    with pytest.raises(ValueError, match="Já existe o lote"):
        service.register_batch(
            context=context,
            medication_id=med_id,
            batch_number="LOTE-2026-001",
            expiry_date=datetime.now(UTC) + timedelta(days=400),
        )

    event = event_log.only(MEDICATION_BATCH_REGISTERED)
    assert event.aggregate_reference.target_id == batch.batch_id
    assert b"LOTE-2026-001" in event.payload.canonical_bytes


def test_register_batch_rejects_invalid_validity(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, med_id = _batch_scenario(recorder, context)

    with pytest.raises(ValueError, match="expiry_date deve ser estritamente posterior"):
        service.register_batch(
            context=context,
            medication_id=med_id,
            batch_number="LOTE-VENCIDO",
            expiry_date=datetime.now(UTC) - timedelta(days=10),
            manufacturing_date=datetime.now(UTC),
        )

    assert event_log.events == [], "Lote recusado não pode deixar evento no log."


def test_register_batch_rejects_unknown_medication(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, _ = _batch_scenario(recorder, context)

    with pytest.raises(KeyError, match="não encontrado"):
        service.register_batch(
            context=context,
            medication_id=TypedId.new("medication"),
            batch_number="LOTE-X",
            expiry_date=datetime.now(UTC) + timedelta(days=100),
        )

    assert event_log.events == []


def test_prescription_issuance_verification_rules(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    org_id = context.organization_id
    vet_repo = InMemoryVetRepo()
    med_repo = InMemoryMedicationRepo()
    presc_repo = InMemoryPrescriptionRepo()
    prop_repo = InMemoryPropRepo()

    service = MedicationService(
        medication_repository=med_repo,
        prescription_repository=presc_repo,
        veterinarian_repository=vet_repo,
        property_repository=prop_repo,
        recorder=recorder,
    )

    prop_id = TypedId.new("rural_property")
    prop_repo.save(
        RuralProperty(
            property_id=prop_id,
            organization_id=org_id,
            code="P-01",
            name="Fazenda 1",
            municipality="SP",
            state_code="SP",
        )
    )

    med = service.register_medication(
        context=context,
        trade_name="Ivomec Gold",
        active_ingredient="Ivermectina",
        manufacturer="Boehringer",
        withdrawal_period_days=122,
    )

    # 1. Veterinário apenas DECLARADO (Deve ser recusado ao emitir prescrição)
    vet_decl = Veterinarian(
        veterinarian_id=TypedId.new("veterinarian"),
        organization_id=org_id,
        name="Dr. Não Verificado",
        cpf="11122233344",
        council_number="123",
        council_state="SP",
        verification_status=VerificationStatus.DECLARADO,
    )
    vet_repo.save(vet_decl)

    animal_id = TypedId.new("animal")

    with pytest.raises(ValueError, match="Para emitir prescrições é necessário estar DOCUMENTADO"):
        service.issue_prescription(
            context=context,
            veterinarian_id=vet_decl.veterinarian_id,
            medication_id=med.medication_id,
            property_id=prop_id,
            dosage="1 mL / 50 kg",
            administration_route="SUBCUTANEOUS",
            target_type=PrescriptionTargetType.ANIMAL,
            target_ids=(animal_id,),
            reason="Controle sanitário",
        )

    # 2. Veterinário DOCUMENTADO (Deve ser aceito)
    vet_doc = Veterinarian(
        veterinarian_id=TypedId.new("veterinarian"),
        organization_id=org_id,
        name="Dr. Verificado",
        cpf="55566677788",
        council_number="456",
        council_state="SP",
        verification_status=VerificationStatus.DOCUMENTADO,
    )
    vet_repo.save(vet_doc)

    presc = service.issue_prescription(
        context=context,
        veterinarian_id=vet_doc.veterinarian_id,
        medication_id=med.medication_id,
        property_id=prop_id,
        dosage="1 mL / 50 kg",
        administration_route="SUBCUTANEOUS",
        target_type=PrescriptionTargetType.ANIMAL,
        target_ids=(animal_id,),
        reason="Controle sanitário",
    )

    assert presc.prescription_id is not None
    # A prescrição recusada não deixou rastro; a emitida deixou, no fluxo dela.
    assert event_log.types() == [MEDICATION_REGISTERED, PRESCRIPTION_ISSUED]
    issued = event_log.only(PRESCRIPTION_ISSUED)
    assert issued.aggregate_reference.target_id == presc.prescription_id
    assert issued.aggregate_reference.organization_id == org_id
    assert str(animal_id.value).encode() in issued.payload.canonical_bytes


def test_medication_event_freezes_the_withdrawal_period_declared_at_registration(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """É o valor que o Passo 9.4 congela no cálculo — o evento precisa preservá-lo."""
    service = MedicationService(
        medication_repository=InMemoryMedicationRepo(),
        prescription_repository=InMemoryPrescriptionRepo(),
        veterinarian_repository=InMemoryVetRepo(),
        property_repository=InMemoryPropRepo(),
        recorder=recorder,
    )

    med = service.register_medication(
        context=context,
        trade_name="Ivomec Gold",
        active_ingredient="Ivermectina",
        manufacturer="Boehringer",
        withdrawal_period_days=122,
    )

    event = event_log.only(MEDICATION_REGISTERED)
    assert event.aggregate_reference.target_id == med.medication_id
    assert b"122" in event.payload.canonical_bytes


def test_medication_registration_accepts_immunobiological_classification(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service = MedicationService(
        medication_repository=InMemoryMedicationRepo(),
        prescription_repository=InMemoryPrescriptionRepo(),
        veterinarian_repository=InMemoryVetRepo(),
        property_repository=InMemoryPropRepo(),
        recorder=recorder,
    )

    med = service.register_medication(
        context=context,
        trade_name="Vacina Clostridial",
        active_ingredient="Antigenos clostridiais",
        manufacturer="Lab Saude Animal",
        withdrawal_period_days=0,
        product_class=MedicationProductClass.IMMUNOBIOLOGICAL,
    )

    event = event_log.only(MEDICATION_REGISTERED)
    assert med.product_class == MedicationProductClass.IMMUNOBIOLOGICAL
    assert b"IMMUNOBIOLOGICAL" in event.payload.canonical_bytes
