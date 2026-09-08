"""Persistence adapter for AI Explanation audit records.

The table lives in ``core_audit`` because it is protected audit material, but the
adapter belongs to Livestock infrastructure because it maps Livestock
application concepts.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.livestock_application.market_optionality import (
    MarketOptionExplanationAuditRecord,
    MarketOptionExplanationOpaqueAuditReference,
    MarketOptionExplanationReleaseDisposition,
)
from packages.shared_kernel import OrganizationId, TypedId

ai_explanation_audit_records_table = Table(
    "ai_explanation_audit_records",
    organization_metadata,
    Column("audit_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("policy_id", PG_UUID(as_uuid=True), nullable=False),
    Column("policy_version", Integer, nullable=False),
    Column("reference_time", DateTime(timezone=True), nullable=False),
    Column("knowledge_cutoff", DateTime(timezone=True), nullable=False),
    Column("requested_at", DateTime(timezone=True), nullable=False),
    Column("evaluated_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("processing_activity", Text, nullable=False),
    Column("processing_authorization_reference", Text, nullable=False),
    Column("processing_authorization_version", Integer, nullable=False),
    Column("processing_authorization_digest", Text, nullable=False),
    Column("data_contract_id", Text, nullable=False),
    Column("data_contract_version", Integer, nullable=False),
    Column("provider_profile", Text, nullable=False),
    Column("provider_profile_version", Integer, nullable=False),
    Column("provider_profile_digest", Text, nullable=False),
    Column("model_name", Text, nullable=False),
    Column("explanation_schema", Text, nullable=False),
    Column("prompt_template_id", Text, nullable=False),
    Column("prompt_template_version", Integer, nullable=False),
    Column("prompt_template_digest", Text, nullable=False),
    Column("guard_version", Integer, nullable=False),
    Column("guard_digest", Text, nullable=False),
    Column("prompt_payload_digest", Text, nullable=False),
    Column("source_reference_digest", Text, nullable=False),
    Column("source_reference_audit_references", JSONB, nullable=False),
    Column("canonical_fallback_digest", Text, nullable=False),
    Column("idempotency_reference", Text, nullable=True),
    Column("released_output_digest", Text, nullable=True),
    Column("release_disposition", String(30), nullable=False),
    Column("accepted", Boolean, nullable=False),
    Column("violation_codes", JSONB, nullable=False),
    Column("limitations", JSONB, nullable=False),
    Column("correlation_id", PG_UUID(as_uuid=True), nullable=False),
    Column("record_digest", Text, nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_ai_explanation_audit_record_owner_org",
    ),
    ForeignKeyConstraint(
        ["policy_id"],
        ["core_audit.policies.policy_id"],
        name="fk_ai_explanation_audit_policy",
    ),
    CheckConstraint("policy_version >= 1", name="ck_ai_explanation_audit_policy_version"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
)

Index(
    "uq_ai_explanation_audit_owner_record_digest",
    ai_explanation_audit_records_table.c.record_owner_organization_id,
    ai_explanation_audit_records_table.c.record_digest,
    unique=True,
)
Index(
    "ix_ai_explanation_audit_owner_created",
    ai_explanation_audit_records_table.c.record_owner_organization_id,
    ai_explanation_audit_records_table.c.created_at.desc(),
)
Index(
    "ix_ai_explanation_audit_owner_policy_temporal",
    ai_explanation_audit_records_table.c.record_owner_organization_id,
    ai_explanation_audit_records_table.c.policy_id,
    ai_explanation_audit_records_table.c.policy_version,
    ai_explanation_audit_records_table.c.reference_time,
    ai_explanation_audit_records_table.c.knowledge_cutoff,
)
Index(
    "ix_ai_explanation_audit_owner_correlation",
    ai_explanation_audit_records_table.c.record_owner_organization_id,
    ai_explanation_audit_records_table.c.correlation_id,
)
Index(
    "ix_ai_explanation_audit_owner_idempotency",
    ai_explanation_audit_records_table.c.record_owner_organization_id,
    ai_explanation_audit_records_table.c.idempotency_reference,
    postgresql_where=ai_explanation_audit_records_table.c.idempotency_reference.is_not(None),
)
Index(
    "ix_ai_explanation_audit_owner_processing_created",
    ai_explanation_audit_records_table.c.record_owner_organization_id,
    ai_explanation_audit_records_table.c.processing_activity,
    ai_explanation_audit_records_table.c.created_at.desc(),
)
Index(
    "ix_ai_explanation_audit_owner_disposition_created",
    ai_explanation_audit_records_table.c.record_owner_organization_id,
    ai_explanation_audit_records_table.c.release_disposition,
    ai_explanation_audit_records_table.c.created_at.desc(),
)

_COLUMNS = """
    audit_id,
    record_owner_organization_id,
    policy_id,
    policy_version,
    reference_time,
    knowledge_cutoff,
    requested_at,
    evaluated_at,
    created_at,
    processing_activity,
    processing_authorization_reference,
    processing_authorization_version,
    processing_authorization_digest,
    data_contract_id,
    data_contract_version,
    provider_profile,
    provider_profile_version,
    provider_profile_digest,
    model_name,
    explanation_schema,
    prompt_template_id,
    prompt_template_version,
    prompt_template_digest,
    guard_version,
    guard_digest,
    prompt_payload_digest,
    source_reference_digest,
    source_reference_audit_references,
    canonical_fallback_digest,
    idempotency_reference,
    released_output_digest,
    release_disposition,
    accepted,
    violation_codes,
    limitations,
    correlation_id,
    record_digest
"""


@dataclass(frozen=True, slots=True)
class TransactionalAIExplanationAuditRepository:
    connection: Connection

    def append(self, record: MarketOptionExplanationAuditRecord) -> None:
        self.connection.execute(
            text(
                f"""
                INSERT INTO core_audit.ai_explanation_audit_records ({_COLUMNS})
                VALUES (
                    :audit_id,
                    :record_owner_organization_id,
                    :policy_id,
                    :policy_version,
                    :reference_time,
                    :knowledge_cutoff,
                    :requested_at,
                    :evaluated_at,
                    :created_at,
                    :processing_activity,
                    :processing_authorization_reference,
                    :processing_authorization_version,
                    :processing_authorization_digest,
                    :data_contract_id,
                    :data_contract_version,
                    :provider_profile,
                    :provider_profile_version,
                    :provider_profile_digest,
                    :model_name,
                    :explanation_schema,
                    :prompt_template_id,
                    :prompt_template_version,
                    :prompt_template_digest,
                    :guard_version,
                    :guard_digest,
                    :prompt_payload_digest,
                    :source_reference_digest,
                    CAST(:source_reference_audit_references AS jsonb),
                    :canonical_fallback_digest,
                    :idempotency_reference,
                    :released_output_digest,
                    :release_disposition,
                    :accepted,
                    CAST(:violation_codes AS jsonb),
                    CAST(:limitations AS jsonb),
                    :correlation_id,
                    :record_digest
                )
                """
            ),
            _to_row(record),
        )

    def get(self, audit_id: TypedId) -> MarketOptionExplanationAuditRecord | None:
        row = self.connection.execute(
            text(
                f"""
                SELECT {_COLUMNS}
                FROM core_audit.ai_explanation_audit_records
                WHERE audit_id = :audit_id
                """
            ),
            {"audit_id": audit_id.value},
        ).fetchone()
        if row is None:
            return None
        return _from_row(row)

    def find_by_correlation_id(
        self,
        *,
        record_owner_organization_id: OrganizationId,
        correlation_id: TypedId,
    ) -> tuple[MarketOptionExplanationAuditRecord, ...]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_COLUMNS}
                FROM core_audit.ai_explanation_audit_records
                WHERE record_owner_organization_id = :record_owner_organization_id
                  AND correlation_id = :correlation_id
                ORDER BY created_at DESC, audit_id DESC
                """
            ),
            {
                "record_owner_organization_id": record_owner_organization_id.value,
                "correlation_id": correlation_id.value,
            },
        ).fetchall()
        return tuple(_from_row(row) for row in rows)

    def find_by_idempotency_reference(
        self,
        *,
        record_owner_organization_id: OrganizationId,
        idempotency_reference: str,
    ) -> tuple[MarketOptionExplanationAuditRecord, ...]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_COLUMNS}
                FROM core_audit.ai_explanation_audit_records
                WHERE record_owner_organization_id = :record_owner_organization_id
                  AND idempotency_reference = :idempotency_reference
                ORDER BY created_at DESC, audit_id DESC
                """
            ),
            {
                "record_owner_organization_id": record_owner_organization_id.value,
                "idempotency_reference": idempotency_reference,
            },
        ).fetchall()
        return tuple(_from_row(row) for row in rows)

    def list_for_owner(
        self,
        record_owner_organization_id: OrganizationId,
    ) -> tuple[MarketOptionExplanationAuditRecord, ...]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_COLUMNS}
                FROM core_audit.ai_explanation_audit_records
                WHERE record_owner_organization_id = :record_owner_organization_id
                ORDER BY created_at DESC, audit_id DESC
                """
            ),
            {"record_owner_organization_id": record_owner_organization_id.value},
        ).fetchall()
        return tuple(_from_row(row) for row in rows)


def _to_row(record: MarketOptionExplanationAuditRecord) -> dict[str, Any]:
    return {
        "audit_id": record.audit_id.value,
        "record_owner_organization_id": record.record_owner_organization_id.value,
        "policy_id": record.policy_id.value,
        "policy_version": record.policy_version,
        "reference_time": record.reference_time,
        "knowledge_cutoff": record.knowledge_cutoff,
        "requested_at": record.requested_at,
        "evaluated_at": record.evaluated_at,
        "created_at": record.evaluated_at,
        "processing_activity": record.processing_activity,
        "processing_authorization_reference": record.processing_authorization_reference,
        "processing_authorization_version": record.processing_authorization_version,
        "processing_authorization_digest": record.processing_authorization_digest,
        "data_contract_id": record.data_contract_id,
        "data_contract_version": record.data_contract_version,
        "provider_profile": record.provider_profile,
        "provider_profile_version": record.provider_profile_version,
        "provider_profile_digest": record.provider_profile_digest,
        "model_name": record.model_name,
        "explanation_schema": record.explanation_schema,
        "prompt_template_id": record.prompt_template_id,
        "prompt_template_version": record.prompt_template_version,
        "prompt_template_digest": record.prompt_template_digest,
        "guard_version": record.guard_version,
        "guard_digest": record.guard_digest,
        "prompt_payload_digest": record.prompt_payload_digest,
        "source_reference_digest": record.source_reference_digest,
        "source_reference_audit_references": json.dumps(
            [dict(reference.as_mapping()) for reference in record.source_reference_audit_references]
        ),
        "canonical_fallback_digest": record.canonical_fallback_digest,
        "idempotency_reference": record.idempotency_reference,
        "released_output_digest": record.released_output_digest,
        "release_disposition": record.release_disposition.value,
        "accepted": record.accepted,
        "violation_codes": json.dumps(list(record.violation_codes)),
        "limitations": json.dumps(list(record.limitations)),
        "correlation_id": record.correlation_id.value,
        "record_digest": record.record_digest(),
    }


def _from_row(row: Any) -> MarketOptionExplanationAuditRecord:
    return MarketOptionExplanationAuditRecord(
        audit_id=TypedId("ai_explanation_audit", row.audit_id),
        record_owner_organization_id=OrganizationId(row.record_owner_organization_id),
        policy_id=TypedId("policy", row.policy_id),
        policy_version=row.policy_version,
        reference_time=_ensure_utc(row.reference_time),
        knowledge_cutoff=_ensure_utc(row.knowledge_cutoff),
        requested_at=_ensure_utc(row.requested_at),
        evaluated_at=_ensure_utc(row.evaluated_at),
        processing_activity=row.processing_activity,
        processing_authorization_reference=row.processing_authorization_reference,
        processing_authorization_version=row.processing_authorization_version,
        processing_authorization_digest=row.processing_authorization_digest,
        data_contract_id=row.data_contract_id,
        data_contract_version=row.data_contract_version,
        provider_profile=row.provider_profile,
        provider_profile_version=row.provider_profile_version,
        provider_profile_digest=row.provider_profile_digest,
        model_name=row.model_name,
        explanation_schema=row.explanation_schema,
        prompt_template_id=row.prompt_template_id,
        prompt_template_version=row.prompt_template_version,
        prompt_template_digest=row.prompt_template_digest,
        guard_version=row.guard_version,
        guard_digest=row.guard_digest,
        prompt_payload_digest=row.prompt_payload_digest,
        source_reference_digest=row.source_reference_digest,
        source_reference_audit_references=_audit_references_from_row(
            row.source_reference_audit_references
        ),
        canonical_fallback_digest=row.canonical_fallback_digest,
        idempotency_reference=row.idempotency_reference,
        released_output_digest=row.released_output_digest,
        release_disposition=MarketOptionExplanationReleaseDisposition(row.release_disposition),
        accepted=bool(row.accepted),
        violation_codes=_tuple_from_json_array(row.violation_codes),
        limitations=_tuple_from_json_array(row.limitations),
        correlation_id=TypedId("correlation", row.correlation_id),
    )


def _audit_references_from_row(
    value: Any,
) -> tuple[MarketOptionExplanationOpaqueAuditReference, ...]:
    items = json.loads(value) if isinstance(value, str) else value
    return tuple(
        MarketOptionExplanationOpaqueAuditReference(
            alias=item["alias"],
            key_version=int(item["key_version"]),
            reference=item["reference"],
        )
        for item in items
    )


def _tuple_from_json_array(value: Any) -> tuple[str, ...]:
    items = json.loads(value) if isinstance(value, str) else value
    return tuple(str(item) for item in items)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
