"""Persistência de SourceArtifact e EstablishmentQualificationAssertion (ADR-0045)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_domain.evidence import ConfidenceTier
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_domain.establishment_qualification_assertion import (
    AssertionStatus,
    EstablishmentQualificationAssertion,
)
from packages.livestock_domain.qualification_source_artifact import (
    QualificationSourceArtifact,
    SourceCoverage,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

qualification_source_artifacts_table = Table(
    "qualification_source_artifacts",
    livestock_metadata,
    Column("artifact_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("source", String(120), nullable=False),
    Column("source_version", String(120), nullable=False),
    Column("content_hash", String(120), nullable=False),
    Column("snapshot_semantics", String(40), nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_qualification_source_artifacts_organization",
    ),
    UniqueConstraint(
        "record_owner_organization_id",
        "source",
        "source_version",
        name="uq_qualification_source_artifacts_identity",
    ),
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    schema=CORE_AUDIT_SCHEMA,
)

establishment_qualification_assertions_table = Table(
    "establishment_qualification_assertions",
    livestock_metadata,
    Column("assertion_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("establishment_id", PG_UUID(as_uuid=True), nullable=False),
    Column("qualification_type", String(120), nullable=False),
    Column("asserted_status", String(40), nullable=False),
    Column("effective_from", DateTime(timezone=True), nullable=True),
    Column("effective_until", DateTime(timezone=True), nullable=True),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("source_artifact_id", PG_UUID(as_uuid=True), nullable=False),
    Column("confidence_tier", String(40), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_establishment_qualification_assertions_organization",
    ),
    ForeignKeyConstraint(
        ["establishment_id"],
        ["core_audit.external_counterparties.counterparty_id"],
        name="fk_establishment_qualification_assertions_establishment",
    ),
    ForeignKeyConstraint(
        ["source_artifact_id"],
        ["core_audit.qualification_source_artifacts.artifact_id"],
        name="fk_establishment_qualification_assertions_artifact",
    ),
    Index(
        "ix_establishment_qualification_assertions_lookup",
        "record_owner_organization_id",
        "establishment_id",
        "qualification_type",
    ),
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    schema=CORE_AUDIT_SCHEMA,
)


class QualificationSourceArtifactRepositoryPort(Protocol):
    def save(self, artifact: QualificationSourceArtifact) -> None: ...

    def find_by_identity(
        self, organization_id: OrganizationId, source: str, source_version: str
    ) -> QualificationSourceArtifact | None: ...

    def find_latest_complete_snapshot(
        self, organization_id: OrganizationId, source: str
    ) -> QualificationSourceArtifact | None: ...


class EstablishmentQualificationAssertionRepositoryPort(Protocol):
    def save(self, assertion: EstablishmentQualificationAssertion) -> None: ...

    def list_by_establishment(
        self, organization_id: OrganizationId, establishment_id: TypedId
    ) -> list[EstablishmentQualificationAssertion]: ...

    def list_by_source_artifact(
        self, organization_id: OrganizationId, source_artifact_id: TypedId
    ) -> list[EstablishmentQualificationAssertion]: ...


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _aware_or_none(value: datetime | None) -> datetime | None:
    return None if value is None else _aware(value)


@dataclass(frozen=True, slots=True)
class TransactionalQualificationSourceArtifactRepository(QualificationSourceArtifactRepositoryPort):
    connection: Connection

    def save(self, artifact: QualificationSourceArtifact) -> None:
        self.connection.execute(
            insert(qualification_source_artifacts_table).values(
                artifact_id=artifact.artifact_id.value,
                record_owner_organization_id=artifact.organization_id.value,
                source=artifact.source,
                source_version=artifact.source_version,
                content_hash=artifact.content_hash,
                snapshot_semantics=artifact.snapshot_semantics.value,
                observed_at=artifact.observed_at,
                recorded_at=artifact.recorded_at,
            )
        )

    def find_by_identity(
        self, organization_id: OrganizationId, source: str, source_version: str
    ) -> QualificationSourceArtifact | None:
        row = self.connection.execute(
            select(qualification_source_artifacts_table).where(
                qualification_source_artifacts_table.c.record_owner_organization_id
                == organization_id.value,
                qualification_source_artifacts_table.c.source == source,
                qualification_source_artifacts_table.c.source_version == source_version,
            )
        ).first()
        return None if row is None else self._map(row)

    def find_latest_complete_snapshot(
        self, organization_id: OrganizationId, source: str
    ) -> QualificationSourceArtifact | None:
        row = self.connection.execute(
            select(qualification_source_artifacts_table)
            .where(
                qualification_source_artifacts_table.c.record_owner_organization_id
                == organization_id.value,
                qualification_source_artifacts_table.c.source == source,
                qualification_source_artifacts_table.c.snapshot_semantics
                == SourceCoverage.COMPLETE_SNAPSHOT.value,
            )
            .order_by(qualification_source_artifacts_table.c.observed_at.desc())
            .limit(1)
        ).first()
        return None if row is None else self._map(row)

    def _map(self, row: Row[Any]) -> QualificationSourceArtifact:
        return QualificationSourceArtifact(
            artifact_id=TypedId(entity_type="qualification_source_artifact", value=row.artifact_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            source=row.source,
            source_version=row.source_version,
            content_hash=row.content_hash,
            snapshot_semantics=SourceCoverage(row.snapshot_semantics),
            observed_at=_aware(row.observed_at),
            recorded_at=_aware(row.recorded_at),
        )


@dataclass(frozen=True, slots=True)
class TransactionalEstablishmentQualificationAssertionRepository(
    EstablishmentQualificationAssertionRepositoryPort
):
    connection: Connection

    def save(self, assertion: EstablishmentQualificationAssertion) -> None:
        self.connection.execute(
            insert(establishment_qualification_assertions_table).values(
                assertion_id=assertion.assertion_id.value,
                record_owner_organization_id=assertion.organization_id.value,
                establishment_id=assertion.establishment_id.value,
                qualification_type=assertion.qualification_type,
                asserted_status=assertion.asserted_status.value,
                effective_from=assertion.effective_from,
                effective_until=assertion.effective_until,
                observed_at=assertion.observed_at,
                source_artifact_id=assertion.source_artifact_id.value,
                confidence_tier=assertion.confidence_tier.value,
                recorded_at=assertion.recorded_at,
            )
        )

    def list_by_establishment(
        self, organization_id: OrganizationId, establishment_id: TypedId
    ) -> list[EstablishmentQualificationAssertion]:
        rows = self.connection.execute(
            select(establishment_qualification_assertions_table)
            .where(
                establishment_qualification_assertions_table.c.record_owner_organization_id
                == organization_id.value,
                establishment_qualification_assertions_table.c.establishment_id
                == establishment_id.value,
            )
            .order_by(
                establishment_qualification_assertions_table.c.qualification_type,
                establishment_qualification_assertions_table.c.observed_at,
            )
        ).all()
        return [self._map(row) for row in rows]

    def list_by_source_artifact(
        self, organization_id: OrganizationId, source_artifact_id: TypedId
    ) -> list[EstablishmentQualificationAssertion]:
        rows = self.connection.execute(
            select(establishment_qualification_assertions_table).where(
                establishment_qualification_assertions_table.c.record_owner_organization_id
                == organization_id.value,
                establishment_qualification_assertions_table.c.source_artifact_id
                == source_artifact_id.value,
            )
        ).all()
        return [self._map(row) for row in rows]

    def _map(self, row: Row[Any]) -> EstablishmentQualificationAssertion:
        return EstablishmentQualificationAssertion(
            assertion_id=TypedId(
                entity_type="establishment_qualification_assertion", value=row.assertion_id
            ),
            organization_id=OrganizationId(row.record_owner_organization_id),
            establishment_id=TypedId(
                entity_type="external_counterparty", value=row.establishment_id
            ),
            qualification_type=row.qualification_type,
            asserted_status=AssertionStatus(row.asserted_status),
            effective_from=_aware_or_none(row.effective_from),
            effective_until=_aware_or_none(row.effective_until),
            observed_at=_aware(row.observed_at),
            source_artifact_id=TypedId(
                entity_type="qualification_source_artifact", value=row.source_artifact_id
            ),
            confidence_tier=ConfidenceTier(row.confidence_tier),
            recorded_at=_aware(row.recorded_at),
        )
