"""Identidade externa e contexto organizacional validado."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Self

from packages.core_domain.authentication import AuthenticatedPrincipal, PrincipalType
from packages.shared_kernel import OrganizationId, TypedId


class ExternalIdentityStatus(StrEnum):
    ATIVA = "ATIVA"
    SUSPENSA = "SUSPENSA"


def _require_typed_id(value: TypedId, entity_type: str, name: str) -> None:
    if not isinstance(value, TypedId):
        raise TypeError(f"{name} deve ser TypedId.")
    if value.entity_type != entity_type:
        raise ValueError(f"{name} deve possuir tipo lógico '{entity_type}'.")


def _require_utc(value: datetime, name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} deve ser datetime.")
    offset = value.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError(f"{name} deve possuir timezone UTC.")


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    external_identity_id: TypedId
    record_owner_organization_id: OrganizationId
    issuer: str
    subject: str
    principal_type: PrincipalType
    internal_principal_id: TypedId
    status: ExternalIdentityStatus
    linked_at: datetime
    linked_by_actor_id: TypedId

    def __post_init__(self) -> None:
        _require_typed_id(self.external_identity_id, "external_identity", "external_identity_id")
        if not isinstance(self.record_owner_organization_id, OrganizationId):
            raise TypeError("record_owner_organization_id deve ser OrganizationId.")
        if not isinstance(self.issuer, str) or not self.issuer:
            raise ValueError("issuer não pode ser vazio.")
        if not isinstance(self.subject, str) or not self.subject:
            raise ValueError("subject não pode ser vazio.")
        if self.principal_type is PrincipalType.USER:
            _require_typed_id(self.internal_principal_id, "user", "internal_principal_id")
        else:
            _require_typed_id(
                self.internal_principal_id, "service_identity", "internal_principal_id"
            )
        if not isinstance(self.status, ExternalIdentityStatus):
            raise TypeError("status deve ser ExternalIdentityStatus.")
        _require_utc(self.linked_at, "linked_at")
        _require_typed_id(self.linked_by_actor_id, "actor", "linked_by_actor_id")

    @classmethod
    def link_user(
        cls,
        *,
        operator_organization_id: OrganizationId,
        issuer: str,
        subject: str,
        user_id: TypedId,
        linked_at: datetime,
        linked_by_actor_id: TypedId,
    ) -> Self:
        return cls(
            TypedId.new("external_identity"),
            operator_organization_id,
            issuer,
            subject,
            PrincipalType.USER,
            user_id,
            ExternalIdentityStatus.ATIVA,
            linked_at,
            linked_by_actor_id,
        )


@dataclass(frozen=True, slots=True)
class OrganizationContext:
    organization_id: OrganizationId
    authenticated_principal: AuthenticatedPrincipal
    user_id: TypedId
    actor_id: TypedId
    membership_id: TypedId
    role_ids: tuple[TypedId, ...]
    permission_codes: frozenset[str]
    validated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.authenticated_principal, AuthenticatedPrincipal):
            raise TypeError("authenticated_principal deve ser AuthenticatedPrincipal.")
        _require_typed_id(self.user_id, "user", "user_id")
        _require_typed_id(self.actor_id, "actor", "actor_id")
        _require_typed_id(self.membership_id, "membership", "membership_id")
        for role_id in self.role_ids:
            _require_typed_id(role_id, "role", "role_ids")
        if not isinstance(self.permission_codes, frozenset):
            raise TypeError("permission_codes deve ser frozenset.")
        _require_utc(self.validated_at, "validated_at")
