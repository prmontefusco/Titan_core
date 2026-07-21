"""Persistência do vínculo canônico entre identidade externa e User."""

from dataclasses import dataclass

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import UUID

from packages.core_domain import (
    AuthenticatedPrincipal,
    ExternalIdentity,
    ExternalIdentityStatus,
    PrincipalType,
)
from packages.core_infrastructure.persistence.organizations import (
    CORE_IDENTITY_SCHEMA,
    organization_metadata,
)
from packages.shared_kernel import OrganizationId, TypedId

external_identities_table = Table(
    "external_identities",
    organization_metadata,
    Column("external_identity_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "record_owner_organization_id",
        UUID(as_uuid=True),
        ForeignKey(
            "core_identity.organizations.organization_id",
            name="fk_external_identities_owner",
        ),
        nullable=False,
    ),
    Column("issuer", String(500), nullable=False),
    Column("subject", String(255), nullable=False),
    Column("principal_type", String(30), nullable=False),
    Column(
        "internal_principal_id",
        UUID(as_uuid=True),
        ForeignKey("core_identity.users.user_id", name="fk_external_identities_user"),
        nullable=False,
    ),
    Column("status", String(20), nullable=False),
    Column("linked_at", DateTime(timezone=True), nullable=False),
    Column("linked_by_actor_id", UUID(as_uuid=True), nullable=False),
    CheckConstraint("principal_type = 'USER'", name="ck_external_identities_type"),
    CheckConstraint("status IN ('ATIVA', 'SUSPENSA')", name="ck_external_identities_status"),
    UniqueConstraint("issuer", "subject", name="uq_external_identities_issuer_subject"),
    schema=CORE_IDENTITY_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_identity",
)


@dataclass(frozen=True, slots=True)
class ExternalIdentityRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("ExternalIdentityRepository exige transação ativa.")

    def add(self, identity: ExternalIdentity) -> None:
        self.connection.execute(
            insert(external_identities_table).values(
                external_identity_id=identity.external_identity_id.value,
                record_owner_organization_id=identity.record_owner_organization_id.value,
                issuer=identity.issuer,
                subject=identity.subject,
                principal_type=identity.principal_type.value,
                internal_principal_id=identity.internal_principal_id.value,
                status=identity.status.value,
                linked_at=identity.linked_at,
                linked_by_actor_id=identity.linked_by_actor_id.value,
            )
        )

    def resolve(self, principal: AuthenticatedPrincipal) -> ExternalIdentity | None:
        row = self.connection.execute(
            select(external_identities_table).where(
                external_identities_table.c.issuer == principal.issuer,
                external_identities_table.c.subject == principal.subject,
                external_identities_table.c.principal_type == principal.principal_type.value,
            )
        ).one_or_none()
        if row is None:
            return None
        return ExternalIdentity(
            external_identity_id=TypedId("external_identity", row.external_identity_id),
            record_owner_organization_id=OrganizationId(row.record_owner_organization_id),
            issuer=row.issuer,
            subject=row.subject,
            principal_type=PrincipalType(row.principal_type),
            internal_principal_id=TypedId("user", row.internal_principal_id),
            status=ExternalIdentityStatus(row.status),
            linked_at=row.linked_at,
            linked_by_actor_id=TypedId("actor", row.linked_by_actor_id),
        )
