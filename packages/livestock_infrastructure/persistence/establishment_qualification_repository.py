"""Persistencia da qualificacao auditavel de estabelecimento por mercado."""

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
from packages.livestock_application.establishment_qualification_service import (
    EstablishmentQualificationRepositoryPort,
)
from packages.livestock_domain.establishment_qualification import (
    EstablishmentQualification,
    EstablishmentQualificationStatus,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

establishment_qualifications_table = Table(
    "establishment_qualifications",
    livestock_metadata,
    Column("qualification_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("counterparty_id", PG_UUID(as_uuid=True), nullable=False),
    Column("market_purpose", String(120), nullable=False),
    Column("qualification_status", String(40), nullable=False),
    Column("source_name", String(255), nullable=False),
    Column("source_version", String(120), nullable=True),
    Column("assessed_at", DateTime(timezone=True), nullable=False),
    Column("evidence_references", JSONB, nullable=False, server_default="[]"),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_establishment_qualifications_organization",
    ),
    ForeignKeyConstraint(
        ["counterparty_id"],
        ["core_audit.external_counterparties.counterparty_id"],
        name="fk_establishment_qualifications_counterparty",
    ),
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    schema=CORE_AUDIT_SCHEMA,
)


@dataclass(frozen=True, slots=True)
class TransactionalEstablishmentQualificationRepository(EstablishmentQualificationRepositoryPort):
    connection: Connection

    def save(self, qualification: EstablishmentQualification) -> None:
        self.connection.execute(
            insert(establishment_qualifications_table).values(
                qualification_id=qualification.qualification_id.value,
                record_owner_organization_id=qualification.organization_id.value,
                counterparty_id=qualification.counterparty_id.value,
                market_purpose=qualification.market_purpose,
                qualification_status=qualification.status.value,
                source_name=qualification.source_name,
                source_version=qualification.source_version,
                assessed_at=qualification.assessed_at,
                evidence_references=json.dumps(
                    [reference_to_dict(r) for r in qualification.evidence_references]
                ),
                recorded_at=qualification.recorded_at,
            )
        )

    def list_by_counterparty(
        self, organization_id: OrganizationId, counterparty_id: TypedId
    ) -> list[EstablishmentQualification]:
        rows = self.connection.execute(
            select(establishment_qualifications_table)
            .where(
                establishment_qualifications_table.c.record_owner_organization_id
                == organization_id.value,
                establishment_qualifications_table.c.counterparty_id == counterparty_id.value,
            )
            .order_by(
                establishment_qualifications_table.c.market_purpose,
                establishment_qualifications_table.c.assessed_at,
                establishment_qualifications_table.c.recorded_at,
            )
        ).all()
        return [self._map(row) for row in rows]

    def _map(self, row: Row[Any]) -> EstablishmentQualification:
        def _aware(value: datetime) -> datetime:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        references = row.evidence_references
        if isinstance(references, str):
            references = json.loads(references)
        return EstablishmentQualification(
            qualification_id=TypedId(
                entity_type="establishment_qualification", value=row.qualification_id
            ),
            organization_id=OrganizationId(row.record_owner_organization_id),
            counterparty_id=TypedId(entity_type="external_counterparty", value=row.counterparty_id),
            market_purpose=row.market_purpose,
            status=EstablishmentQualificationStatus(row.qualification_status),
            source_name=row.source_name,
            source_version=row.source_version,
            assessed_at=_aware(row.assessed_at),
            evidence_references=tuple(
                reference
                for reference in (reference_from_dict(item) for item in (references or []))
                if reference is not None
            ),
            recorded_at=_aware(row.recorded_at),
        )
