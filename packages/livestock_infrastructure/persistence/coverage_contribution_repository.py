"""Persistência append-only das contribuições dimensionais de coverage."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.coverage_contribution_service import (
    CoverageContributionRepositoryPort,
)
from packages.livestock_application.dimensional_coverage import (
    CoverageContribution,
    CoverageContributionAdmissibility,
    CoverageContributionValidation,
    StoredCoverageContribution,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

coverage_contributions_table = Table(
    "coverage_contributions",
    livestock_metadata,
    Column("contribution_id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "record_owner_organization_id",
        PG_UUID(as_uuid=True),
        ForeignKey("core_identity.organizations.organization_id"),
        nullable=False,
    ),
    Column(
        "subject_id",
        PG_UUID(as_uuid=True),
        ForeignKey("core_audit.animals.animal_id"),
        nullable=False,
    ),
    Column("dimension", String(120), nullable=False),
    Column("covered_from", DateTime(timezone=True), nullable=False),
    Column("covered_until", DateTime(timezone=True), nullable=False),
    Column("validation", String(40), nullable=False),
    Column("admissibility", String(40), nullable=False),
    Column("source_entity_type", String(80), nullable=True),
    Column("source_id", PG_UUID(as_uuid=True), nullable=True),
    Column("accessible", Boolean, nullable=False),
    Column("conflicting", Boolean, nullable=False),
    Column("recorded_by", PG_UUID(as_uuid=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Index(
        "ix_coverage_contributions_subject_dimension",
        "record_owner_organization_id",
        "subject_id",
        "dimension",
        "covered_from",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalCoverageContributionRepository(CoverageContributionRepositoryPort):
    connection: Connection

    def save(self, item: StoredCoverageContribution) -> None:
        source = item.contribution.source_reference
        self.connection.execute(
            insert(coverage_contributions_table).values(
                contribution_id=item.contribution_id.value,
                record_owner_organization_id=item.organization_id.value,
                subject_id=item.subject_id.value,
                dimension=item.contribution.dimension,
                covered_from=item.contribution.covered_from,
                covered_until=item.contribution.covered_until,
                validation=item.contribution.validation.value,
                admissibility=item.contribution.admissibility.value,
                source_entity_type=None if source is None else source.target_id.entity_type,
                source_id=None if source is None else source.target_id.value,
                accessible=item.contribution.accessible,
                conflicting=item.contribution.conflicting,
                recorded_by=item.recorded_by.value,
                recorded_at=item.recorded_at,
            )
        )

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[StoredCoverageContribution]:
        rows = self.connection.execute(
            select(coverage_contributions_table)
            .where(
                coverage_contributions_table.c.record_owner_organization_id
                == organization_id.value,
                coverage_contributions_table.c.subject_id == subject_id.value,
            )
            .order_by(coverage_contributions_table.c.recorded_at)
        ).all()
        return [self._map(row) for row in rows]

    @staticmethod
    def _map(row: Row[Any]) -> StoredCoverageContribution:
        def aware(value: datetime) -> datetime:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        source = (
            None
            if row.source_id is None
            else UniversalReference(
                target_id=TypedId(entity_type=row.source_entity_type, value=row.source_id),
                organization_id=OrganizationId(row.record_owner_organization_id),
                contract_version=1,
            )
        )
        return StoredCoverageContribution(
            contribution_id=TypedId(entity_type="coverage_contribution", value=row.contribution_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            subject_id=TypedId(entity_type="animal", value=row.subject_id),
            contribution=CoverageContribution(
                dimension=row.dimension,
                covered_from=aware(row.covered_from),
                covered_until=aware(row.covered_until),
                validation=CoverageContributionValidation(row.validation),
                admissibility=CoverageContributionAdmissibility(row.admissibility),
                source_reference=source,
                accessible=row.accessible,
                conflicting=row.conflicting,
            ),
            recorded_by=TypedId(entity_type="actor", value=row.recorded_by),
            recorded_at=aware(row.recorded_at),
        )
