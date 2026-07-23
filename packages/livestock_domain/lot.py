"""Entidades de domínio LivestockLot e LotMembership (Passo 8.4 - Titan Livestock)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId


class LotType(StrEnum):
    OPERATIONAL = "OPERATIONAL"
    SANITARY = "SANITARY"
    COMMERCIAL = "COMMERCIAL"
    OTHER = "OTHER"


class LotStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class LotMembership:
    membership_id: TypedId
    lot_id: TypedId
    animal_id: TypedId
    valid_from: datetime = datetime.now(UTC)
    valid_until: datetime | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.membership_id.entity_type != "lot_membership":
            raise ValueError(
                "membership_id deve ter entity_type 'lot_membership', recebido "
                f"'{self.membership_id.entity_type}'."
            )
        if self.lot_id.entity_type != "livestock_lot":
            raise ValueError(
                "lot_id deve ter entity_type 'livestock_lot', recebido "
                f"'{self.lot_id.entity_type}'."
            )
        if self.animal_id.entity_type != "animal":
            raise ValueError(
                f"animal_id deve ter entity_type 'animal', recebido '{self.animal_id.entity_type}'."
            )

        if self.valid_until is not None:
            v_from = (
                self.valid_from.replace(tzinfo=UTC)
                if self.valid_from.tzinfo is None
                else self.valid_from
            )
            v_until = (
                self.valid_until.replace(tzinfo=UTC)
                if self.valid_until.tzinfo is None
                else self.valid_until
            )
            if v_until <= v_from:
                raise ValueError("valid_until deve ser estritamente posterior a valid_from.")


@dataclass(frozen=True, slots=True)
class LivestockLot:
    lot_id: TypedId
    organization_id: OrganizationId
    property_id: TypedId
    code: str
    name: str
    lot_type: LotType = LotType.OPERATIONAL
    status: LotStatus = LotStatus.ACTIVE
    created_at: datetime = datetime.now(UTC)

    def __post_init__(self) -> None:
        if self.lot_id.entity_type != "livestock_lot":
            raise ValueError(
                "lot_id deve ter entity_type 'livestock_lot', recebido "
                f"'{self.lot_id.entity_type}'."
            )
        if self.property_id.entity_type != "rural_property":
            raise ValueError(
                "property_id deve ter entity_type 'rural_property', recebido "
                f"'{self.property_id.entity_type}'."
            )
        if not self.code or not self.code.strip():
            raise ValueError("code do lote não pode ser vazio.")
        if not self.name or not self.name.strip():
            raise ValueError("name do lote não pode ser vazio.")
