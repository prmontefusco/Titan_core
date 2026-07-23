"""Entidade de domínio Prescription (Passo 9.1 - Titan Livestock)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class PrescriptionTargetType(StrEnum):
    ANIMAL = "ANIMAL"
    LOT = "LOT"


@dataclass(frozen=True, slots=True)
class Prescription:
    prescription_id: TypedId
    organization_id: OrganizationId
    veterinarian_id: TypedId
    medication_id: TypedId
    property_id: TypedId
    prescribed_date: datetime
    dosage: str
    administration_route: str
    target_type: PrescriptionTargetType
    target_ids: tuple[TypedId, ...]
    reason: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.prescribed_date, field_name="prescribed_date")
        require_utc(self.created_at, field_name="created_at")
        if self.prescription_id.entity_type != "prescription":
            raise ValueError(
                "prescription_id deve ter entity_type 'prescription', recebido "
                f"'{self.prescription_id.entity_type}'."
            )
        if self.veterinarian_id.entity_type != "veterinarian":
            raise ValueError(
                "veterinarian_id deve ter entity_type 'veterinarian', recebido "
                f"'{self.veterinarian_id.entity_type}'."
            )
        if self.medication_id.entity_type != "medication":
            raise ValueError(
                "medication_id deve ter entity_type 'medication', recebido "
                f"'{self.medication_id.entity_type}'."
            )
        if self.property_id.entity_type != "rural_property":
            raise ValueError(
                "property_id deve ter entity_type 'rural_property', recebido "
                f"'{self.property_id.entity_type}'."
            )
        if not self.dosage or not self.dosage.strip():
            raise ValueError("dosage não pode ser vazia.")
        if not self.target_ids:
            raise ValueError("target_ids deve conter ao menos um elemento alvo.")
        if not self.reason or not self.reason.strip():
            raise ValueError("reason da prescrição não pode ser vazio.")
