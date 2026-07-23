"""Repositório PostgreSQL com RLS para Decisions explicáveis (ADR-0016/Passo 6.6)."""

import json
from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_domain.decision import Decision, DecisionReason, DecisionResult
from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

decisions_table = Table(
    "decisions",
    organization_metadata,
    Column("decision_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("evaluation_id", PG_UUID(as_uuid=True), nullable=False),
    Column("evaluation_hash", String(64), nullable=False),
    Column("policy_id", PG_UUID(as_uuid=True), nullable=False),
    Column("policy_version", Integer, nullable=False),
    Column("subject_entity_type", String(100), nullable=False),
    Column("subject_id", PG_UUID(as_uuid=True), nullable=False),
    Column("purpose", String(255), nullable=False),
    Column("result", String(50), nullable=False),
    Column("engine_version", Integer, nullable=False),
    Column("issued_at", DateTime(timezone=True), nullable=False),
    Column("snapshot_hash", String(64), nullable=False),
    Column("decision_hash", String(64), nullable=False),
    Column("reasons", JSONB, nullable=False),
    Column("affected_subjects", JSONB, nullable=False, server_default="[]"),
    Column("evidence_references", JSONB, nullable=False, server_default="[]"),
    Column("corrective_actions", JSONB, nullable=False, server_default="[]"),
    CheckConstraint("policy_version >= 1", name="ck_decisions_policy_version"),
    CheckConstraint("engine_version >= 1", name="ck_decisions_engine_version"),
    CheckConstraint("jsonb_array_length(reasons) > 0", name="ck_decisions_reasons_not_empty"),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_decisions_organization",
    ),
    ForeignKeyConstraint(
        ["evaluation_id"],
        ["core_audit.evaluations.evaluation_id"],
        name="fk_decisions_evaluation",
    ),
    ForeignKeyConstraint(
        ["policy_id"],
        ["core_audit.policies.policy_id"],
        name="fk_decisions_policy",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

_SELECT_COLUMNS = """
    decision_id,
    record_owner_organization_id,
    evaluation_id,
    evaluation_hash,
    policy_id,
    policy_version,
    subject_entity_type,
    subject_id,
    purpose,
    result,
    engine_version,
    issued_at,
    snapshot_hash,
    decision_hash,
    reasons,
    affected_subjects,
    evidence_references,
    corrective_actions
"""


@dataclass(frozen=True, slots=True)
class TransactionalDecisionRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalDecisionRepository exige transacao ativa.")

    def save(self, decision: Decision) -> None:
        # Decision histórica nunca muda: gravação é estritamente append-only.
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.decisions (
                    decision_id,
                    record_owner_organization_id,
                    evaluation_id,
                    evaluation_hash,
                    policy_id,
                    policy_version,
                    subject_entity_type,
                    subject_id,
                    purpose,
                    result,
                    engine_version,
                    issued_at,
                    snapshot_hash,
                    decision_hash,
                    reasons,
                    affected_subjects,
                    evidence_references,
                    corrective_actions
                ) VALUES (
                    :decision_id,
                    :org_id,
                    :evaluation_id,
                    :evaluation_hash,
                    :policy_id,
                    :policy_version,
                    :subject_entity_type,
                    :subject_id,
                    :purpose,
                    :result,
                    :engine_version,
                    :issued_at,
                    :snapshot_hash,
                    :decision_hash,
                    :reasons,
                    :affected_subjects,
                    :evidence_references,
                    :corrective_actions
                )
                """
            ),
            {
                "decision_id": decision.decision_id.value,
                "org_id": decision.organization_id.value,
                "evaluation_id": decision.evaluation_id.value,
                "evaluation_hash": decision.evaluation_hash,
                "policy_id": decision.policy_id.value,
                "policy_version": decision.policy_version,
                "subject_entity_type": decision.subject_id.entity_type,
                "subject_id": decision.subject_id.value,
                "purpose": decision.purpose,
                "result": decision.result.value,
                "engine_version": decision.engine_version,
                "issued_at": decision.issued_at,
                "snapshot_hash": decision.snapshot_hash,
                "decision_hash": decision.decision_hash,
                "reasons": json.dumps([r.to_dict() for r in decision.reasons]),
                "affected_subjects": json.dumps(
                    [reference_to_dict(r) for r in decision.affected_subjects]
                ),
                "evidence_references": json.dumps(
                    [reference_to_dict(r) for r in decision.evidence_references]
                ),
                "corrective_actions": json.dumps(list(decision.corrective_actions)),
            },
        )

    def get_by_id(self, decision_id: TypedId) -> Decision | None:
        row = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.decisions
                WHERE decision_id = :decision_id
                """
            ),
            {"decision_id": decision_id.value},
        ).first()

        if row is None:
            return None
        return self._map_row_to_decision(row)

    def list_by_subject(
        self,
        organization_id: OrganizationId,
        subject_id: TypedId,
    ) -> list[Decision]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.decisions
                WHERE record_owner_organization_id = :org_id
                  AND subject_id = :subject_id
                ORDER BY issued_at DESC
                """
            ),
            {"org_id": organization_id.value, "subject_id": subject_id.value},
        ).fetchall()

        return [self._map_row_to_decision(row) for row in rows]

    def _map_row_to_decision(self, row: object) -> Decision:
        issued_at = (
            row.issued_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
            if row.issued_at.tzinfo is None  # type: ignore[attr-defined]
            else row.issued_at  # type: ignore[attr-defined]
        )

        def _loaded(value: Any) -> Any:
            return json.loads(value) if isinstance(value, str) else value

        raw_reasons = _loaded(row.reasons)  # type: ignore[attr-defined]
        raw_affected = _loaded(row.affected_subjects)  # type: ignore[attr-defined]
        raw_evidence = _loaded(row.evidence_references)  # type: ignore[attr-defined]
        raw_actions = _loaded(row.corrective_actions)  # type: ignore[attr-defined]

        return Decision(
            decision_id=TypedId(entity_type="decision", value=row.decision_id),  # type: ignore[attr-defined]
            organization_id=OrganizationId(row.record_owner_organization_id),  # type: ignore[attr-defined]
            subject_id=TypedId(
                entity_type=row.subject_entity_type,  # type: ignore[attr-defined]
                value=row.subject_id,  # type: ignore[attr-defined]
            ),
            purpose=row.purpose,  # type: ignore[attr-defined]
            evaluation_id=TypedId(entity_type="evaluation", value=row.evaluation_id),  # type: ignore[attr-defined]
            evaluation_hash=row.evaluation_hash,  # type: ignore[attr-defined]
            policy_id=TypedId(entity_type="policy", value=row.policy_id),  # type: ignore[attr-defined]
            policy_version=row.policy_version,  # type: ignore[attr-defined]
            result=DecisionResult(row.result),  # type: ignore[attr-defined]
            reasons=tuple(DecisionReason.from_dict(item) for item in raw_reasons),
            snapshot_hash=row.snapshot_hash,  # type: ignore[attr-defined]
            issued_at=issued_at,
            engine_version=row.engine_version,  # type: ignore[attr-defined]
            decision_hash=row.decision_hash,  # type: ignore[attr-defined]
            affected_subjects=tuple(
                ref for ref in (reference_from_dict(i) for i in raw_affected) if ref is not None
            ),
            evidence_references=tuple(
                ref for ref in (reference_from_dict(i) for i in raw_evidence) if ref is not None
            ),
            corrective_actions=tuple(raw_actions),
        )
