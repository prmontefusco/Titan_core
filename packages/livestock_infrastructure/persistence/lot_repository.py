"""Repositórios PostgreSQL com RLS para LivestockLot e LotMembership (Passo 8.4)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.lot_service import (
    LivestockLotRepositoryPort,
    LotMembershipRepositoryPort,
)
from packages.livestock_domain.lot import (
    LivestockLot,
    LotMembership,
    LotStatus,
    LotType,
)
from packages.shared_kernel import OrganizationId, TypedId

livestock_metadata = MetaData(schema=CORE_AUDIT_SCHEMA)

livestock_lots_table = Table(
    "livestock_lots",
    livestock_metadata,
    Column("lot_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("property_id", PG_UUID(as_uuid=True), nullable=False),
    Column("code", String(100), nullable=False),
    Column("name", String(255), nullable=False),
    Column("lot_type", String(50), nullable=False),
    Column("status", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "record_owner_organization_id",
        "code",
        name="uq_livestock_lots_org_code",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_livestock_lots_organization",
    ),
    ForeignKeyConstraint(
        ["property_id"],
        ["core_audit.rural_properties.property_id"],
        name="fk_livestock_lots_property",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)

lot_memberships_table = Table(
    "lot_memberships",
    livestock_metadata,
    Column("membership_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("lot_id", PG_UUID(as_uuid=True), nullable=False),
    Column("animal_id", PG_UUID(as_uuid=True), nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("valid_until", DateTime(timezone=True), nullable=True),
    Column("reason", String(255), nullable=True),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_lot_memberships_organization",
    ),
    ForeignKeyConstraint(
        ["lot_id"],
        ["core_audit.livestock_lots.lot_id"],
        name="fk_lot_memberships_lot",
    ),
    ForeignKeyConstraint(
        ["animal_id"],
        ["core_audit.animals.animal_id"],
        name="fk_lot_memberships_animal",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalLivestockLotRepository(LivestockLotRepositoryPort):
    connection: Connection

    def save(self, lot: LivestockLot) -> None:
        stmt = insert(livestock_lots_table).values(
            lot_id=lot.lot_id.value,
            record_owner_organization_id=lot.organization_id.value,
            property_id=lot.property_id.value,
            code=lot.code,
            name=lot.name,
            lot_type=lot.lot_type.value,
            status=lot.status.value,
            created_at=lot.created_at,
        )
        self.connection.execute(stmt)

    def update(self, lot: LivestockLot) -> None:
        stmt = (
            update(livestock_lots_table)
            .where(livestock_lots_table.c.lot_id == lot.lot_id.value)
            .values(
                name=lot.name,
                lot_type=lot.lot_type.value,
                status=lot.status.value,
            )
        )
        self.connection.execute(stmt)

    def get_by_id(self, lot_id: TypedId) -> LivestockLot | None:
        if lot_id.entity_type != "livestock_lot":
            return None
        stmt = select(livestock_lots_table).where(livestock_lots_table.c.lot_id == lot_id.value)
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_lot(row)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> LivestockLot | None:
        stmt = select(livestock_lots_table).where(
            livestock_lots_table.c.record_owner_organization_id == organization_id.value,
            livestock_lots_table.c.code == code,
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_lot(row)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[LivestockLot]:
        stmt = (
            select(livestock_lots_table)
            .where(livestock_lots_table.c.record_owner_organization_id == organization_id.value)
            .order_by(livestock_lots_table.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map_lot(row) for row in rows]

    def _map_lot(self, row: Row[Any]) -> LivestockLot:
        c_at = row.created_at
        if c_at.tzinfo is None:
            c_at = c_at.replace(tzinfo=UTC)

        return LivestockLot(
            lot_id=TypedId(entity_type="livestock_lot", value=row.lot_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            property_id=TypedId(entity_type="rural_property", value=row.property_id),
            code=row.code,
            name=row.name,
            lot_type=LotType(row.lot_type),
            status=LotStatus(row.status),
            created_at=c_at,
        )


@dataclass(frozen=True, slots=True)
class TransactionalLotMembershipRepository(LotMembershipRepositoryPort):
    connection: Connection

    def save(self, membership: LotMembership) -> None:
        # Busca o record_owner_organization_id do lote correspondente
        stmt_lot = select(livestock_lots_table.c.record_owner_organization_id).where(
            livestock_lots_table.c.lot_id == membership.lot_id.value
        )
        row_lot = self.connection.execute(stmt_lot).fetchone()
        if row_lot is None:
            raise KeyError(f"Lote '{membership.lot_id.value}' não encontrado no banco.")

        stmt = insert(lot_memberships_table).values(
            membership_id=membership.membership_id.value,
            record_owner_organization_id=row_lot.record_owner_organization_id,
            lot_id=membership.lot_id.value,
            animal_id=membership.animal_id.value,
            valid_from=membership.valid_from,
            valid_until=membership.valid_until,
            reason=membership.reason,
        )
        self.connection.execute(stmt)

    def update(self, membership: LotMembership) -> None:
        stmt = (
            update(lot_memberships_table)
            .where(lot_memberships_table.c.membership_id == membership.membership_id.value)
            .values(
                valid_until=membership.valid_until,
                reason=membership.reason,
            )
        )
        self.connection.execute(stmt)

    def get_active_memberships_for_animal(self, animal_id: TypedId) -> list[LotMembership]:
        stmt = select(lot_memberships_table).where(
            lot_memberships_table.c.animal_id == animal_id.value,
            lot_memberships_table.c.valid_until.is_(None),
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map_membership(row) for row in rows]

    def get_memberships_for_lot(
        self, lot_id: TypedId, at_time: datetime | None = None
    ) -> list[LotMembership]:
        stmt = select(lot_memberships_table).where(lot_memberships_table.c.lot_id == lot_id.value)
        rows = self.connection.execute(stmt).fetchall()
        result = []
        target_time = (
            at_time.replace(tzinfo=UTC)
            if at_time is not None and at_time.tzinfo is None
            else at_time
        )
        for r in rows:
            m = self._map_membership(r)
            if target_time is None:
                if m.valid_until is None:
                    result.append(m)
            else:
                if m.valid_from <= target_time and (
                    m.valid_until is None or m.valid_until > target_time
                ):
                    result.append(m)
        return result

    def _map_membership(self, row: Row[Any]) -> LotMembership:
        v_from = row.valid_from
        if v_from.tzinfo is None:
            v_from = v_from.replace(tzinfo=UTC)

        v_until = row.valid_until
        if v_until is not None and v_until.tzinfo is None:
            v_until = v_until.replace(tzinfo=UTC)

        return LotMembership(
            membership_id=TypedId(entity_type="lot_membership", value=row.membership_id),
            lot_id=TypedId(entity_type="livestock_lot", value=row.lot_id),
            animal_id=TypedId(entity_type="animal", value=row.animal_id),
            valid_from=v_from,
            valid_until=v_until,
            reason=row.reason,
        )
