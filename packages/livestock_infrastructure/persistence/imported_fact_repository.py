"""Persistencia de fatos importados da vertical Livestock (ADR-0042)."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
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

from packages.core_domain.evidence import ConfidenceTier
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.imported_fact_service import (
    ImportedLivestockFactRepositoryPort,
)
from packages.livestock_domain.imported_fact import FactOrigin, ImportedLivestockFact
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

imported_livestock_facts_table = Table(
    "imported_livestock_facts",
    livestock_metadata,
    Column("imported_fact_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("animal_id", PG_UUID(as_uuid=True), nullable=False),
    Column("source_artifact_id", PG_UUID(as_uuid=True), nullable=False),
    Column("fact_type", String(120), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("asserted_by", String(255), nullable=False),
    Column("received_by", PG_UUID(as_uuid=True), nullable=False),
    Column("origin", String(40), nullable=False),
    Column("confidence_tier", String(40), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("imported_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_imported_livestock_facts_organization",
    ),
    ForeignKeyConstraint(
        ["animal_id"],
        ["core_audit.animals.animal_id"],
        name="fk_imported_livestock_facts_animal",
    ),
    ForeignKeyConstraint(
        ["source_artifact_id"],
        ["core_audit.received_transfer_artifacts.artifact_id"],
        name="fk_imported_livestock_facts_artifact",
    ),
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    schema=CORE_AUDIT_SCHEMA,
)


@dataclass(frozen=True, slots=True)
class TransactionalImportedLivestockFactRepository(ImportedLivestockFactRepositoryPort):
    connection: Connection

    def save(self, fact: ImportedLivestockFact) -> None:
        self.connection.execute(
            insert(imported_livestock_facts_table).values(
                imported_fact_id=fact.imported_fact_id.value,
                record_owner_organization_id=fact.organization_id.value,
                animal_id=fact.animal_id.value,
                source_artifact_id=fact.source_artifact_id.value,
                fact_type=fact.fact_type,
                occurred_at=fact.occurred_at,
                asserted_by=fact.asserted_by,
                received_by=fact.received_by.value,
                origin=fact.origin.value,
                confidence_tier=fact.confidence_tier.value,
                payload=json.dumps(dict(fact.payload)),
                imported_at=fact.imported_at,
            )
        )

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[ImportedLivestockFact]:
        rows = self.connection.execute(
            select(imported_livestock_facts_table)
            .where(
                imported_livestock_facts_table.c.record_owner_organization_id
                == organization_id.value,
                imported_livestock_facts_table.c.animal_id == animal_id.value,
            )
            .order_by(imported_livestock_facts_table.c.occurred_at)
        ).all()
        return [self._map(row) for row in rows]

    def _map(self, row: Row[Any]) -> ImportedLivestockFact:
        def _aware(value: datetime) -> datetime:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        payload = row.payload
        if isinstance(payload, str):
            payload = json.loads(payload)

        return ImportedLivestockFact(
            imported_fact_id=TypedId(
                entity_type="imported_livestock_fact", value=row.imported_fact_id
            ),
            organization_id=OrganizationId(row.record_owner_organization_id),
            animal_id=TypedId(entity_type="animal", value=row.animal_id),
            source_artifact_id=TypedId(
                entity_type="received_transfer_artifact", value=row.source_artifact_id
            ),
            fact_type=row.fact_type,
            occurred_at=_aware(row.occurred_at),
            asserted_by=row.asserted_by,
            received_by=TypedId(entity_type="actor", value=row.received_by),
            origin=FactOrigin(row.origin),
            confidence_tier=ConfidenceTier(row.confidence_tier),
            payload=MappingProxyType(dict(payload or {})),
            imported_at=_aware(row.imported_at),
        )
