"""Serviço de aplicação MedicationService (Passo 9.1 - Titan Livestock)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.veterinarian_service import VeterinarianRepositoryPort
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.events import (
    MEDICATION_BATCH_REGISTERED,
    MEDICATION_REGISTERED,
    PRESCRIPTION_ISSUED,
    medication_batch_registered_payload,
    medication_registered_payload,
    prescription_issued_payload,
)
from packages.livestock_domain.medication import (
    Medication,
    MedicationBatch,
    MedicationProductClass,
)
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
    recorder: LivestockEventRecorder

    def register_batch(
        self,
        context: LivestockOperationContext,
        medication_id: TypedId,
        batch_number: str,
        expiry_date: datetime,
        manufacturing_date: datetime | None = None,
    ) -> MedicationBatch:
        organization_id = context.organization_id
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

        created_at = datetime.now(UTC)
        batch = MedicationBatch(
            batch_id=TypedId.new("medication_batch"),
            organization_id=organization_id,
            medication_id=medication_id,
            batch_number=number,
            expiry_date=expiry_date,
            manufacturing_date=manufacturing_date,
            created_at=created_at,
        )
        self.batch_repository.save(batch)
        self.recorder.record(
            context=context,
            aggregate_id=batch.batch_id,
            event_type=MEDICATION_BATCH_REGISTERED,
            payload=medication_batch_registered_payload(
                batch_id=batch.batch_id,
                medication_id=batch.medication_id,
                batch_number=batch.batch_number,
                expiry_date=batch.expiry_date,
                manufacturing_date=batch.manufacturing_date,
            ),
            occurred_at=created_at,
        )
        return batch


@dataclass(frozen=True, slots=True)
class MedicationService:
    medication_repository: MedicationRepositoryPort
    prescription_repository: PrescriptionRepositoryPort
    veterinarian_repository: VeterinarianRepositoryPort
    property_repository: RuralPropertyRepositoryPort
    recorder: LivestockEventRecorder

    def register_medication(
        self,
        context: LivestockOperationContext,
        trade_name: str,
        active_ingredient: str,
        manufacturer: str,
        withdrawal_period_days: int,
        product_class: MedicationProductClass = MedicationProductClass.PHARMACOLOGICAL,
        dosage_instruction: str | None = None,
    ) -> Medication:
        organization_id = context.organization_id
        t_name = trade_name.strip()
        existing = self.medication_repository.get_by_trade_name(organization_id, t_name)
        if existing is not None:
            raise ValueError(
                f"Já existe um medicamento cadastrado com o nome '{t_name}' para a "
                f"organização {organization_id.value}."
            )

        created_at = datetime.now(UTC)
        medication = Medication(
            medication_id=TypedId.new("medication"),
            organization_id=organization_id,
            trade_name=t_name,
            active_ingredient=active_ingredient.strip(),
            manufacturer=manufacturer.strip(),
            withdrawal_period_days=withdrawal_period_days,
            product_class=product_class,
            dosage_instruction=dosage_instruction,
            created_at=created_at,
        )

        self.medication_repository.save(medication)
        # A carência declarada aqui é o que o Passo 9.4 congela no cálculo: o
        # evento preserva o valor vigente no cadastro, não o de uma releitura.
        self.recorder.record(
            context=context,
            aggregate_id=medication.medication_id,
            event_type=MEDICATION_REGISTERED,
            payload=medication_registered_payload(
                medication_id=medication.medication_id,
                trade_name=medication.trade_name,
                active_ingredient=medication.active_ingredient,
                manufacturer=medication.manufacturer,
                withdrawal_period_days=medication.withdrawal_period_days,
                product_class=medication.product_class.value,
            ),
            occurred_at=created_at,
        )
        return medication

    def issue_prescription(
        self,
        context: LivestockOperationContext,
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
        organization_id = context.organization_id
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
        self.recorder.record(
            context=context,
            aggregate_id=prescription.prescription_id,
            event_type=PRESCRIPTION_ISSUED,
            payload=prescription_issued_payload(
                prescription_id=prescription.prescription_id,
                veterinarian_id=prescription.veterinarian_id,
                medication_id=prescription.medication_id,
                property_id=prescription.property_id,
                prescribed_date=prescription.prescribed_date,
                target_type=prescription.target_type.value,
                target_ids=prescription.target_ids,
                dosage=prescription.dosage,
                administration_route=prescription.administration_route,
                reason=prescription.reason,
            ),
            occurred_at=prescription.prescribed_date,
        )
        return prescription
