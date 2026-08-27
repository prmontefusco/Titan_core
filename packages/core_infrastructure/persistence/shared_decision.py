"""Persistencia de SharedDecision para BuyerPolicy Fase 3."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_domain.policy_sharing import (
    SHARED_DECISION_STATUS_REVISADA,
    SharedDecision,
)
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

shared_decisions_table = Table(
    "shared_decisions",
    organization_metadata,
    Column("decision_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("grant_id", PG_UUID(as_uuid=True), nullable=False),
    Column("evaluation_id", PG_UUID(as_uuid=True), nullable=False),
    Column("policy_id", PG_UUID(as_uuid=True), nullable=False),
    Column("proposer_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("proposal_content", Text, nullable=False),
    Column("proposal_evidence_references", JSONB, nullable=False),
    Column("proposed_at", DateTime(timezone=True), nullable=False),
    Column("reviewer_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("review_decision", String(50), nullable=True),
    Column("review_content", Text, nullable=True),
    Column("reviewed_at", DateTime(timezone=True), nullable=True),
    Column("reviewed_by", String(255), nullable=True),
    Column("status", String(20), nullable=False),
    Column("created_by", String(255), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    ForeignKeyConstraint(
        ["grant_id"],
        ["core_audit.authorization_grants.grant_id"],
        name="fk_shared_decisions_grant",
    ),
    ForeignKeyConstraint(
        ["evaluation_id"],
        ["core_audit.evaluations.evaluation_id"],
        name="fk_shared_decisions_evaluation",
    ),
    ForeignKeyConstraint(
        ["policy_id"],
        ["core_audit.policies.policy_id"],
        name="fk_shared_decisions_policy",
    ),
    ForeignKeyConstraint(
        ["proposer_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_shared_decisions_proposer_org",
    ),
    ForeignKeyConstraint(
        ["reviewer_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_shared_decisions_reviewer_org",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_shared_decisions_record_owner_org",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

Index(
    "ix_shared_decisions_policy_proposed_at",
    shared_decisions_table.c.policy_id,
    shared_decisions_table.c.proposed_at,
)
Index("ix_shared_decisions_grant", shared_decisions_table.c.grant_id)


class SharedDecisionRepositoryPort(Protocol):
    def save(self, decision: SharedDecision) -> None: ...

    def get_by_id(self, decision_id: TypedId) -> SharedDecision | None: ...

    def list_by_policy(self, policy_id: TypedId) -> list[SharedDecision]: ...

    def update_review(
        self,
        decision_id: TypedId,
        *,
        review_decision: str,
        review_content: str,
        reviewed_at: datetime,
        reviewed_by: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class TransactionalSharedDecisionRepository:
    connection: Connection

    def save(self, decision: SharedDecision) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.shared_decisions (
                    decision_id,
                    grant_id,
                    evaluation_id,
                    policy_id,
                    proposer_organization_id,
                    proposal_content,
                    proposal_evidence_references,
                    proposed_at,
                    reviewer_organization_id,
                    review_decision,
                    review_content,
                    reviewed_at,
                    reviewed_by,
                    status,
                    created_by,
                    record_owner_organization_id
                ) VALUES (
                    :decision_id,
                    :grant_id,
                    :evaluation_id,
                    :policy_id,
                    :proposer_organization_id,
                    :proposal_content,
                    :proposal_evidence_references,
                    :proposed_at,
                    :reviewer_organization_id,
                    :review_decision,
                    :review_content,
                    :reviewed_at,
                    :reviewed_by,
                    :status,
                    :created_by,
                    :record_owner_organization_id
                )
                """
            ),
            self._params(decision),
        )

    def get_by_id(self, decision_id: TypedId) -> SharedDecision | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    decision_id,
                    grant_id,
                    evaluation_id,
                    policy_id,
                    proposer_organization_id,
                    proposal_content,
                    proposal_evidence_references,
                    proposed_at,
                    reviewer_organization_id,
                    review_decision,
                    review_content,
                    reviewed_at,
                    reviewed_by,
                    status,
                    created_by,
                    record_owner_organization_id
                FROM core_audit.shared_decisions
                WHERE decision_id = :decision_id
                """
            ),
            {"decision_id": decision_id.value},
        ).fetchone()
        return self._map(row) if row is not None else None

    def list_by_policy(self, policy_id: TypedId) -> list[SharedDecision]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    decision_id,
                    grant_id,
                    evaluation_id,
                    policy_id,
                    proposer_organization_id,
                    proposal_content,
                    proposal_evidence_references,
                    proposed_at,
                    reviewer_organization_id,
                    review_decision,
                    review_content,
                    reviewed_at,
                    reviewed_by,
                    status,
                    created_by,
                    record_owner_organization_id
                FROM core_audit.shared_decisions
                WHERE policy_id = :policy_id
                ORDER BY proposed_at DESC, decision_id DESC
                """
            ),
            {"policy_id": policy_id.value},
        ).fetchall()
        return [self._map(row) for row in rows]

    def update_review(
        self,
        decision_id: TypedId,
        *,
        review_decision: str,
        review_content: str,
        reviewed_at: datetime,
        reviewed_by: str,
    ) -> None:
        self.connection.execute(
            text(
                """
                UPDATE core_audit.shared_decisions
                SET
                    status = :status,
                    review_decision = :review_decision,
                    review_content = :review_content,
                    reviewed_at = :reviewed_at,
                    reviewed_by = :reviewed_by
                WHERE decision_id = :decision_id
                """
            ),
            {
                "decision_id": decision_id.value,
                "status": SHARED_DECISION_STATUS_REVISADA,
                "review_decision": review_decision,
                "review_content": review_content,
                "reviewed_at": reviewed_at,
                "reviewed_by": reviewed_by,
            },
        )

    def _params(self, decision: SharedDecision) -> dict[str, object]:
        return {
            "decision_id": decision.decision_id.value,
            "grant_id": decision.grant_id,
            "evaluation_id": decision.evaluation_id.value,
            "policy_id": decision.policy_id.value,
            "proposer_organization_id": decision.proposer_organization_id.value,
            "proposal_content": decision.proposal_content,
            "proposal_evidence_references": json.dumps(list(decision.proposal_evidence_references)),
            "proposed_at": decision.proposed_at,
            "reviewer_organization_id": decision.reviewer_organization_id.value,
            "review_decision": decision.review_decision,
            "review_content": decision.review_content,
            "reviewed_at": decision.reviewed_at,
            "reviewed_by": decision.reviewed_by,
            "status": decision.status,
            "created_by": decision.created_by,
            "record_owner_organization_id": decision.record_owner_organization_id.value,
        }

    def _map(self, row: object) -> SharedDecision:
        raw_references = row.proposal_evidence_references  # type: ignore[attr-defined]
        if isinstance(raw_references, str):
            raw_references = json.loads(raw_references)
        proposed_at = self._ensure_utc(row.proposed_at)  # type: ignore[attr-defined]
        reviewed_at = row.reviewed_at  # type: ignore[attr-defined]
        return SharedDecision(
            decision_id=TypedId("shared_decision", row.decision_id),  # type: ignore[attr-defined]
            grant_id=row.grant_id,  # type: ignore[attr-defined]
            evaluation_id=TypedId("evaluation", row.evaluation_id),  # type: ignore[attr-defined]
            policy_id=TypedId("policy", row.policy_id),  # type: ignore[attr-defined]
            proposer_organization_id=OrganizationId(
                row.proposer_organization_id  # type: ignore[attr-defined]
            ),
            proposal_content=row.proposal_content,  # type: ignore[attr-defined]
            proposal_evidence_references=tuple(raw_references),
            proposed_at=proposed_at,
            reviewer_organization_id=OrganizationId(
                row.reviewer_organization_id  # type: ignore[attr-defined]
            ),
            review_decision=row.review_decision,  # type: ignore[attr-defined]
            review_content=row.review_content,  # type: ignore[attr-defined]
            reviewed_at=self._ensure_utc(reviewed_at) if reviewed_at is not None else None,
            reviewed_by=row.reviewed_by,  # type: ignore[attr-defined]
            status=row.status,  # type: ignore[attr-defined]
            created_by=row.created_by,  # type: ignore[attr-defined]
            record_owner_organization_id=OrganizationId(
                row.record_owner_organization_id  # type: ignore[attr-defined]
            ),
        )

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
