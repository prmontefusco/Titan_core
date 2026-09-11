"""Persistência de `StockPosition`, `StockReservation` e `StockTransfer` — Titan Asset (A3).

`StockReservationLine.demand_ref`, `StockReservation.demand.ref`,
`StockReservation.decision_ref` e `StockTransfer.linked_reservation_ref` são
`TypedId` sem `entity_type` fixado por validação do domínio (mesmo caso de
`Applicability.asserted_by`, já resolvido em `applicability_repository.py`) —
cada um ganha uma coluna `*_entity_type` própria para não corromper o
round-trip.

`stock_position_reservations` (a projeção que `StockPosition.reservations`
guarda) **não** tem FK para `stock_reservations.reservation_id` de propósito:
`06_AGGREGATE_ANALYSIS.md` §3 já registra que a coordenação entre os dois
agregados pode ser assíncrona (cenário B, saga) — uma FK rígida aqui
impediria a projeção de existir antes da `StockReservation` estar
durável, contradizendo o design. É referência lógica, não de integridade
referencial (mesmo padrão de `evidence_ref`/`asserted_by`).

Nada em `stock_position_reservations` tem FK apontando para ela, então
`update()` da posição pode seguir delete+reinsert com segurança (ao
contrário do que se descobriu em `part_repository.py`/`vehicle_repository.py`).
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Table,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.asset_domain.inventory import (
    DemandKind,
    DemandRef,
    ReservationState,
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
    StockReservation,
    StockReservationLine,
    StockTransfer,
    TransferState,
)
from packages.asset_infrastructure.persistence.metadata import asset_metadata
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.shared_kernel import OrganizationId, TypedId

stock_positions_table = Table(
    "stock_positions",
    asset_metadata,
    Column("stock_position_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("part_id", PG_UUID(as_uuid=True), nullable=False),
    Column("location_id", PG_UUID(as_uuid=True), nullable=False),
    Column("purpose", String(30), nullable=False),
    Column("ownership", String(30), nullable=False),
    Column("on_hand", Numeric, nullable=False, default=0),
    Column("in_transit", Numeric, nullable=False, default=0),
    Column("quarantine", Numeric, nullable=False, default=0),
    Column("inspection", Numeric, nullable=False, default=0),
    Column("damaged", Numeric, nullable=False, default=0),
    Column("lot", String(100), nullable=True),
    Column("serial", String(100), nullable=True),
    Column("version", Integer, nullable=False, default=1),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_stock_positions_organization",
    ),
    ForeignKeyConstraint(["part_id"], ["core_audit.parts.part_id"], name="fk_stock_positions_part"),
    ForeignKeyConstraint(
        ["location_id"],
        ["core_audit.stock_locations.location_id"],
        name="fk_stock_positions_location",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

stock_reservations_table = Table(
    "stock_reservations",
    asset_metadata,
    Column("reservation_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("stock_position_id", PG_UUID(as_uuid=True), nullable=False),
    Column("demand_kind", String(30), nullable=False),
    Column("demand_ref_id", PG_UUID(as_uuid=True), nullable=False),
    Column("demand_ref_entity_type", String(100), nullable=False),
    Column("qty", Numeric, nullable=False),
    Column("purpose", String(30), nullable=False),
    Column("priority", Integer, nullable=False),
    Column("state", String(20), nullable=False),
    Column("decision_id", PG_UUID(as_uuid=True), nullable=True),
    Column("decision_entity_type", String(100), nullable=True),
    Column("version", Integer, nullable=False, default=1),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_stock_reservations_organization",
    ),
    ForeignKeyConstraint(
        ["stock_position_id"],
        ["core_audit.stock_positions.stock_position_id"],
        name="fk_stock_reservations_position",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

stock_transfers_table = Table(
    "stock_transfers",
    asset_metadata,
    Column("transfer_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("part_id", PG_UUID(as_uuid=True), nullable=False),
    Column("from_location_id", PG_UUID(as_uuid=True), nullable=False),
    Column("to_location_id", PG_UUID(as_uuid=True), nullable=False),
    Column("qty", Numeric, nullable=False),
    Column("state", String(30), nullable=False),
    Column("qty_received", Numeric, nullable=False, default=0),
    Column("linked_reservation_id", PG_UUID(as_uuid=True), nullable=True),
    Column("linked_reservation_entity_type", String(100), nullable=True),
    Column("version", Integer, nullable=False, default=1),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_stock_transfers_organization",
    ),
    ForeignKeyConstraint(["part_id"], ["core_audit.parts.part_id"], name="fk_stock_transfers_part"),
    ForeignKeyConstraint(
        ["from_location_id"],
        ["core_audit.stock_locations.location_id"],
        name="fk_stock_transfers_from_location",
    ),
    ForeignKeyConstraint(
        ["to_location_id"],
        ["core_audit.stock_locations.location_id"],
        name="fk_stock_transfers_to_location",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

stock_position_reservations_table = Table(
    "stock_position_reservations",
    asset_metadata,
    Column("stock_position_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("reservation_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("demand_ref_id", PG_UUID(as_uuid=True), nullable=False),
    Column("demand_ref_entity_type", String(100), nullable=False),
    Column("qty", Numeric, nullable=False),
    Column("priority", Integer, nullable=False),
    Column("purpose_lock", String(30), nullable=False),
    ForeignKeyConstraint(
        ["stock_position_id"],
        ["core_audit.stock_positions.stock_position_id"],
        name="fk_stock_position_reservations_position",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)


@dataclass(frozen=True, slots=True)
class TransactionalStockPositionRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalStockPositionRepository exige Connection com transação ativa."
            )

    def save(self, position: StockPosition) -> None:
        self.connection.execute(insert(stock_positions_table).values(**self._values(position)))
        self._insert_reservation_lines(position)

    def update(self, position: StockPosition) -> None:
        self.connection.execute(
            update(stock_positions_table)
            .where(stock_positions_table.c.stock_position_id == position.stock_position_id.value)
            .values(**self._values(position, include_id=False))
        )
        self.connection.execute(
            delete(stock_position_reservations_table).where(
                stock_position_reservations_table.c.stock_position_id
                == position.stock_position_id.value
            )
        )
        self._insert_reservation_lines(position)

    def _values(self, position: StockPosition, *, include_id: bool = True) -> dict[str, Any]:
        q = position.quantities
        values: dict[str, Any] = {
            "record_owner_organization_id": position.organization_id.value,
            "part_id": position.part_ref.value,
            "location_id": position.location_ref.value,
            "purpose": position.purpose.value,
            "ownership": position.ownership.value,
            "on_hand": q.on_hand,
            "in_transit": q.in_transit,
            "quarantine": q.quarantine,
            "inspection": q.inspection,
            "damaged": q.damaged,
            "lot": position.lot,
            "serial": position.serial,
            "version": position.version,
        }
        if include_id:
            values["stock_position_id"] = position.stock_position_id.value
        return values

    def _insert_reservation_lines(self, position: StockPosition) -> None:
        for line in position.reservations:
            self.connection.execute(
                insert(stock_position_reservations_table).values(
                    stock_position_id=position.stock_position_id.value,
                    reservation_id=line.reservation_id.value,
                    record_owner_organization_id=position.organization_id.value,
                    demand_ref_id=line.demand_ref.value,
                    demand_ref_entity_type=line.demand_ref.entity_type,
                    qty=line.qty,
                    priority=line.priority,
                    purpose_lock=line.purpose_lock.value,
                )
            )

    def get_by_id(self, stock_position_id: TypedId) -> StockPosition | None:
        row = self.connection.execute(
            select(stock_positions_table).where(
                stock_positions_table.c.stock_position_id == stock_position_id.value
            )
        ).fetchone()
        if row is None:
            return None
        return self._map(row)

    def _map(self, row: Row[Any]) -> StockPosition:
        line_rows = self.connection.execute(
            select(stock_position_reservations_table).where(
                stock_position_reservations_table.c.stock_position_id == row.stock_position_id
            )
        ).fetchall()
        reservations = tuple(
            StockReservationLine(
                reservation_id=TypedId(
                    entity_type="stock_reservation", value=line_row.reservation_id
                ),
                demand_ref=TypedId(
                    entity_type=line_row.demand_ref_entity_type, value=line_row.demand_ref_id
                ),
                qty=line_row.qty,
                priority=line_row.priority,
                purpose_lock=StockPurpose(line_row.purpose_lock),
            )
            for line_row in line_rows
        )
        return StockPosition(
            stock_position_id=TypedId(entity_type="stock_position", value=row.stock_position_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            part_ref=TypedId(entity_type="part", value=row.part_id),
            location_ref=TypedId(entity_type="stock_location", value=row.location_id),
            purpose=StockPurpose(row.purpose),
            ownership=StockOwnership(row.ownership),
            quantities=StockQuantities(
                on_hand=row.on_hand,
                in_transit=row.in_transit,
                quarantine=row.quarantine,
                inspection=row.inspection,
                damaged=row.damaged,
            ),
            reservations=reservations,
            lot=row.lot,
            serial=row.serial,
            version=row.version,
        )


@dataclass(frozen=True, slots=True)
class TransactionalStockReservationRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalStockReservationRepository exige Connection com transação ativa."
            )

    def save(self, reservation: StockReservation) -> None:
        self.connection.execute(
            insert(stock_reservations_table).values(**self._values(reservation))
        )

    def update(self, reservation: StockReservation) -> None:
        self.connection.execute(
            update(stock_reservations_table)
            .where(stock_reservations_table.c.reservation_id == reservation.reservation_id.value)
            .values(**self._values(reservation, include_id=False))
        )

    def _values(self, reservation: StockReservation, *, include_id: bool = True) -> dict[str, Any]:
        values: dict[str, Any] = {
            "record_owner_organization_id": reservation.organization_id.value,
            "stock_position_id": reservation.stock_position_ref.value,
            "demand_kind": reservation.demand.kind.value,
            "demand_ref_id": reservation.demand.ref.value,
            "demand_ref_entity_type": reservation.demand.ref.entity_type,
            "qty": reservation.qty,
            "purpose": reservation.purpose.value,
            "priority": reservation.priority,
            "state": reservation.state.value,
            "decision_id": reservation.decision_ref.value if reservation.decision_ref else None,
            "decision_entity_type": (
                reservation.decision_ref.entity_type if reservation.decision_ref else None
            ),
            "version": reservation.version,
        }
        if include_id:
            values["reservation_id"] = reservation.reservation_id.value
        return values

    def get_by_id(self, reservation_id: TypedId) -> StockReservation | None:
        row = self.connection.execute(
            select(stock_reservations_table).where(
                stock_reservations_table.c.reservation_id == reservation_id.value
            )
        ).fetchone()
        if row is None:
            return None
        return self._map(row)

    def _map(self, row: Row[Any]) -> StockReservation:
        return StockReservation(
            reservation_id=TypedId(entity_type="stock_reservation", value=row.reservation_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            stock_position_ref=TypedId(entity_type="stock_position", value=row.stock_position_id),
            demand=DemandRef(
                kind=DemandKind(row.demand_kind),
                ref=TypedId(entity_type=row.demand_ref_entity_type, value=row.demand_ref_id),
            ),
            qty=row.qty,
            purpose=StockPurpose(row.purpose),
            priority=row.priority,
            state=ReservationState(row.state),
            decision_ref=(
                TypedId(entity_type=row.decision_entity_type, value=row.decision_id)
                if row.decision_id is not None
                else None
            ),
            version=row.version,
        )


@dataclass(frozen=True, slots=True)
class TransactionalStockTransferRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalStockTransferRepository exige Connection com transação ativa."
            )

    def save(self, transfer: StockTransfer) -> None:
        self.connection.execute(insert(stock_transfers_table).values(**self._values(transfer)))

    def update(self, transfer: StockTransfer) -> None:
        self.connection.execute(
            update(stock_transfers_table)
            .where(stock_transfers_table.c.transfer_id == transfer.transfer_id.value)
            .values(**self._values(transfer, include_id=False))
        )

    def _values(self, transfer: StockTransfer, *, include_id: bool = True) -> dict[str, Any]:
        values: dict[str, Any] = {
            "record_owner_organization_id": transfer.organization_id.value,
            "part_id": transfer.part_ref.value,
            "from_location_id": transfer.from_location_ref.value,
            "to_location_id": transfer.to_location_ref.value,
            "qty": transfer.qty,
            "state": transfer.state.value,
            "qty_received": transfer.qty_received,
            "linked_reservation_id": (
                transfer.linked_reservation_ref.value if transfer.linked_reservation_ref else None
            ),
            "linked_reservation_entity_type": (
                transfer.linked_reservation_ref.entity_type
                if transfer.linked_reservation_ref
                else None
            ),
            "version": transfer.version,
        }
        if include_id:
            values["transfer_id"] = transfer.transfer_id.value
        return values

    def get_by_id(self, transfer_id: TypedId) -> StockTransfer | None:
        row = self.connection.execute(
            select(stock_transfers_table).where(
                stock_transfers_table.c.transfer_id == transfer_id.value
            )
        ).fetchone()
        if row is None:
            return None
        return self._map(row)

    def _map(self, row: Row[Any]) -> StockTransfer:
        return StockTransfer(
            transfer_id=TypedId(entity_type="stock_transfer", value=row.transfer_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            part_ref=TypedId(entity_type="part", value=row.part_id),
            from_location_ref=TypedId(entity_type="stock_location", value=row.from_location_id),
            to_location_ref=TypedId(entity_type="stock_location", value=row.to_location_id),
            qty=row.qty,
            state=TransferState(row.state),
            qty_received=row.qty_received,
            linked_reservation_ref=(
                TypedId(
                    entity_type=row.linked_reservation_entity_type,
                    value=row.linked_reservation_id,
                )
                if row.linked_reservation_id is not None
                else None
            ),
            version=row.version,
        )
