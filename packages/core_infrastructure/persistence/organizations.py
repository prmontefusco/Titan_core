"""Persistência PostgreSQL da Organization, protegida por contexto transacional."""

from dataclasses import dataclass

from sqlalchemy import CheckConstraint, Column, Connection, MetaData, Table, insert, select, text
from sqlalchemy.dialects.postgresql import UUID

from packages.core_domain import Organization
from packages.shared_kernel import OrganizationId

CORE_IDENTITY_SCHEMA = "core_identity"
ORGANIZATION_CONTEXT_SETTING = "titan.organization_id"

organization_metadata = MetaData(schema=CORE_IDENTITY_SCHEMA)

organizations_table = Table(
    "organizations",
    organization_metadata,
    Column("organization_id", UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    CheckConstraint(
        "record_owner_organization_id = organization_id",
        name="ck_organizations_self_owned",
    ),
    comment="titan.classification=PROTECTED;titan.module_owner=core_identity",
)


def set_local_organization_context(
    connection: Connection,
    organization_id: OrganizationId,
) -> None:
    """Define a Organization atuante somente para a transação corrente."""
    if not isinstance(connection, Connection):
        raise TypeError("connection deve ser uma Connection SQLAlchemy.")
    if not isinstance(organization_id, OrganizationId):
        raise TypeError("organization_id deve ser um OrganizationId.")
    if not connection.in_transaction():
        raise RuntimeError("O contexto de Organization exige transação ativa.")
    connection.execute(
        text("SELECT set_config(:setting_name, :organization_id, true)"),
        {
            "setting_name": ORGANIZATION_CONTEXT_SETTING,
            "organization_id": str(organization_id),
        },
    )


@dataclass(frozen=True, slots=True)
class OrganizationRepository:
    """Acesso ao registro de Organization dentro de transação contextualizada."""

    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection):
            raise TypeError("connection deve ser uma Connection SQLAlchemy.")
        if not self.connection.in_transaction():
            raise RuntimeError("OrganizationRepository exige transação ativa.")

    def add(self, organization: Organization) -> None:
        if not isinstance(organization, Organization):
            raise TypeError("organization deve ser uma Organization.")
        identifier = organization.organization_id.value
        self.connection.execute(
            insert(organizations_table).values(
                organization_id=identifier,
                record_owner_organization_id=identifier,
            )
        )

    def get(self, organization_id: OrganizationId) -> Organization | None:
        if not isinstance(organization_id, OrganizationId):
            raise TypeError("organization_id deve ser um OrganizationId.")
        stored_id = self.connection.execute(
            select(organizations_table.c.organization_id).where(
                organizations_table.c.organization_id == organization_id.value
            )
        ).scalar_one_or_none()
        if stored_id is None:
            return None
        return Organization(organization_id=OrganizationId(stored_id))
