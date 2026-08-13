"""Persistência append-only do catálogo sintético de base normativa."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    Column,
    Connection,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.internal_test_normative_basis import InternalTestNormativeBasis
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

internal_test_normative_bases_table = Table(
    "internal_test_normative_bases",
    livestock_metadata,
    Column("normative_basis_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "record_owner_organization_id",
        UUID(as_uuid=True),
        ForeignKey("core_identity.organizations.organization_id"),
        nullable=False,
    ),
    Column("code", String(120), nullable=False),
    Column("version", Integer, nullable=False),
    Column("policy_id", UUID(as_uuid=True), nullable=False),
    Column("policy_code", String(160), nullable=False),
    Column("policy_version", Integer, nullable=False),
    Column("purpose", String(160), nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("valid_until", DateTime(timezone=True)),
    Column("known_at", DateTime(timezone=True), nullable=False),
    Column("approved_by", String(240), nullable=False),
    Column("approved_at", DateTime(timezone=True), nullable=False),
    Column("instrument_code", String(240), nullable=False),
    Column("instrument_version", String(120), nullable=False),
    Column("provision", String(240)),
    Column("content_digest", String(128), nullable=False),
    Column("limitations", ARRAY(Text), nullable=False),
    UniqueConstraint(
        "record_owner_organization_id",
        "code",
        "version",
        name="uq_internal_test_normative_basis_version",
    ),
    Index(
        "ix_internal_test_normative_bases_policy_temporal",
        "record_owner_organization_id",
        "policy_id",
        "known_at",
        "valid_from",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalInternalTestNormativeBasisRepository:
    connection: Connection

    def save(self, item: InternalTestNormativeBasis) -> None:
        self.connection.execute(
            insert(internal_test_normative_bases_table).values(
                normative_basis_id=item.normative_basis_id.value,
                record_owner_organization_id=item.organization_id.value,
                code=item.code,
                version=item.version,
                policy_id=item.policy_id.value,
                policy_code=item.policy_code,
                policy_version=item.policy_version,
                purpose=item.purpose,
                valid_from=item.valid_from,
                valid_until=item.valid_until,
                known_at=item.known_at,
                approved_by=item.approved_by,
                approved_at=item.approved_at,
                instrument_code=item.instrument_code,
                instrument_version=item.instrument_version,
                provision=item.provision,
                content_digest=item.content_digest,
                limitations=list(item.limitations),
            )
        )

    def list_by_policy(
        self, organization_id: OrganizationId, policy_id: TypedId
    ) -> list[InternalTestNormativeBasis]:
        rows = self.connection.execute(
            select(internal_test_normative_bases_table)
            .where(
                internal_test_normative_bases_table.c.record_owner_organization_id
                == organization_id.value,
                internal_test_normative_bases_table.c.policy_id == policy_id.value,
            )
            .order_by(internal_test_normative_bases_table.c.version)
        ).all()
        return [self._map(row) for row in rows]

    @staticmethod
    def _map(row: Row[Any]) -> InternalTestNormativeBasis:
        def aware(value: datetime | None) -> datetime | None:
            if value is not None and value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value

        valid_from = aware(row.valid_from)
        known_at = aware(row.known_at)
        approved_at = aware(row.approved_at)
        assert valid_from is not None and known_at is not None and approved_at is not None
        return InternalTestNormativeBasis(
            normative_basis_id=TypedId("normative_basis", row.normative_basis_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            code=row.code,
            version=row.version,
            policy_id=TypedId("policy", row.policy_id),
            policy_code=row.policy_code,
            policy_version=row.policy_version,
            purpose=row.purpose,
            valid_from=valid_from,
            valid_until=aware(row.valid_until),
            known_at=known_at,
            approved_by=row.approved_by,
            approved_at=approved_at,
            instrument_code=row.instrument_code,
            instrument_version=row.instrument_version,
            provision=row.provision,
            content_digest=row.content_digest,
            limitations=tuple(row.limitations),
        )
