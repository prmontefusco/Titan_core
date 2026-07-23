"""Repositório PostgreSQL com RLS para RuralProperty (Passo 8.1 - Titan Livestock)."""

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.property import RuralProperty
from packages.shared_kernel import OrganizationId, TypedId

livestock_metadata = MetaData(schema=CORE_AUDIT_SCHEMA)

rural_properties_table = Table(
    "rural_properties",
    livestock_metadata,
    Column("property_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("code", String(100), nullable=False),
    Column("name", String(255), nullable=False),
    Column("municipality", String(255), nullable=False),
    Column("state_code", String(2), nullable=False),
    Column("registration_number", String(255), nullable=True),
    Column("total_area_hectares", Float, nullable=True),
    Column("status", String(50), nullable=False, default="ACTIVE"),
    Column("version", Integer, nullable=False, default=1),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "record_owner_organization_id",
        "code",
        name="uq_rural_properties_org_code",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_rural_properties_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalRuralPropertyRepository(RuralPropertyRepositoryPort):
    connection: Connection

    def save(self, property: RuralProperty) -> None:
        stmt = insert(rural_properties_table).values(
            property_id=property.property_id.value,
            record_owner_organization_id=property.organization_id.value,
            code=property.code,
            name=property.name,
            municipality=property.municipality,
            state_code=property.state_code,
            registration_number=property.registration_number,
            total_area_hectares=property.total_area_hectares,
            status=property.status,
            version=property.version,
            created_at=property.created_at,
        )
        self.connection.execute(stmt)

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None:
        if property_id.entity_type != "rural_property":
            return None
        stmt = select(rural_properties_table).where(
            rural_properties_table.c.property_id == property_id.value
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_row(row)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        stmt = select(rural_properties_table).where(
            rural_properties_table.c.record_owner_organization_id == organization_id.value,
            rural_properties_table.c.code == code,
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_row(row)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        stmt = (
            select(rural_properties_table)
            .where(rural_properties_table.c.record_owner_organization_id == organization_id.value)
            .order_by(rural_properties_table.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map_row(row) for row in rows]

    def _map_row(self, row: Row[Any]) -> RuralProperty:
        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        status = getattr(row, "status", "ACTIVE") or "ACTIVE"
        version = getattr(row, "version", 1) or 1

        return RuralProperty(
            property_id=TypedId(entity_type="rural_property", value=row.property_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            code=row.code,
            name=row.name,
            municipality=row.municipality,
            state_code=row.state_code,
            registration_number=row.registration_number,
            total_area_hectares=row.total_area_hectares,
            status=status,
            version=version,
            created_at=created_at,
        )
