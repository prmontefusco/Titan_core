"""Persistência do agregado `CustomerSite` — Titan Asset & Sustainment (A3).

Mapeamento SQLAlchemy Core (`Table` + repositório transacional), mesmo padrão
de `packages/livestock_infrastructure/persistence/animal_repository.py`.
`contacts` é sincronizado por delete+reinsert em `update()` (mesma técnica de
`animal_identifiers`), com `position` para preservar a ordem da tupla.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    UniqueConstraint,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.asset_domain.customer_site import CustomerSite, CustomerSiteKind, SiteContact
from packages.asset_infrastructure.persistence.metadata import asset_metadata
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.shared_kernel import OrganizationId, TypedId

customer_sites_table = Table(
    "customer_sites",
    asset_metadata,
    Column("site_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("customer_id", PG_UUID(as_uuid=True), nullable=False),
    Column("code", String(100), nullable=False),
    Column("display_name", String(200), nullable=False),
    Column("kind", String(30), nullable=False),
    Column("version", Integer, nullable=False, default=1),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_customer_sites_organization",
    ),
    UniqueConstraint("record_owner_organization_id", "code", name="uq_customer_sites_owner_code"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

customer_site_contacts_table = Table(
    "customer_site_contacts",
    asset_metadata,
    Column("site_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("position", Integer, primary_key=True),
    # Denormalizado do pai para a policy de RLS poder filtrar sem JOIN (mesmo
    # padrão de `animal_identifiers_table` em livestock_infrastructure).
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("name", String(200), nullable=False),
    Column("role", String(100), nullable=True),
    Column("email", String(200), nullable=True),
    Column("phone", String(50), nullable=True),
    ForeignKeyConstraint(
        ["site_id"],
        ["core_audit.customer_sites.site_id"],
        name="fk_customer_site_contacts_site",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)


@dataclass(frozen=True, slots=True)
class TransactionalCustomerSiteRepository:
    """`connection` precisa estar numa transação ativa — quem decide o escopo
    da transação é a camada de composição (A4/A5), não este repositório."""

    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalCustomerSiteRepository exige Connection com transação ativa."
            )

    def save(self, site: CustomerSite) -> None:
        self.connection.execute(
            insert(customer_sites_table).values(
                site_id=site.site_id.value,
                record_owner_organization_id=site.organization_id.value,
                customer_id=site.customer_ref.value,
                code=site.code,
                display_name=site.display_name,
                kind=site.kind.value,
                version=site.version,
            )
        )
        self._insert_contacts(site)

    def update(self, site: CustomerSite) -> None:
        self.connection.execute(
            update(customer_sites_table)
            .where(customer_sites_table.c.site_id == site.site_id.value)
            .values(
                code=site.code,
                display_name=site.display_name,
                kind=site.kind.value,
                version=site.version,
            )
        )
        self.connection.execute(
            delete(customer_site_contacts_table).where(
                customer_site_contacts_table.c.site_id == site.site_id.value
            )
        )
        self._insert_contacts(site)

    def _insert_contacts(self, site: CustomerSite) -> None:
        for position, contact in enumerate(site.contacts):
            self.connection.execute(
                insert(customer_site_contacts_table).values(
                    site_id=site.site_id.value,
                    position=position,
                    record_owner_organization_id=site.organization_id.value,
                    name=contact.name,
                    role=contact.role,
                    email=contact.email,
                    phone=contact.phone,
                )
            )

    def get_by_id(self, site_id: TypedId) -> CustomerSite | None:
        row = self.connection.execute(
            select(customer_sites_table).where(customer_sites_table.c.site_id == site_id.value)
        ).fetchone()
        if row is None:
            return None
        return self._map(row)

    def _map(self, row: Row[Any]) -> CustomerSite:
        contact_rows = self.connection.execute(
            select(customer_site_contacts_table)
            .where(customer_site_contacts_table.c.site_id == row.site_id)
            .order_by(customer_site_contacts_table.c.position)
        ).fetchall()
        contacts = tuple(
            SiteContact(
                name=contact_row.name,
                role=contact_row.role,
                email=contact_row.email,
                phone=contact_row.phone,
            )
            for contact_row in contact_rows
        )
        return CustomerSite(
            site_id=TypedId(entity_type="customer_site", value=row.site_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            customer_ref=TypedId(entity_type="customer", value=row.customer_id),
            code=row.code,
            display_name=row.display_name,
            kind=CustomerSiteKind(row.kind),
            contacts=contacts,
            version=row.version,
        )
