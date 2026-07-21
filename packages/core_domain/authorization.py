"""Papéis e permissões internos do Titan."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Self

from packages.shared_kernel import OrganizationId, TypedId

_PERMISSION_CODE = re.compile(r"^[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*$")


def _require_id(value: TypedId, entity_type: str, field_name: str) -> None:
    if not isinstance(value, TypedId):
        raise TypeError(f"{field_name} deve ser um TypedId.")
    if value.entity_type != entity_type:
        raise ValueError(f"{field_name} deve possuir tipo lógico '{entity_type}'.")


def _require_utc(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} deve ser datetime.")
    offset = value.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError(f"{field_name} deve possuir timezone UTC.")


@dataclass(frozen=True, slots=True)
class Permission:
    permission_id: TypedId
    record_owner_organization_id: OrganizationId
    code: str

    def __post_init__(self) -> None:
        _require_id(self.permission_id, "permission", "permission_id")
        if not isinstance(self.record_owner_organization_id, OrganizationId):
            raise TypeError("record_owner_organization_id deve ser OrganizationId.")
        if not isinstance(self.code, str):
            raise TypeError("code deve ser texto.")
        if not _PERMISSION_CODE.fullmatch(self.code):
            raise ValueError("code deve usar o formato RECURSO.ACAO em maiúsculas.")

    @classmethod
    def create(cls, *, operator_organization_id: OrganizationId, code: str) -> Self:
        return cls(TypedId.new("permission"), operator_organization_id, code)


@dataclass(frozen=True, slots=True)
class Role:
    role_id: TypedId
    organization_id: OrganizationId
    record_owner_organization_id: OrganizationId
    name: str
    permission_ids: tuple[TypedId, ...]

    def __post_init__(self) -> None:
        _require_id(self.role_id, "role", "role_id")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if self.record_owner_organization_id != self.organization_id:
            raise ValueError("Role deve ser owned pela Organization que o define.")
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 100:
            raise ValueError("name deve possuir entre 1 e 100 caracteres.")
        if not isinstance(self.permission_ids, tuple):
            raise TypeError("permission_ids deve ser tuple.")
        for permission_id in self.permission_ids:
            _require_id(permission_id, "permission", "permission_ids")
        if len(set(self.permission_ids)) != len(self.permission_ids):
            raise ValueError("permission_ids não pode conter duplicidade.")

    @classmethod
    def create(
        cls,
        *,
        organization_id: OrganizationId,
        name: str,
        permission_ids: tuple[TypedId, ...],
    ) -> Self:
        return cls(TypedId.new("role"), organization_id, organization_id, name, permission_ids)


@dataclass(frozen=True, slots=True)
class MembershipRoleAssignment:
    assignment_id: TypedId
    membership_id: TypedId
    role_id: TypedId
    organization_id: OrganizationId
    record_owner_organization_id: OrganizationId
    valid_from: datetime
    valid_until: datetime | None
    granted_by_actor_id: TypedId

    def __post_init__(self) -> None:
        _require_id(self.assignment_id, "membership_role_assignment", "assignment_id")
        _require_id(self.membership_id, "membership", "membership_id")
        _require_id(self.role_id, "role", "role_id")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if self.record_owner_organization_id != self.organization_id:
            raise ValueError("A atribuição deve ser owned pela Organization vinculada.")
        _require_utc(self.valid_from, "valid_from")
        if self.valid_until is not None:
            _require_utc(self.valid_until, "valid_until")
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until deve ser posterior a valid_from.")
        _require_id(self.granted_by_actor_id, "actor", "granted_by_actor_id")

    @classmethod
    def create(
        cls,
        *,
        membership_id: TypedId,
        role_id: TypedId,
        organization_id: OrganizationId,
        valid_from: datetime,
        valid_until: datetime | None,
        granted_by_actor_id: TypedId,
    ) -> Self:
        return cls(
            TypedId.new("membership_role_assignment"),
            membership_id,
            role_id,
            organization_id,
            organization_id,
            valid_from,
            valid_until,
            granted_by_actor_id,
        )


@dataclass(frozen=True, slots=True)
class MembershipRoleRevocation:
    revocation_id: TypedId
    assignment_id: TypedId
    organization_id: OrganizationId
    record_owner_organization_id: OrganizationId
    revoked_at: datetime
    revoked_by_actor_id: TypedId

    def __post_init__(self) -> None:
        _require_id(self.revocation_id, "membership_role_revocation", "revocation_id")
        _require_id(self.assignment_id, "membership_role_assignment", "assignment_id")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if self.record_owner_organization_id != self.organization_id:
            raise ValueError("A revogação deve preservar a Organization da atribuição.")
        _require_utc(self.revoked_at, "revoked_at")
        _require_id(self.revoked_by_actor_id, "actor", "revoked_by_actor_id")

    @classmethod
    def create(
        cls,
        *,
        assignment_id: TypedId,
        organization_id: OrganizationId,
        revoked_at: datetime,
        revoked_by_actor_id: TypedId,
    ) -> Self:
        return cls(
            TypedId.new("membership_role_revocation"),
            assignment_id,
            organization_id,
            organization_id,
            revoked_at,
            revoked_by_actor_id,
        )
