"""Persistence adapter for Market Supply query audit records.

The table lives in ``core_audit`` because it is protected audit material, but the
adapter belongs to Livestock infrastructure because it maps Livestock
application concepts.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
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
from packages.core_infrastructure.persistence.organizations import (
    organization_metadata,
    set_local_organization_context,
)
from packages.livestock_application.market_supply_audit import (
    MarketSupplyAuditExternalDisposition,
    MarketSupplyAuditOutcome,
    MarketSupplyQueryAuditRecord,
    MarketSupplyRevocationState,
)
from packages.livestock_application.market_supply_privacy import (
    AggregationQueryFingerprint,
    DisclosureDecisionState,
)
from packages.shared_kernel import (
    CanonicalSerializer,
    OrganizationId,
    TypedId,
    canonicalize_for_hash,
)

market_supply_query_audit_records_table = Table(
    "market_supply_query_audit_records",
    organization_metadata,
    Column("audit_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("requester_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("beneficiary_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("access_purpose", Text, nullable=False),
    Column("authorization_context_digest", Text, nullable=False),
    Column("policy_id", PG_UUID(as_uuid=True), nullable=False),
    Column("policy_version", Integer, nullable=False),
    Column("privacy_profile_id", Text, nullable=False),
    Column("privacy_profile_version", Integer, nullable=False),
    Column("candidate_population_digest", Text, nullable=False),
    Column("population_digest", Text, nullable=True),
    Column("query_fingerprint_digest", Text, nullable=False),
    Column("policy_context_digest", Text, nullable=False),
    Column("filter_fingerprint", Text, nullable=False),
    Column("result_subject_count", Integer, nullable=False),
    Column("reference_time", DateTime(timezone=True), nullable=False),
    Column("knowledge_cutoff", DateTime(timezone=True), nullable=False),
    Column("requested_at", DateTime(timezone=True), nullable=False),
    Column("evaluated_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("disclosure_state", String(20), nullable=False),
    Column("decision_reason_codes", JSONB, nullable=False),
    Column("outcome", String(50), nullable=False),
    Column("external_disposition", String(50), nullable=False),
    Column("result_digest", Text, nullable=True),
    Column("revocation_state", String(50), nullable=False),
    Column("correlation_id", PG_UUID(as_uuid=True), nullable=False),
    Column("idempotency_reference", Text, nullable=False),
    Column("semantic_request_digest", Text, nullable=False),
    Column("grant_id", PG_UUID(as_uuid=True), nullable=True),
    Column("record_digest", Text, nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_market_supply_query_audit_record_owner_org",
    ),
    ForeignKeyConstraint(
        ["requester_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_market_supply_query_audit_requester_org",
    ),
    ForeignKeyConstraint(
        ["beneficiary_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_market_supply_query_audit_beneficiary_org",
    ),
    ForeignKeyConstraint(
        ["policy_id"],
        ["core_audit.policies.policy_id"],
        name="fk_market_supply_query_audit_policy",
    ),
    ForeignKeyConstraint(
        ["grant_id"],
        ["core_audit.authorization_grants.grant_id"],
        name="fk_market_supply_query_audit_grant",
    ),
    CheckConstraint("policy_version >= 1", name="ck_market_supply_query_audit_policy_version"),
    CheckConstraint(
        "privacy_profile_version >= 1",
        name="ck_market_supply_query_audit_privacy_profile_version",
    ),
    CheckConstraint(
        "result_subject_count >= 0",
        name="ck_market_supply_query_audit_result_subject_count",
    ),
    CheckConstraint("access_purpose <> ''", name="ck_market_supply_query_audit_purpose"),
    CheckConstraint(
        "authorization_context_digest <> ''",
        name="ck_market_supply_query_audit_authorization_digest",
    ),
    CheckConstraint(
        "privacy_profile_id <> ''",
        name="ck_market_supply_query_audit_privacy_profile",
    ),
    CheckConstraint(
        "candidate_population_digest <> ''",
        name="ck_market_supply_query_audit_candidate_digest",
    ),
    CheckConstraint(
        "query_fingerprint_digest <> ''",
        name="ck_market_supply_query_audit_fingerprint_digest",
    ),
    CheckConstraint(
        "policy_context_digest <> ''",
        name="ck_market_supply_query_audit_policy_context_digest",
    ),
    CheckConstraint("filter_fingerprint <> ''", name="ck_market_supply_query_audit_filter"),
    CheckConstraint(
        "idempotency_reference <> ''",
        name="ck_market_supply_query_audit_idempotency_reference",
    ),
    CheckConstraint(
        "semantic_request_digest <> ''",
        name="ck_market_supply_query_audit_semantic_request_digest",
    ),
    CheckConstraint("record_digest <> ''", name="ck_market_supply_query_audit_record_digest"),
    CheckConstraint(
        "outcome IN ('RELEASED', 'DENIED_BY_AUTHORIZATION', 'PURPOSE_MISMATCH', "
        "'GRANT_REVOKED', 'SUPPRESSED_BY_PRIVACY')",
        name="ck_market_supply_query_audit_outcome",
    ),
    CheckConstraint(
        "external_disposition IN ('RELEASE_AGGREGATE', 'UNIFORM_NOT_RELEASED')",
        name="ck_market_supply_query_audit_external_disposition",
    ),
    CheckConstraint(
        "disclosure_state IN ('ALLOW', 'GENERALIZE', 'SUPPRESS', 'DENY')",
        name="ck_market_supply_query_audit_disclosure_state",
    ),
    CheckConstraint(
        "revocation_state IN ('NOT_APPLICABLE', 'NOT_REVOKED', 'REVOKED_OBSERVED')",
        name="ck_market_supply_query_audit_revocation_state",
    ),
    CheckConstraint(
        "(outcome = 'RELEASED' AND external_disposition = 'RELEASE_AGGREGATE') "
        "OR (outcome <> 'RELEASED' AND external_disposition = 'UNIFORM_NOT_RELEASED')",
        name="ck_market_supply_query_audit_release_disposition",
    ),
    CheckConstraint(
        "(outcome = 'RELEASED' AND result_digest IS NOT NULL) "
        "OR (outcome <> 'RELEASED' AND result_digest IS NULL)",
        name="ck_market_supply_query_audit_result_digest",
    ),
    CheckConstraint(
        "population_digest IS NOT NULL OR outcome <> 'RELEASED'",
        name="ck_market_supply_query_audit_population_digest",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
)

Index(
    "uq_market_supply_query_audit_record_digest",
    market_supply_query_audit_records_table.c.record_digest,
    unique=True,
)
Index(
    "ix_market_supply_query_audit_requester_purpose_requested",
    market_supply_query_audit_records_table.c.requester_organization_id,
    market_supply_query_audit_records_table.c.access_purpose,
    market_supply_query_audit_records_table.c.requested_at.desc(),
)
Index(
    "ix_market_supply_query_audit_beneficiary_purpose_requested",
    market_supply_query_audit_records_table.c.beneficiary_organization_id,
    market_supply_query_audit_records_table.c.access_purpose,
    market_supply_query_audit_records_table.c.requested_at.desc(),
)
Index(
    "ix_market_supply_query_audit_related_fingerprint",
    market_supply_query_audit_records_table.c.requester_organization_id,
    market_supply_query_audit_records_table.c.beneficiary_organization_id,
    market_supply_query_audit_records_table.c.access_purpose,
    market_supply_query_audit_records_table.c.policy_context_digest,
    market_supply_query_audit_records_table.c.requested_at.desc(),
)
Index(
    "ix_market_supply_query_audit_policy_window",
    market_supply_query_audit_records_table.c.policy_id,
    market_supply_query_audit_records_table.c.policy_version,
    market_supply_query_audit_records_table.c.reference_time,
    market_supply_query_audit_records_table.c.knowledge_cutoff,
)
Index(
    "ix_market_supply_query_audit_candidate_population",
    market_supply_query_audit_records_table.c.candidate_population_digest,
)
Index(
    "ix_market_supply_query_audit_population",
    market_supply_query_audit_records_table.c.population_digest,
    postgresql_where=market_supply_query_audit_records_table.c.population_digest.is_not(None),
)
Index(
    "ix_market_supply_query_audit_semantic_request",
    market_supply_query_audit_records_table.c.requester_organization_id,
    market_supply_query_audit_records_table.c.idempotency_reference,
    market_supply_query_audit_records_table.c.semantic_request_digest,
)
Index(
    "ix_market_supply_query_audit_correlation",
    market_supply_query_audit_records_table.c.correlation_id,
)
Index(
    "ix_market_supply_query_audit_grant",
    market_supply_query_audit_records_table.c.grant_id,
    postgresql_where=market_supply_query_audit_records_table.c.grant_id.is_not(None),
)

_SERIALIZER = CanonicalSerializer()

_COLUMNS = """
    audit_id,
    record_owner_organization_id,
    requester_organization_id,
    beneficiary_organization_id,
    access_purpose,
    authorization_context_digest,
    policy_id,
    policy_version,
    privacy_profile_id,
    privacy_profile_version,
    candidate_population_digest,
    population_digest,
    query_fingerprint_digest,
    policy_context_digest,
    filter_fingerprint,
    result_subject_count,
    reference_time,
    knowledge_cutoff,
    requested_at,
    evaluated_at,
    created_at,
    disclosure_state,
    decision_reason_codes,
    outcome,
    external_disposition,
    result_digest,
    revocation_state,
    correlation_id,
    idempotency_reference,
    semantic_request_digest,
    grant_id,
    record_digest
"""


@dataclass(frozen=True, slots=True)
class TransactionalMarketSupplyQueryAuditRepository:
    connection: Connection

    def append(self, record: MarketSupplyQueryAuditRecord) -> None:
        self.connection.execute(
            text(
                f"""
                INSERT INTO core_audit.market_supply_query_audit_records ({_COLUMNS})
                VALUES (
                    :audit_id,
                    :record_owner_organization_id,
                    :requester_organization_id,
                    :beneficiary_organization_id,
                    :access_purpose,
                    :authorization_context_digest,
                    :policy_id,
                    :policy_version,
                    :privacy_profile_id,
                    :privacy_profile_version,
                    :candidate_population_digest,
                    :population_digest,
                    :query_fingerprint_digest,
                    :policy_context_digest,
                    :filter_fingerprint,
                    :result_subject_count,
                    :reference_time,
                    :knowledge_cutoff,
                    :requested_at,
                    :evaluated_at,
                    :created_at,
                    :disclosure_state,
                    CAST(:decision_reason_codes AS jsonb),
                    :outcome,
                    :external_disposition,
                    :result_digest,
                    :revocation_state,
                    :correlation_id,
                    :idempotency_reference,
                    :semantic_request_digest,
                    :grant_id,
                    :record_digest
                )
                """
            ),
            _to_row(record),
        )

    def get(self, audit_id: TypedId) -> MarketSupplyQueryAuditRecord | None:
        row = self.connection.execute(
            text(
                f"""
                SELECT {_COLUMNS}
                FROM core_audit.market_supply_query_audit_records
                WHERE audit_id = :audit_id
                """
            ),
            {"audit_id": audit_id.value},
        ).fetchone()
        if row is None:
            return None
        return _from_row(row)

    def find_related(
        self,
        *,
        requester_organization_id: OrganizationId,
        beneficiary_organization_id: OrganizationId,
        access_purpose: str,
        policy_context_digest: str,
    ) -> tuple[MarketSupplyQueryAuditRecord, ...]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_COLUMNS}
                FROM core_audit.market_supply_query_audit_records
                WHERE requester_organization_id = :requester_organization_id
                  AND beneficiary_organization_id = :beneficiary_organization_id
                  AND access_purpose = :access_purpose
                  AND policy_context_digest = :policy_context_digest
                ORDER BY requested_at DESC, audit_id DESC
                """
            ),
            {
                "requester_organization_id": requester_organization_id.value,
                "beneficiary_organization_id": beneficiary_organization_id.value,
                "access_purpose": access_purpose,
                "policy_context_digest": policy_context_digest,
            },
        ).fetchall()
        return tuple(_from_row(row) for row in rows)

    def find_related_query_fingerprints(
        self,
        *,
        requester_organization_id: OrganizationId,
        beneficiary_organization_id: OrganizationId,
        access_purpose: str,
        policy_context_digest: str,
    ) -> tuple[AggregationQueryFingerprint, ...]:
        return tuple(
            record.query_fingerprint
            for record in self.find_related(
                requester_organization_id=requester_organization_id,
                beneficiary_organization_id=beneficiary_organization_id,
                access_purpose=access_purpose,
                policy_context_digest=policy_context_digest,
            )
        )


@dataclass(frozen=True, slots=True)
class TransactionalMarketSupplyOwnerScopedQueryAuditRepository:
    """Application-mediated owner-scoped audit repository for Market Supply F3.5.

    Raw audit remains owner-only by RLS. The buyer request can start under buyer
    context, but audit writes and related-history reads are executed in the
    contributor owner context and then restore the previous context.
    """

    connection: Connection

    def append(self, record: MarketSupplyQueryAuditRecord) -> None:
        previous_organization_id = self._current_organization_id()
        set_local_organization_context(self.connection, record.audit_owner_organization_id)
        try:
            TransactionalMarketSupplyQueryAuditRepository(self.connection).append(record)
        finally:
            self._restore_organization_context(previous_organization_id)

    def get(self, audit_id: TypedId) -> MarketSupplyQueryAuditRecord | None:
        return TransactionalMarketSupplyQueryAuditRepository(self.connection).get(audit_id)

    def find_related(
        self,
        *,
        requester_organization_id: OrganizationId,
        beneficiary_organization_id: OrganizationId,
        access_purpose: str,
        policy_context_digest: str,
    ) -> tuple[MarketSupplyQueryAuditRecord, ...]:
        return TransactionalMarketSupplyQueryAuditRepository(self.connection).find_related(
            requester_organization_id=requester_organization_id,
            beneficiary_organization_id=beneficiary_organization_id,
            access_purpose=access_purpose,
            policy_context_digest=policy_context_digest,
        )

    def find_related_query_fingerprints(
        self,
        *,
        requester_organization_id: OrganizationId,
        beneficiary_organization_id: OrganizationId,
        access_purpose: str,
        policy_context_digest: str,
    ) -> tuple[AggregationQueryFingerprint, ...]:
        return TransactionalMarketSupplyQueryAuditRepository(
            self.connection,
        ).find_related_query_fingerprints(
            requester_organization_id=requester_organization_id,
            beneficiary_organization_id=beneficiary_organization_id,
            access_purpose=access_purpose,
            policy_context_digest=policy_context_digest,
        )

    def find_related_query_fingerprints_for_owner(
        self,
        *,
        owner_organization_id: OrganizationId,
        requester_organization_id: OrganizationId,
        beneficiary_organization_id: OrganizationId,
        access_purpose: str,
        policy_context_digest: str,
    ) -> tuple[AggregationQueryFingerprint, ...]:
        # Existing F3.5 single-owner orchestration evaluates one owner-scoped
        # contribution at a time. Multi-owner history completeness still requires
        # an explicit correlation layer before aggregate release.
        previous_organization_id = self._current_organization_id()
        set_local_organization_context(self.connection, owner_organization_id)
        try:
            return self.find_related_query_fingerprints(
                requester_organization_id=requester_organization_id,
                beneficiary_organization_id=beneficiary_organization_id,
                access_purpose=access_purpose,
                policy_context_digest=policy_context_digest,
            )
        finally:
            self._restore_organization_context(previous_organization_id)

    def _current_organization_id(self) -> OrganizationId | None:
        raw = self.connection.execute(
            text("SELECT NULLIF(current_setting('titan.organization_id', true), '')::uuid"),
        ).scalar_one_or_none()
        if raw is None:
            return None
        return OrganizationId(raw)

    def _restore_organization_context(self, organization_id: OrganizationId | None) -> None:
        if organization_id is None:
            self.connection.execute(
                text("SELECT set_config('titan.organization_id', '', true)"),
            )
            return
        set_local_organization_context(self.connection, organization_id)


def _query_fingerprint_digest(fingerprint: AggregationQueryFingerprint) -> str:
    return hashlib.sha256(
        _SERIALIZER.serialize(
            canonicalize_for_hash(
                {
                    "schema": "titan.market_supply.query_fingerprint",
                    "version": 1,
                    "requester_organization_id": str(fingerprint.requester_organization_id.value),
                    "beneficiary_organization_id": str(
                        fingerprint.beneficiary_organization_id.value,
                    ),
                    "access_purpose": fingerprint.access_purpose,
                    "policy_context_digest": fingerprint.policy_context_digest,
                    "filter_fingerprint": fingerprint.filter_fingerprint,
                    "result_subject_count": fingerprint.result_subject_count,
                    "requested_at": fingerprint.requested_at,
                },
            ),
        ),
    ).hexdigest()


def _to_row(record: MarketSupplyQueryAuditRecord) -> dict[str, Any]:
    return {
        "audit_id": record.audit_id.value,
        "record_owner_organization_id": record.audit_owner_organization_id.value,
        "requester_organization_id": record.requester_organization_id.value,
        "beneficiary_organization_id": record.beneficiary_organization_id.value,
        "access_purpose": record.access_purpose,
        "authorization_context_digest": record.authorization_context_digest,
        "policy_id": record.policy_id.value,
        "policy_version": record.policy_version,
        "privacy_profile_id": record.privacy_profile_id,
        "privacy_profile_version": record.privacy_profile_version,
        "candidate_population_digest": record.candidate_population_digest,
        "population_digest": record.population_digest,
        "query_fingerprint_digest": _query_fingerprint_digest(record.query_fingerprint),
        "policy_context_digest": record.query_fingerprint.policy_context_digest,
        "filter_fingerprint": record.query_fingerprint.filter_fingerprint,
        "result_subject_count": record.query_fingerprint.result_subject_count,
        "reference_time": record.reference_time,
        "knowledge_cutoff": record.knowledge_cutoff,
        "requested_at": record.requested_at,
        "evaluated_at": record.evaluated_at,
        "created_at": record.evaluated_at,
        "disclosure_state": record.disclosure_state.value,
        "decision_reason_codes": json.dumps(list(record.decision_reason_codes), sort_keys=True),
        "outcome": record.outcome.value,
        "external_disposition": record.external_disposition.value,
        "result_digest": record.result_digest,
        "revocation_state": record.revocation_state.value,
        "correlation_id": record.correlation_id.value,
        "idempotency_reference": record.idempotency_reference,
        "semantic_request_digest": record.semantic_request_digest,
        "grant_id": record.grant_id,
        "record_digest": record.record_digest(),
    }


def _from_row(row: object) -> MarketSupplyQueryAuditRecord:
    requested_at = _ensure_utc(row.requested_at)  # type: ignore[attr-defined]
    query_fingerprint = AggregationQueryFingerprint(
        requester_organization_id=OrganizationId(
            row.requester_organization_id,  # type: ignore[attr-defined]
        ),
        beneficiary_organization_id=OrganizationId(
            row.beneficiary_organization_id,  # type: ignore[attr-defined]
        ),
        access_purpose=row.access_purpose,  # type: ignore[attr-defined]
        policy_context_digest=row.policy_context_digest,  # type: ignore[attr-defined]
        filter_fingerprint=row.filter_fingerprint,  # type: ignore[attr-defined]
        result_subject_count=row.result_subject_count,  # type: ignore[attr-defined]
        requested_at=requested_at,
    )
    return MarketSupplyQueryAuditRecord(
        audit_id=TypedId(
            "market_supply_query_audit",
            row.audit_id,  # type: ignore[attr-defined]
        ),
        audit_owner_organization_id=OrganizationId(
            row.record_owner_organization_id,  # type: ignore[attr-defined]
        ),
        requester_organization_id=OrganizationId(
            row.requester_organization_id,  # type: ignore[attr-defined]
        ),
        beneficiary_organization_id=OrganizationId(
            row.beneficiary_organization_id,  # type: ignore[attr-defined]
        ),
        access_purpose=row.access_purpose,  # type: ignore[attr-defined]
        authorization_context_digest=row.authorization_context_digest,  # type: ignore[attr-defined]
        policy_id=TypedId("policy", row.policy_id),  # type: ignore[attr-defined]
        policy_version=row.policy_version,  # type: ignore[attr-defined]
        privacy_profile_id=row.privacy_profile_id,  # type: ignore[attr-defined]
        privacy_profile_version=row.privacy_profile_version,  # type: ignore[attr-defined]
        candidate_population_digest=row.candidate_population_digest,  # type: ignore[attr-defined]
        population_digest=row.population_digest,  # type: ignore[attr-defined]
        query_fingerprint=query_fingerprint,
        reference_time=_ensure_utc(row.reference_time),  # type: ignore[attr-defined]
        knowledge_cutoff=_ensure_utc(row.knowledge_cutoff),  # type: ignore[attr-defined]
        requested_at=requested_at,
        evaluated_at=_ensure_utc(row.evaluated_at),  # type: ignore[attr-defined]
        disclosure_state=DisclosureDecisionState(row.disclosure_state),  # type: ignore[attr-defined]
        decision_reason_codes=_decision_reason_codes(row.decision_reason_codes),  # type: ignore[attr-defined]
        outcome=MarketSupplyAuditOutcome(row.outcome),  # type: ignore[attr-defined]
        external_disposition=MarketSupplyAuditExternalDisposition(
            row.external_disposition,  # type: ignore[attr-defined]
        ),
        result_digest=row.result_digest,  # type: ignore[attr-defined]
        revocation_state=MarketSupplyRevocationState(row.revocation_state),  # type: ignore[attr-defined]
        correlation_id=TypedId("correlation", row.correlation_id),  # type: ignore[attr-defined]
        idempotency_reference=row.idempotency_reference,  # type: ignore[attr-defined]
        semantic_request_digest=row.semantic_request_digest,  # type: ignore[attr-defined]
        grant_id=row.grant_id,  # type: ignore[attr-defined]
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _decision_reason_codes(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        decoded = json.loads(value)
    else:
        decoded = value
    return tuple(str(item) for item in decoded)
