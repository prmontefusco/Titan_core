"""Persistencia de contraparte externa local (ADR-0042)."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    String,
    Table,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.external_counterparty_service import (
    ExternalCounterpartyRepositoryPort,
)
from packages.livestock_domain.external_counterparty import CounterpartyType, ExternalCounterparty
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

external_counterparties_table = Table(
    "external_counterparties",
    livestock_metadata,
    Column("counterparty_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("name", String(255), nullable=False),
    Column("counterparty_type", String(40), nullable=False),
    Column("identifiers", JSONB, nullable=False, server_default="[]"),
    Column("evidence_references", JSONB, nullable=False, server_default="[]"),
    Column("notes", String(500), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_external_counterparties_organization",
    ),
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    schema=CORE_AUDIT_SCHEMA,
)


@dataclass(frozen=True, slots=True)
class TransactionalExternalCounterpartyRepository(ExternalCounterpartyRepositoryPort):
    connection: Connection

    def save(self, counterparty: ExternalCounterparty) -> None:
        self.connection.execute(
            insert(external_counterparties_table).values(
                counterparty_id=counterparty.counterparty_id.value,
                record_owner_organization_id=counterparty.organization_id.value,
                name=counterparty.name,
                counterparty_type=counterparty.counterparty_type.value,
                identifiers=json.dumps(list(counterparty.identifiers)),
                evidence_references=json.dumps(
                    [reference_to_dict(r) for r in counterparty.evidence_references]
                ),
                notes=counterparty.notes,
                created_at=counterparty.created_at,
            )
        )

    def get_by_id(self, counterparty_id: TypedId) -> ExternalCounterparty | None:
        row = self.connection.execute(
            select(external_counterparties_table).where(
                external_counterparties_table.c.counterparty_id == counterparty_id.value
            )
        ).one_or_none()
        return None if row is None else self._map(row)

    def list_by_organization(self, organization_id: OrganizationId) -> list[ExternalCounterparty]:
        rows = self.connection.execute(
            select(external_counterparties_table)
            .where(
                external_counterparties_table.c.record_owner_organization_id
                == organization_id.value
            )
            .order_by(external_counterparties_table.c.created_at)
        ).all()
        return [self._map(row) for row in rows]

    def _map(self, row: Row[Any]) -> ExternalCounterparty:
        def _aware(value: datetime) -> datetime:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        identifiers = row.identifiers
        if isinstance(identifiers, str):
            identifiers = json.loads(identifiers)
        references = row.evidence_references
        if isinstance(references, str):
            references = json.loads(references)

        return ExternalCounterparty(
            counterparty_id=TypedId(entity_type="external_counterparty", value=row.counterparty_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            name=row.name,
            counterparty_type=CounterpartyType(row.counterparty_type),
            identifiers=tuple(identifiers or []),
            evidence_references=tuple(
                reference
                for reference in (reference_from_dict(item) for item in (references or []))
                if reference is not None
            ),
            notes=row.notes,
            created_at=_aware(row.created_at),
        )
