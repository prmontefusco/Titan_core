"""Persistencia da assercao auditavel de embargo ambiental."""

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.environmental_embargo_assertion_service import (
    PropertyEnvironmentalEmbargoAssertionRepositoryPort,
)
from packages.livestock_domain.environmental_embargo_assertion import (
    EnvironmentalEmbargoAssertionStatus,
    PropertyEnvironmentalEmbargoAssertion,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

property_environmental_embargo_assertions_table = Table(
    "property_environmental_embargo_assertions",
    livestock_metadata,
    Column("assertion_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("property_id", PG_UUID(as_uuid=True), nullable=False),
    Column("geometry_id", PG_UUID(as_uuid=True), nullable=True),
    Column("geometry_version", Integer(), nullable=True),
    Column("source_name", String(120), nullable=False),
    Column("source_layer", String(120), nullable=False),
    Column("operation", String(40), nullable=False),
    Column("status", String(40), nullable=False),
    Column("source_digest", String(64), nullable=True),
    Column("response_digest", String(64), nullable=True),
    Column("version_ids", JSONB, nullable=False, server_default="[]"),
    Column("restrictions_payload", JSONB, nullable=False, server_default="[]"),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_property_environmental_embargo_assertions_organization",
    ),
    ForeignKeyConstraint(
        ["property_id"],
        ["core_audit.rural_properties.property_id"],
        name="fk_property_environmental_embargo_assertions_property",
    ),
    ForeignKeyConstraint(
        ["geometry_id"],
        ["core_audit.property_geometries.geometry_id"],
        name="fk_property_environmental_embargo_assertions_geometry",
    ),
    Index(
        "ix_property_environmental_embargo_assertions_lookup",
        "record_owner_organization_id",
        "property_id",
        "observed_at",
    ),
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    schema=CORE_AUDIT_SCHEMA,
)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


@dataclass(frozen=True, slots=True)
class TransactionalPropertyEnvironmentalEmbargoAssertionRepository(
    PropertyEnvironmentalEmbargoAssertionRepositoryPort
):
    connection: Connection

    def save(self, assertion: PropertyEnvironmentalEmbargoAssertion) -> None:
        self.connection.execute(
            insert(property_environmental_embargo_assertions_table).values(
                assertion_id=assertion.assertion_id.value,
                record_owner_organization_id=assertion.organization_id.value,
                property_id=assertion.property_id.value,
                geometry_id=(
                    None if assertion.geometry_id is None else assertion.geometry_id.value
                ),
                geometry_version=assertion.geometry_version,
                source_name=assertion.source_name,
                source_layer=assertion.source_layer,
                operation=assertion.operation,
                status=assertion.status.value,
                source_digest=assertion.source_digest,
                response_digest=assertion.response_digest,
                version_ids=list(assertion.version_ids),
                restrictions_payload=[dict(item) for item in assertion.restrictions_payload],
                observed_at=assertion.observed_at,
                recorded_at=assertion.recorded_at,
            )
        )

    def list_by_property(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> list[PropertyEnvironmentalEmbargoAssertion]:
        rows = self.connection.execute(
            select(property_environmental_embargo_assertions_table)
            .where(
                property_environmental_embargo_assertions_table.c.record_owner_organization_id
                == organization_id.value,
                property_environmental_embargo_assertions_table.c.property_id == property_id.value,
            )
            .order_by(property_environmental_embargo_assertions_table.c.observed_at.desc())
        ).all()
        return [self._map(row) for row in rows]

    def _map(self, row: Row[Any]) -> PropertyEnvironmentalEmbargoAssertion:
        return PropertyEnvironmentalEmbargoAssertion(
            assertion_id=TypedId(
                entity_type="property_environmental_embargo_assertion",
                value=row.assertion_id,
            ),
            organization_id=OrganizationId(row.record_owner_organization_id),
            property_id=TypedId(entity_type="rural_property", value=row.property_id),
            geometry_id=(
                None
                if row.geometry_id is None
                else TypedId(entity_type="property_geometry", value=row.geometry_id)
            ),
            geometry_version=(None if row.geometry_version is None else int(row.geometry_version)),
            source_name=row.source_name,
            source_layer=row.source_layer,
            operation=row.operation,
            status=EnvironmentalEmbargoAssertionStatus(row.status),
            source_digest=row.source_digest,
            response_digest=row.response_digest,
            version_ids=tuple(row.version_ids or []),
            restrictions_payload=tuple(
                MappingProxyType(dict(item)) for item in (row.restrictions_payload or [])
            ),
            observed_at=_aware(row.observed_at),
            recorded_at=_aware(row.recorded_at),
        )
