"""Entidade de domínio Medication (Passo 9.1 - Titan Livestock)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


@dataclass(frozen=True, slots=True)
class Medication:
    medication_id: TypedId
    organization_id: OrganizationId
    trade_name: str
    active_ingredient: str
    manufacturer: str
    withdrawal_period_days: int
    dosage_instruction: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.created_at, field_name="created_at")
        if self.medication_id.entity_type != "medication":
            raise ValueError(
                "medication_id deve ter entity_type 'medication', recebido "
                f"'{self.medication_id.entity_type}'."
            )
        if not self.trade_name or not self.trade_name.strip():
            raise ValueError("trade_name não pode ser vazio.")
        if not self.active_ingredient or not self.active_ingredient.strip():
            raise ValueError("active_ingredient não pode ser vazio.")
        if self.withdrawal_period_days < 0:
            raise ValueError("withdrawal_period_days deve ser maior ou igual a zero.")


@dataclass(frozen=True, slots=True)
class MedicationBatch:
    """Lote fabricado de um Medication, rastreável para recall e carência.

    Imutável: um lote não é editado. É a unidade física que a TreatmentApplication
    referencia, de modo que um recall de lote consiga localizar os animais tratados.
    """

    batch_id: TypedId
    organization_id: OrganizationId
    medication_id: TypedId
    batch_number: str
    expiry_date: datetime
    manufacturing_date: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.expiry_date, field_name="expiry_date")
        require_utc(self.created_at, field_name="created_at")
        if self.batch_id.entity_type != "medication_batch":
            raise ValueError(
                "batch_id deve ter entity_type 'medication_batch', recebido "
                f"'{self.batch_id.entity_type}'."
            )
        if self.medication_id.entity_type != "medication":
            raise ValueError(
                "medication_id deve ter entity_type 'medication', recebido "
                f"'{self.medication_id.entity_type}'."
            )
        if not self.batch_number or not self.batch_number.strip():
            raise ValueError("batch_number não pode ser vazio.")
        if self.manufacturing_date is not None:
            require_utc(self.manufacturing_date, field_name="manufacturing_date")
            if self.expiry_date <= self.manufacturing_date:
                raise ValueError(
                    "expiry_date deve ser estritamente posterior a manufacturing_date."
                )
