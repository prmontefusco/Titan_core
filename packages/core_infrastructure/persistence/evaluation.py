"""Repositório PostgreSQL com RLS para Evaluations preservadas (ADR-0036/Passo 6.5)."""

import json
from dataclasses import dataclass
from datetime import UTC

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

from packages.core_domain.evaluation import Evaluation, EvaluationOutcome, RuleResult
from packages.core_domain.facts import FactSnapshot, reference_from_dict, reference_to_dict
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

evaluations_table = Table(
    "evaluations",
    organization_metadata,
    Column("evaluation_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("policy_id", PG_UUID(as_uuid=True), nullable=False),
    Column("policy_version", Integer, nullable=False),
    Column("subject_entity_type", String(100), nullable=False),
    Column("subject_id", PG_UUID(as_uuid=True), nullable=False),
    Column("purpose", String(255), nullable=False),
    Column("outcome", String(50), nullable=False),
    Column("engine_version", Integer, nullable=False),
    Column("evaluated_at", DateTime(timezone=True), nullable=False),
    Column("snapshot_hash", String(64), nullable=False),
    Column("evaluation_hash", String(64), nullable=False),
    Column("fact_snapshot", JSONB, nullable=False),
    Column("rule_results", JSONB, nullable=False),
    Column("rule_versions", JSONB, nullable=False, server_default="[]"),
    Column("executor_reference", JSONB, nullable=True),
    CheckConstraint("policy_version >= 1", name="ck_evaluations_policy_version"),
    CheckConstraint("engine_version >= 1", name="ck_evaluations_engine_version"),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_evaluations_organization",
    ),
    ForeignKeyConstraint(
        ["policy_id"],
        ["core_audit.policies.policy_id"],
        name="fk_evaluations_policy",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TransactionalEvaluationRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalEvaluationRepository exige transacao ativa.")

    def save(self, evaluation: Evaluation) -> None:
        # Evaluation histórica nunca é alterada: gravação é estritamente append-only.
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.evaluations (
                    evaluation_id,
                    record_owner_organization_id,
                    policy_id,
                    policy_version,
                    subject_entity_type,
                    subject_id,
                    purpose,
                    outcome,
                    engine_version,
                    evaluated_at,
                    snapshot_hash,
                    evaluation_hash,
                    fact_snapshot,
                    rule_results,
                    rule_versions,
                    executor_reference
                ) VALUES (
                    :evaluation_id,
                    :org_id,
                    :policy_id,
                    :policy_version,
                    :subject_entity_type,
                    :subject_id,
                    :purpose,
                    :outcome,
                    :engine_version,
                    :evaluated_at,
                    :snapshot_hash,
                    :evaluation_hash,
                    :fact_snapshot,
                    :rule_results,
                    :rule_versions,
                    :executor_reference
                )
                """
            ),
            {
                "evaluation_id": evaluation.evaluation_id.value,
                "org_id": evaluation.organization_id.value,
                "policy_id": evaluation.policy_id.value,
                "policy_version": evaluation.policy_version,
                "subject_entity_type": evaluation.subject_id.entity_type,
                "subject_id": evaluation.subject_id.value,
                "purpose": evaluation.purpose,
                "outcome": evaluation.outcome.value,
                "engine_version": evaluation.engine_version,
                "evaluated_at": evaluation.evaluated_at,
                "snapshot_hash": evaluation.fact_snapshot.snapshot_hash,
                "evaluation_hash": evaluation.evaluation_hash,
                "fact_snapshot": json.dumps(evaluation.fact_snapshot.to_dict()),
                "rule_results": json.dumps([r.to_dict() for r in evaluation.rule_results]),
                "rule_versions": json.dumps(
                    [
                        {"code": code, "version": version}
                        for code, version in evaluation.rule_versions
                    ]
                ),
                "executor_reference": json.dumps(reference_to_dict(evaluation.executor_reference)),
            },
        )

    def get_by_id(self, evaluation_id: TypedId) -> Evaluation | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    evaluation_id,
                    record_owner_organization_id,
                    policy_id,
                    policy_version,
                    subject_entity_type,
                    subject_id,
                    purpose,
                    outcome,
                    engine_version,
                    evaluated_at,
                    evaluation_hash,
                    fact_snapshot,
                    rule_results,
                    rule_versions,
                    executor_reference
                FROM core_audit.evaluations
                WHERE evaluation_id = :evaluation_id
                """
            ),
            {"evaluation_id": evaluation_id.value},
        ).first()

        if row is None:
            return None
        return self._map_row_to_evaluation(row)

    def list_by_subject(
        self,
        organization_id: OrganizationId,
        subject_id: TypedId,
    ) -> list[Evaluation]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    evaluation_id,
                    record_owner_organization_id,
                    policy_id,
                    policy_version,
                    subject_entity_type,
                    subject_id,
                    purpose,
                    outcome,
                    engine_version,
                    evaluated_at,
                    evaluation_hash,
                    fact_snapshot,
                    rule_results,
                    rule_versions,
                    executor_reference
                FROM core_audit.evaluations
                WHERE record_owner_organization_id = :org_id
                  AND subject_id = :subject_id
                ORDER BY evaluated_at DESC
                """
            ),
            {"org_id": organization_id.value, "subject_id": subject_id.value},
        ).fetchall()

        return [self._map_row_to_evaluation(row) for row in rows]

    def _map_row_to_evaluation(self, row: object) -> Evaluation:
        evaluated_at = (
            row.evaluated_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
            if row.evaluated_at.tzinfo is None  # type: ignore[attr-defined]
            else row.evaluated_at  # type: ignore[attr-defined]
        )

        raw_snapshot = row.fact_snapshot  # type: ignore[attr-defined]
        if isinstance(raw_snapshot, str):
            raw_snapshot = json.loads(raw_snapshot)

        raw_results = row.rule_results  # type: ignore[attr-defined]
        if isinstance(raw_results, str):
            raw_results = json.loads(raw_results)

        raw_versions = row.rule_versions  # type: ignore[attr-defined]
        if isinstance(raw_versions, str):
            raw_versions = json.loads(raw_versions)

        raw_executor = row.executor_reference  # type: ignore[attr-defined]
        if isinstance(raw_executor, str):
            raw_executor = json.loads(raw_executor)

        return Evaluation(
            evaluation_id=TypedId(entity_type="evaluation", value=row.evaluation_id),  # type: ignore[attr-defined]
            organization_id=OrganizationId(row.record_owner_organization_id),  # type: ignore[attr-defined]
            subject_id=TypedId(
                entity_type=row.subject_entity_type,  # type: ignore[attr-defined]
                value=row.subject_id,  # type: ignore[attr-defined]
            ),
            purpose=row.purpose,  # type: ignore[attr-defined]
            policy_id=TypedId(entity_type="policy", value=row.policy_id),  # type: ignore[attr-defined]
            policy_version=row.policy_version,  # type: ignore[attr-defined]
            fact_snapshot=FactSnapshot.from_dict(raw_snapshot),
            rule_results=tuple(RuleResult.from_dict(item) for item in raw_results),
            outcome=EvaluationOutcome(row.outcome),  # type: ignore[attr-defined]
            evaluated_at=evaluated_at,
            engine_version=row.engine_version,  # type: ignore[attr-defined]
            evaluation_hash=row.evaluation_hash,  # type: ignore[attr-defined]
            executor_reference=reference_from_dict(raw_executor),
            rule_versions=tuple((item["code"], item["version"]) for item in raw_versions),
        )
