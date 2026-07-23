"""Testes unitários para MedicationService (Passo 9.1 - Titan Livestock)."""

from uuid import uuid4

import pytest

from packages.livestock_application.medication_service import (
    MedicationRepositoryPort,
    MedicationService,
    PrescriptionRepositoryPort,
)
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.veterinarian_service import VeterinarianRepositoryPort
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.medication import Medication
from packages.livestock_domain.prescription import Prescription, PrescriptionTargetType
from packages.livestock_domain.property import RuralProperty
from packages.livestock_domain.veterinarian import Veterinarian
from packages.shared_kernel import OrganizationId, TypedId


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


def test_prescription_issuance_verification_rules() -> None:
    org_id = OrganizationId(uuid4())
    vet_repo = InMemoryVetRepo()
    med_repo = InMemoryMedicationRepo()
    presc_repo = InMemoryPrescriptionRepo()
    prop_repo = InMemoryPropRepo()

    service = MedicationService(
        medication_repository=med_repo,
        prescription_repository=presc_repo,
        veterinarian_repository=vet_repo,
        property_repository=prop_repo,
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
        organization_id=org_id,
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
            organization_id=org_id,
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
        organization_id=org_id,
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
