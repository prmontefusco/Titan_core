"""Persistência da entidade de referência `StockLocation` — Titan Asset (A3).

Sem invariante transacional forte própria (`06_AGGREGATE_ANALYSIS.md` §2) —
sem tabela filha, sem coleção de VOs. Mesmo padrão de
`customer_site_repository.py` sem a parte de sincronização de filhos.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    ForeignKeyConstraint,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.asset_domain.inventory import StockLocation, StockLocationKind
from packages.asset_infrastructure.persistence.metadata import asset_metadata
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.shared_kernel import OrganizationId, TypedId

stock_locations_table = Table(
    "stock_locations",
    asset_metadata,
    Column("location_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("kind", String(30), nullable=False),
    Column("code", String(100), nullable=False),
    Column("display_name", String(200), nullable=False),
    Column("site_id", PG_UUID(as_uuid=True), nullable=True),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_stock_locations_organization",
    ),
    ForeignKeyConstraint(
        ["site_id"],
        ["core_audit.customer_sites.site_id"],
        name="fk_stock_locations_site",
    ),
    UniqueConstraint("record_owner_organization_id", "code", name="uq_stock_locations_owner_code"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)


@dataclass(frozen=True, slots=True)
class TransactionalStockLocationRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalStockLocationRepository exige Connection com transação ativa."
            )

    def save(self, location: StockLocation) -> None:
        self.connection.execute(
            insert(stock_locations_table).values(
                location_id=location.location_id.value,
                record_owner_organization_id=location.organization_id.value,
                kind=location.kind.value,
                code=location.code,
                display_name=location.display_name,
                site_id=location.site_ref.value if location.site_ref is not None else None,
            )
        )

    def update(self, location: StockLocation) -> None:
        self.connection.execute(
            update(stock_locations_table)
            .where(stock_locations_table.c.location_id == location.location_id.value)
            .values(
                kind=location.kind.value,
                code=location.code,
                display_name=location.display_name,
                site_id=location.site_ref.value if location.site_ref is not None else None,
            )
        )

    def get_by_id(self, location_id: TypedId) -> StockLocation | None:
        row = self.connection.execute(
            select(stock_locations_table).where(
                stock_locations_table.c.location_id == location_id.value
            )
        ).fetchone()
        if row is None:
            return None
        return self._map(row)

    def _map(self, row: Row[Any]) -> StockLocation:
        return StockLocation(
            location_id=TypedId(entity_type="stock_location", value=row.location_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            kind=StockLocationKind(row.kind),
            code=row.code,
            display_name=row.display_name,
            site_ref=(
                TypedId(entity_type="customer_site", value=row.site_id)
                if row.site_id is not None
                else None
            ),
        )
