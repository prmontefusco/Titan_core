"""Vínculo humano temporal entre User e Organization."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Self

from packages.shared_kernel import OrganizationId, TypedId


class MembershipStatus(StrEnum):
    """Estados controlados do vínculo humano."""

    ATIVA = "ATIVA"
    SUSPENSA = "SUSPENSA"
    ENCERRADA = "ENCERRADA"
    SUBSTITUIDA = "SUBSTITUIDA"


def _require_utc(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} deve ser datetime.")
    offset = value.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError(f"{field_name} deve possuir timezone UTC.")


@dataclass(frozen=True, slots=True)
class Membership:
    """Vínculo humano owned pela Organization em que o User pode atuar."""

    membership_id: TypedId
    user_id: TypedId
    organization_id: OrganizationId
    record_owner_organization_id: OrganizationId
    valid_from: datetime
    valid_until: datetime | None
    status: MembershipStatus
    origin_reference: TypedId
    granted_by_actor_id: TypedId

    def __post_init__(self) -> None:
        if not isinstance(self.membership_id, TypedId):
            raise TypeError("membership_id deve ser um TypedId.")
        if self.membership_id.entity_type != "membership":
            raise ValueError("membership_id deve possuir tipo lógico 'membership'.")
        if not isinstance(self.user_id, TypedId):
            raise TypeError("user_id deve ser um TypedId.")
        if self.user_id.entity_type != "user":
            raise ValueError("user_id deve possuir tipo lógico 'user'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser um OrganizationId.")
        if not isinstance(self.record_owner_organization_id, OrganizationId):
            raise TypeError("record_owner_organization_id deve ser um OrganizationId.")
        if self.record_owner_organization_id != self.organization_id:
            raise ValueError("Membership deve ser owned pela Organization vinculada.")
        _require_utc(self.valid_from, "valid_from")
        if self.valid_until is not None:
            _require_utc(self.valid_until, "valid_until")
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until deve ser posterior a valid_from.")
        if not isinstance(self.status, MembershipStatus):
            raise TypeError("status deve ser um MembershipStatus.")
        if not isinstance(self.origin_reference, TypedId):
            raise TypeError("origin_reference deve ser um TypedId.")
        if not isinstance(self.granted_by_actor_id, TypedId):
            raise TypeError("granted_by_actor_id deve ser um TypedId.")
        if self.granted_by_actor_id.entity_type != "actor":
            raise ValueError("granted_by_actor_id deve possuir tipo lógico 'actor'.")

    @classmethod
    def create(
        cls,
        *,
        user_id: TypedId,
        organization_id: OrganizationId,
        valid_from: datetime,
        valid_until: datetime | None,
        origin_reference: TypedId,
        granted_by_actor_id: TypedId,
    ) -> Self:
        return cls(
            membership_id=TypedId.new("membership"),
            user_id=user_id,
            organization_id=organization_id,
            record_owner_organization_id=organization_id,
            valid_from=valid_from,
            valid_until=valid_until,
            status=MembershipStatus.ATIVA,
            origin_reference=origin_reference,
            granted_by_actor_id=granted_by_actor_id,
        )

    def is_valid_at(self, instant: datetime) -> bool:
        """Informa validade sem converter o resultado em autorização."""
        _require_utc(instant, "instant")
        return (
            self.status is MembershipStatus.ATIVA
            and self.valid_from <= instant
            and (self.valid_until is None or instant < self.valid_until)
        )
