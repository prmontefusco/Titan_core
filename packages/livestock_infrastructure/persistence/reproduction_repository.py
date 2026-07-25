"""Repositório PostgreSQL com RLS para o evento reprodutivo (Passo 13.3, ADR-0040)."""

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_domain.animal import BirthOutcome
from packages.livestock_domain.reproduction import (
    GestationalAgeBasis,
    Offspring,
    ReproductiveEvent,
    ReproductiveEventType,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

reproductive_events_table = Table(
    "reproductive_events",
    livestock_metadata,
    Column("event_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("dam_id", PG_UUID(as_uuid=True), nullable=False),
    Column("sire_id", PG_UUID(as_uuid=True), nullable=True),
    Column("event_type", String(20), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("gestational_age_days", Integer, nullable=True),
    Column("gestational_age_basis", String(20), nullable=False),
    Column("notes", String(1000), nullable=True),
    Column("evidence_references", JSONB, nullable=False, server_default="[]"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_reproductive_events_organization",
    ),
    ForeignKeyConstraint(
        ["dam_id"], ["core_audit.animals.animal_id"], name="fk_reproductive_events_dam"
    ),
    ForeignKeyConstraint(
        ["sire_id"], ["core_audit.animals.animal_id"], name="fk_reproductive_events_sire"
    ),
    CheckConstraint(
        "gestational_age_days IS NULL OR gestational_age_days > 0",
        name="ck_reproductive_events_gestational_age",
    ),
    CheckConstraint(
        "(gestational_age_days IS NULL AND gestational_age_basis = 'UNKNOWN')"
        " OR (gestational_age_days IS NOT NULL AND gestational_age_basis <> 'UNKNOWN')",
        name="ck_reproductive_events_gestational_basis",
    ),
    Index("ix_reproductive_events_dam", "dam_id", "occurred_at"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)

reproductive_event_offspring_table = Table(
    "reproductive_event_offspring",
    livestock_metadata,
    Column("event_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("animal_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("outcome", String(20), nullable=False),
    ForeignKeyConstraint(
        ["event_id"],
        ["core_audit.reproductive_events.event_id"],
        name="fk_offspring_event",
    ),
    ForeignKeyConstraint(
        ["animal_id"], ["core_audit.animals.animal_id"], name="fk_offspring_animal"
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_offspring_organization",
    ),
    # Um animal nasce de um parto só.
    UniqueConstraint("animal_id", name="uq_offspring_animal"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalReproductiveEventRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalReproductiveEventRepository exige transacao ativa.")

    def save(self, event: ReproductiveEvent) -> None:
        self.connection.execute(
            insert(reproductive_events_table).values(
                event_id=event.event_id.value,
                record_owner_organization_id=event.organization_id.value,
                dam_id=event.dam_id.value,
                sire_id=None if event.sire_id is None else event.sire_id.value,
                event_type=event.event_type.value,
                occurred_at=event.occurred_at,
                gestational_age_days=event.gestational_age_days,
                gestational_age_basis=event.gestational_age_basis.value,
                notes=event.notes,
                evidence_references=[
                    str(referencia.target_id.value) for referencia in event.evidence_references
                ],
                created_at=event.created_at,
            )
        )
        for cria in event.offspring:
            self.connection.execute(
                insert(reproductive_event_offspring_table).values(
                    event_id=event.event_id.value,
                    animal_id=cria.animal_id.value,
                    record_owner_organization_id=event.organization_id.value,
                    outcome=cria.outcome.value,
                )
            )

    def get_by_id(self, event_id: TypedId) -> ReproductiveEvent | None:
        row = self.connection.execute(
            select(reproductive_events_table).where(
                reproductive_events_table.c.event_id == event_id.value
            )
        ).fetchone()
        return None if row is None else self._mapear(row)

    def list_by_dam(
        self, organization_id: OrganizationId, dam_id: TypedId
    ) -> list[ReproductiveEvent]:
        rows = self.connection.execute(
            select(reproductive_events_table)
            .where(
                reproductive_events_table.c.record_owner_organization_id == organization_id.value,
                reproductive_events_table.c.dam_id == dam_id.value,
            )
            .order_by(reproductive_events_table.c.occurred_at.asc())
        ).fetchall()
        return [self._mapear(row) for row in rows]

    def get_by_offspring(self, animal_id: TypedId) -> ReproductiveEvent | None:
        """De qual parto este animal nasceu — a origem da identidade dele."""
        row = self.connection.execute(
            select(reproductive_event_offspring_table.c.event_id).where(
                reproductive_event_offspring_table.c.animal_id == animal_id.value
            )
        ).fetchone()
        if row is None:
            return None
        return self.get_by_id(TypedId(entity_type="reproductive_event", value=row.event_id))

    def _mapear(self, row: Row[Any]) -> ReproductiveEvent:
        crias = self.connection.execute(
            select(reproductive_event_offspring_table).where(
                reproductive_event_offspring_table.c.event_id == row.event_id
            )
        ).fetchall()
        organization_id = OrganizationId(row.record_owner_organization_id)
        return ReproductiveEvent(
            event_id=TypedId(entity_type="reproductive_event", value=row.event_id),
            organization_id=organization_id,
            dam_id=TypedId(entity_type="animal", value=row.dam_id),
            sire_id=(
                None if row.sire_id is None else TypedId(entity_type="animal", value=row.sire_id)
            ),
            event_type=ReproductiveEventType(row.event_type),
            occurred_at=_utc(row.occurred_at),
            offspring=tuple(
                Offspring(
                    animal_id=TypedId(entity_type="animal", value=cria.animal_id),
                    outcome=BirthOutcome(cria.outcome),
                )
                for cria in crias
            ),
            gestational_age_days=row.gestational_age_days,
            gestational_age_basis=GestationalAgeBasis(row.gestational_age_basis),
            notes=row.notes,
            evidence_references=tuple(
                UniversalReference(
                    target_id=TypedId.parse("evidence", bruto),
                    organization_id=organization_id,
                    contract_version=1,
                )
                for bruto in (row.evidence_references or [])
            ),
            created_at=_utc(row.created_at),
        )


def _utc(valor: Any) -> Any:
    return valor if valor.tzinfo is not None else valor.replace(tzinfo=UTC)
