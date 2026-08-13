"""Persistência do artefato de captura externa da ADR-0058."""

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.external_source_capture_service import (
    ExternalSourceCaptureArtifactRepositoryPort,
    ExternalSourceCaptureAssociationReviewRepositoryPort,
)
from packages.livestock_domain.external_source_capture import (
    ExternalSourceCaptureArtifact,
    ExternalSourceCaptureAssociationReview,
    ExternalSourceCaptureAssociationReviewStatus,
    ExternalSourceEnvironment,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

external_source_capture_artifacts_table = Table(
    "external_source_capture_artifacts",
    livestock_metadata,
    Column("artifact_id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "record_owner_organization_id",
        PG_UUID(as_uuid=True),
        ForeignKey("core_identity.organizations.organization_id"),
        nullable=False,
    ),
    Column("source_profile_code", String(120), nullable=False),
    Column("source_environment", String(40), nullable=False),
    Column("contract_version", String(120), nullable=False),
    Column("resource_kind", String(40), nullable=False),
    Column("request_scope_digest", String(64), nullable=False),
    Column("transport_outcome", String(40), nullable=False),
    Column("response_status_code", Integer, nullable=True),
    Column("response_digest", String(64), nullable=True),
    Column("captured_at", DateTime(timezone=True), nullable=False),
    Column("parser_name", String(120), nullable=False),
    Column("parser_version", String(40), nullable=False),
    Column("parsing_diagnostic_code", String(120), nullable=True),
    Column("review_projection", JSONB, nullable=True),
    Column("recorded_by", PG_UUID(as_uuid=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Index(
        "ix_external_source_capture_artifacts_organization_captured",
        "record_owner_organization_id",
        "captured_at",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
)

external_source_capture_association_reviews_table = Table(
    "external_source_capture_association_reviews",
    livestock_metadata,
    Column("review_id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "record_owner_organization_id",
        PG_UUID(as_uuid=True),
        ForeignKey("core_identity.organizations.organization_id"),
        nullable=False,
    ),
    Column(
        "capture_artifact_id",
        PG_UUID(as_uuid=True),
        ForeignKey("core_audit.external_source_capture_artifacts.artifact_id"),
        nullable=False,
    ),
    Column(
        "candidate_animal_id",
        PG_UUID(as_uuid=True),
        ForeignKey("core_audit.animals.animal_id"),
        nullable=False,
    ),
    Column("status", String(40), nullable=False),
    Column("basis_code", String(120), nullable=False),
    Column("reviewed_by", PG_UUID(as_uuid=True), nullable=False),
    Column("reviewed_at", DateTime(timezone=True), nullable=False),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalExternalSourceCaptureArtifactRepository(
    ExternalSourceCaptureArtifactRepositoryPort
):
    connection: Connection

    def save(self, artifact: ExternalSourceCaptureArtifact) -> None:
        self.connection.execute(
            insert(external_source_capture_artifacts_table).values(
                artifact_id=artifact.artifact_id.value,
                record_owner_organization_id=artifact.organization_id.value,
                source_profile_code=artifact.source_profile_code,
                source_environment=artifact.source_environment.value,
                contract_version=artifact.contract_version,
                resource_kind=artifact.resource_kind,
                request_scope_digest=artifact.request_scope_digest,
                transport_outcome=artifact.transport_outcome,
                response_status_code=artifact.response_status_code,
                response_digest=artifact.response_digest,
                captured_at=artifact.captured_at,
                parser_name=artifact.parser_name,
                parser_version=artifact.parser_version,
                parsing_diagnostic_code=artifact.parsing_diagnostic_code,
                review_projection=None
                if artifact.review_projection is None
                else dict(artifact.review_projection),
                recorded_by=artifact.recorded_by.value,
                recorded_at=artifact.recorded_at,
            )
        )

    def list_by_organization(
        self, organization_id: OrganizationId
    ) -> list[ExternalSourceCaptureArtifact]:
        rows = self.connection.execute(
            select(external_source_capture_artifacts_table)
            .where(
                external_source_capture_artifacts_table.c.record_owner_organization_id
                == organization_id.value
            )
            .order_by(external_source_capture_artifacts_table.c.captured_at)
        ).all()
        return [self._map(row) for row in rows]

    @staticmethod
    def _map(row: Row[Any]) -> ExternalSourceCaptureArtifact:
        def aware(value: datetime) -> datetime:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        return ExternalSourceCaptureArtifact(
            TypedId("external_source_capture_artifact", row.artifact_id),
            OrganizationId(row.record_owner_organization_id),
            row.source_profile_code,
            ExternalSourceEnvironment(row.source_environment),
            row.contract_version,
            row.resource_kind,
            row.request_scope_digest,
            row.transport_outcome,
            row.response_status_code,
            row.response_digest,
            aware(row.captured_at),
            row.parser_name,
            row.parser_version,
            row.parsing_diagnostic_code,
            TypedId("actor", row.recorded_by),
            None
            if row.review_projection is None
            else MappingProxyType(dict(row.review_projection)),
            aware(row.recorded_at),
        )


@dataclass(frozen=True, slots=True)
class TransactionalExternalSourceCaptureAssociationReviewRepository(
    ExternalSourceCaptureAssociationReviewRepositoryPort
):
    connection: Connection

    def save(self, review: ExternalSourceCaptureAssociationReview) -> None:
        self.connection.execute(
            insert(external_source_capture_association_reviews_table).values(
                review_id=review.review_id.value,
                record_owner_organization_id=review.organization_id.value,
                capture_artifact_id=review.capture_artifact_id.value,
                candidate_animal_id=review.candidate_animal_id.value,
                status=review.status.value,
                basis_code=review.basis_code,
                reviewed_by=review.reviewed_by.value,
                reviewed_at=review.reviewed_at,
            )
        )

    def list_by_capture(
        self, organization_id: OrganizationId, capture_artifact_id: TypedId
    ) -> list[ExternalSourceCaptureAssociationReview]:
        rows = self.connection.execute(
            select(external_source_capture_association_reviews_table)
            .where(
                external_source_capture_association_reviews_table.c.record_owner_organization_id
                == organization_id.value,
                external_source_capture_association_reviews_table.c.capture_artifact_id
                == capture_artifact_id.value,
            )
            .order_by(external_source_capture_association_reviews_table.c.reviewed_at)
        ).all()
        return [
            ExternalSourceCaptureAssociationReview(
                TypedId("external_source_capture_association_review", row.review_id),
                OrganizationId(row.record_owner_organization_id),
                TypedId("external_source_capture_artifact", row.capture_artifact_id),
                TypedId("animal", row.candidate_animal_id),
                ExternalSourceCaptureAssociationReviewStatus(row.status),
                row.basis_code,
                TypedId("actor", row.reviewed_by),
                row.reviewed_at
                if row.reviewed_at.tzinfo is not None
                else row.reviewed_at.replace(tzinfo=UTC),
            )
            for row in rows
        ]
