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
