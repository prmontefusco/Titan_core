"""Serviço de aplicação MedicationService (Passo 9.1 - Titan Livestock)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.veterinarian_service import VeterinarianRepositoryPort
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.medication import Medication, MedicationBatch
from packages.livestock_domain.prescription import Prescription, PrescriptionTargetType
from packages.shared_kernel import OrganizationId, TypedId


class MedicationRepositoryPort(Protocol):
    def save(self, medication: Medication) -> None: ...

    def get_by_id(self, medication_id: TypedId) -> Medication | None: ...

    def get_by_trade_name(
        self, organization_id: OrganizationId, trade_name: str
    ) -> Medication | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Medication]: ...


class PrescriptionRepositoryPort(Protocol):
    def save(self, prescription: Prescription) -> None: ...

    def get_by_id(self, prescription_id: TypedId) -> Prescription | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Prescription]: ...


class MedicationBatchRepositoryPort(Protocol):
    def save(self, batch: MedicationBatch) -> None: ...

    def get_by_id(self, batch_id: TypedId) -> MedicationBatch | None: ...

    def get_by_number(
        self, organization_id: OrganizationId, medication_id: TypedId, batch_number: str
    ) -> MedicationBatch | None: ...

    def list_by_medication(
        self, organization_id: OrganizationId, medication_id: TypedId
    ) -> list[MedicationBatch]: ...


@dataclass(frozen=True, slots=True)
class MedicationBatchService:
    """Cadastra lotes de medicamento, recusando duplicidade e validade inválida."""

    batch_repository: MedicationBatchRepositoryPort
    medication_repository: MedicationRepositoryPort

    def register_batch(
        self,
        organization_id: OrganizationId,
        medication_id: TypedId,
        batch_number: str,
        expiry_date: datetime,
        manufacturing_date: datetime | None = None,
    ) -> MedicationBatch:
        medication = self.medication_repository.get_by_id(medication_id)
        if medication is None or medication.organization_id != organization_id:
            raise KeyError(
                f"Medicamento '{medication_id.value}' não encontrado ou pertencente a "
                "outra organização."
            )

        number = batch_number.strip()
        existing = self.batch_repository.get_by_number(organization_id, medication_id, number)
        if existing is not None:
            raise ValueError(
                f"Já existe o lote '{number}' para o medicamento {medication_id.value} na "
                f"organização {organization_id.value}."
            )

        batch = MedicationBatch(
            batch_id=TypedId.new("medication_batch"),
            organization_id=organization_id,
            medication_id=medication_id,
            batch_number=number,
            expiry_date=expiry_date,
            manufacturing_date=manufacturing_date,
            created_at=datetime.now(UTC),
        )
        self.batch_repository.save(batch)
        return batch


@dataclass(frozen=True, slots=True)
class MedicationService:
    medication_repository: MedicationRepositoryPort
    prescription_repository: PrescriptionRepositoryPort
    veterinarian_repository: VeterinarianRepositoryPort
    property_repository: RuralPropertyRepositoryPort

    def register_medication(
        self,
        organization_id: OrganizationId,
        trade_name: str,
        active_ingredient: str,
        manufacturer: str,
        withdrawal_period_days: int,
        dosage_instruction: str | None = None,
    ) -> Medication:
        t_name = trade_name.strip()
        existing = self.medication_repository.get_by_trade_name(organization_id, t_name)
        if existing is not None:
            raise ValueError(
                f"Já existe um medicamento cadastrado com o nome '{t_name}' para a "
                f"organização {organization_id.value}."
            )

        medication = Medication(
            medication_id=TypedId.new("medication"),
            organization_id=organization_id,
            trade_name=t_name,
            active_ingredient=active_ingredient.strip(),
            manufacturer=manufacturer.strip(),
            withdrawal_period_days=withdrawal_period_days,
            dosage_instruction=dosage_instruction,
            created_at=datetime.now(UTC),
        )

        self.medication_repository.save(medication)
        return medication

    def issue_prescription(
        self,
        organization_id: OrganizationId,
        veterinarian_id: TypedId,
        medication_id: TypedId,
        property_id: TypedId,
        dosage: str,
        administration_route: str,
        target_type: PrescriptionTargetType,
        target_ids: tuple[TypedId, ...],
        reason: str,
        prescribed_date: datetime | None = None,
    ) -> Prescription:
        vet = self.veterinarian_repository.get_by_id(veterinarian_id)
        if vet is None or vet.organization_id != organization_id:
            raise KeyError(
                f"Veterinário '{veterinarian_id.value}' não encontrado ou pertencente a "
                "outra organização."
            )

        if vet.verification_status not in (
            VerificationStatus.DOCUMENTADO,
            VerificationStatus.VERIFICADO_EM_FONTE,
        ):
            raise ValueError(
                f"Veterinário '{vet.name}' possui status '{vet.verification_status.value}'. "
                "Para emitir prescrições é necessário estar DOCUMENTADO ou VERIFICADO_EM_FONTE."
            )

        med = self.medication_repository.get_by_id(medication_id)
        if med is None or med.organization_id != organization_id:
            raise KeyError(
                f"Medicamento '{medication_id.value}' não encontrado ou pertencente a "
                "outra organização."
            )

        prop = self.property_repository.get_by_id(property_id)
        if prop is None or prop.organization_id != organization_id:
            raise KeyError(
                f"Propriedade '{property_id.value}' não encontrada ou pertencente a "
                "outra organização."
            )

        p_date = prescribed_date if prescribed_date is not None else datetime.now(UTC)
        prescription = Prescription(
            prescription_id=TypedId.new("prescription"),
            organization_id=organization_id,
            veterinarian_id=veterinarian_id,
            medication_id=medication_id,
            property_id=property_id,
            prescribed_date=p_date,
            dosage=dosage.strip(),
            administration_route=administration_route.strip().upper(),
            target_type=target_type,
            target_ids=target_ids,
            reason=reason.strip(),
            created_at=datetime.now(UTC),
        )

        self.prescription_repository.save(prescription)
        return prescription
