"""Repositórios PostgreSQL com RLS para AnimalMovement e PropertyStay (Passo 8.3)."""

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Table,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.movement_service import (
    MovementRepositoryPort,
    PropertyStayRepositoryPort,
)
from packages.livestock_domain.movement import (
    AnimalMovement,
    PropertyStay,
    StayStatus,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

animal_movements_table = Table(
    "animal_movements",
    livestock_metadata,
    Column("movement_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("origin_property_id", PG_UUID(as_uuid=True), nullable=False),
    Column("destination_property_id", PG_UUID(as_uuid=True), nullable=False),
    Column("movement_time", DateTime(timezone=True), nullable=False),
    Column("reason", String(255), nullable=True),
    Column("evidence_reference", String(255), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_animal_movements_organization",
    ),
    ForeignKeyConstraint(
        ["origin_property_id"],
        ["core_audit.rural_properties.property_id"],
        name="fk_animal_movements_origin_property",
    ),
    ForeignKeyConstraint(
        ["destination_property_id"],
        ["core_audit.rural_properties.property_id"],
        name="fk_animal_movements_destination_property",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)

animal_movement_items_table = Table(
    "animal_movement_items",
    livestock_metadata,
    Column(
        "movement_id",
        PG_UUID(as_uuid=True),
        primary_key=True,
    ),
    Column(
        "animal_id",
        PG_UUID(as_uuid=True),
        primary_key=True,
    ),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    ForeignKeyConstraint(
        ["movement_id"],
        ["core_audit.animal_movements.movement_id"],
        name="fk_animal_movement_items_movement",
    ),
    ForeignKeyConstraint(
        ["animal_id"],
        ["core_audit.animals.animal_id"],
        name="fk_animal_movement_items_animal",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_animal_movement_items_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)

property_stays_table = Table(
    "property_stays",
    livestock_metadata,
    Column("stay_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("animal_id", PG_UUID(as_uuid=True), nullable=False),
    Column("property_id", PG_UUID(as_uuid=True), nullable=False),
    Column("start_time", DateTime(timezone=True), nullable=False),
    Column("end_time", DateTime(timezone=True), nullable=True),
    Column("status", String(20), nullable=False),
    Column("source_movement_id", PG_UUID(as_uuid=True), nullable=True),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_property_stays_organization",
    ),
    ForeignKeyConstraint(
        ["animal_id"],
        ["core_audit.animals.animal_id"],
        name="fk_property_stays_animal",
    ),
    ForeignKeyConstraint(
        ["property_id"],
        ["core_audit.rural_properties.property_id"],
        name="fk_property_stays_property",
    ),
    ForeignKeyConstraint(
        ["source_movement_id"],
        ["core_audit.animal_movements.movement_id"],
        name="fk_property_stays_source_movement",
    ),
    Index(
        "ix_property_stays_animal_status",
        "record_owner_organization_id",
        "animal_id",
        "status",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalAnimalMovementRepository(MovementRepositoryPort):
    connection: Connection

    def save(self, movement: AnimalMovement) -> None:
        stmt_m = insert(animal_movements_table).values(
            movement_id=movement.movement_id.value,
            record_owner_organization_id=movement.organization_id.value,
            origin_property_id=movement.origin_property_id.value,
            destination_property_id=movement.destination_property_id.value,
            movement_time=movement.movement_time,
            reason=movement.reason,
            evidence_reference=movement.evidence_reference,
            created_at=movement.created_at,
        )
        self.connection.execute(stmt_m)

        for aid in movement.animal_ids:
            stmt_item = insert(animal_movement_items_table).values(
                movement_id=movement.movement_id.value,
                animal_id=aid.value,
                record_owner_organization_id=movement.organization_id.value,
            )
            self.connection.execute(stmt_item)

    def get_by_id(self, movement_id: TypedId) -> AnimalMovement | None:
        if movement_id.entity_type != "animal_movement":
            return None
        stmt = select(animal_movements_table).where(
            animal_movements_table.c.movement_id == movement_id.value
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_movement(row)

    def list_by_animal(self, animal_id: TypedId) -> list[AnimalMovement]:
        stmt_items = select(animal_movement_items_table.c.movement_id).where(
            animal_movement_items_table.c.animal_id == animal_id.value
        )
        m_rows = self.connection.execute(stmt_items).fetchall()
        m_ids = [r.movement_id for r in m_rows]
        if not m_ids:
            return []

        stmt_m = (
            select(animal_movements_table)
            .where(animal_movements_table.c.movement_id.in_(m_ids))
            .order_by(animal_movements_table.c.movement_time.asc())
        )
        rows = self.connection.execute(stmt_m).fetchall()
        return [self._map_movement(row) for row in rows]

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[AnimalMovement]:
        stmt = (
            select(animal_movements_table)
            .where(animal_movements_table.c.record_owner_organization_id == organization_id.value)
            .order_by(animal_movements_table.c.movement_time.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map_movement(row) for row in rows]

    def _map_movement(self, row: Row[Any]) -> AnimalMovement:
        stmt_items = select(animal_movement_items_table.c.animal_id).where(
            animal_movement_items_table.c.movement_id == row.movement_id
        )
        items_rows = self.connection.execute(stmt_items).fetchall()
        animal_ids = tuple(TypedId(entity_type="animal", value=r.animal_id) for r in items_rows)

        m_time = row.movement_time
        if m_time.tzinfo is None:
            m_time = m_time.replace(tzinfo=UTC)

        c_at = row.created_at
        if c_at.tzinfo is None:
            c_at = c_at.replace(tzinfo=UTC)

        return AnimalMovement(
            movement_id=TypedId(entity_type="animal_movement", value=row.movement_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            origin_property_id=TypedId(entity_type="rural_property", value=row.origin_property_id),
            destination_property_id=TypedId(
                entity_type="rural_property", value=row.destination_property_id
            ),
            movement_time=m_time,
            animal_ids=animal_ids,
            reason=row.reason,
            evidence_reference=row.evidence_reference,
            created_at=c_at,
        )


@dataclass(frozen=True, slots=True)
class TransactionalPropertyStayRepository(PropertyStayRepositoryPort):
    connection: Connection

    def save(self, stay: PropertyStay) -> None:
        stmt = insert(property_stays_table).values(
            stay_id=stay.stay_id.value,
            record_owner_organization_id=stay.organization_id.value,
            animal_id=stay.animal_id.value,
            property_id=stay.property_id.value,
            start_time=stay.start_time,
            end_time=stay.end_time,
            status=stay.status.value,
            source_movement_id=stay.source_movement_id.value
            if stay.source_movement_id is not None
            else None,
        )
        self.connection.execute(stmt)

    def update(self, stay: PropertyStay) -> None:
        stmt = (
            update(property_stays_table)
            .where(property_stays_table.c.stay_id == stay.stay_id.value)
            .values(
                end_time=stay.end_time,
                status=stay.status.value,
            )
        )
        self.connection.execute(stmt)

    def delete_by_animal(self, animal_id: TypedId) -> None:
        stmt = delete(property_stays_table).where(
            property_stays_table.c.animal_id == animal_id.value
        )
        self.connection.execute(stmt)

    def get_active_stay(self, animal_id: TypedId) -> PropertyStay | None:
        stmt = select(property_stays_table).where(
            property_stays_table.c.animal_id == animal_id.value,
            property_stays_table.c.status == StayStatus.ACTIVE.value,
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_stay(row)

    def get_timeline(self, animal_id: TypedId) -> list[PropertyStay]:
        stmt = (
            select(property_stays_table)
            .where(property_stays_table.c.animal_id == animal_id.value)
            .order_by(property_stays_table.c.start_time.asc())
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map_stay(row) for row in rows]

    def _map_stay(self, row: Row[Any]) -> PropertyStay:
        s_time = row.start_time
        if s_time.tzinfo is None:
            s_time = s_time.replace(tzinfo=UTC)

        e_time = row.end_time
        if e_time is not None and e_time.tzinfo is None:
            e_time = e_time.replace(tzinfo=UTC)

        src_m_id = (
            TypedId(entity_type="animal_movement", value=row.source_movement_id)
            if row.source_movement_id is not None
            else None
        )

        return PropertyStay(
            stay_id=TypedId(entity_type="property_stay", value=row.stay_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            animal_id=TypedId(entity_type="animal", value=row.animal_id),
            property_id=TypedId(entity_type="rural_property", value=row.property_id),
            start_time=s_time,
            end_time=e_time,
            status=StayStatus(row.status),
            source_movement_id=src_m_id,
        )
