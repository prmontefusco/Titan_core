"""Registro auditável de Recalls em modo incidente (Passo 7.4)."""

import json
from dataclasses import dataclass
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_domain.recall import RecallResult
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

recalls_table = Table(
    "recalls",
    organization_metadata,
    Column("recall_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("subject_entity_type", String(100), nullable=False),
    Column("subject_id", PG_UUID(as_uuid=True), nullable=False),
    Column("direction", String(30), nullable=False),
    Column("mode", String(30), nullable=False),
    Column("status", String(30), nullable=False),
    Column("executed_at", DateTime(timezone=True), nullable=False),
    Column("visited_nodes", Integer, nullable=False),
    # O resultado completo fica preservado: caminhos, lacunas e decisões afetadas
    # precisam ser reproduzíveis para explicar a análise depois.
    Column("result_document", JSONB, nullable=False),
    CheckConstraint("visited_nodes >= 0", name="ck_recalls_visited_nodes"),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_recalls_organization",
    ),
    Index("ix_recalls_subject", "record_owner_organization_id", "subject_id"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TransactionalRecallRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalRecallRepository exige transacao ativa.")

    def save(self, result: RecallResult) -> None:
        # Recall de incidente é registro histórico: gravação append-only.
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.recalls (
                    recall_id, record_owner_organization_id,
                    subject_entity_type, subject_id,
                    direction, mode, status, executed_at,
                    visited_nodes, result_document
                ) VALUES (
                    :recall_id, :org_id,
                    :subject_entity_type, :subject_id,
                    :direction, :mode, :status, :executed_at,
                    :visited_nodes, :result_document
                )
                """
            ),
            {
                "recall_id": result.recall_id.value,
                "org_id": result.request.organization_id.value,
                "subject_entity_type": (result.request.subject_reference.target_id.entity_type),
                "subject_id": result.request.subject_reference.target_id.value,
                "direction": result.request.direction.value,
                "mode": result.request.mode.value,
                "status": result.status.value,
                "executed_at": result.executed_at,
                "visited_nodes": result.visited_nodes,
                "result_document": json.dumps(result.to_dict()),
            },
        )

    def get_by_id(self, recall_id: TypedId) -> RecallResult | None:
        row = self.connection.execute(
            text(
                """
                SELECT result_document
                FROM core_audit.recalls
                WHERE recall_id = :recall_id
                """
            ),
            {"recall_id": recall_id.value},
        ).first()
        if row is None:
            return None
        return RecallResult.from_dict(self._loaded(row.result_document))

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[RecallResult]:
        rows = self.connection.execute(
            text(
                """
                SELECT result_document
                FROM core_audit.recalls
                WHERE record_owner_organization_id = :org_id
                  AND subject_id = :subject_id
                ORDER BY executed_at DESC
                """
            ),
            {"org_id": organization_id.value, "subject_id": subject_id.value},
        ).fetchall()
        return [RecallResult.from_dict(self._loaded(r.result_document)) for r in rows]

    @staticmethod
    def _loaded(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value


@dataclass(frozen=True, slots=True)
class PostgresAffectedDecisionLookup:
    """Localiza decisões emitidas sobre um sujeito, sob RLS."""

    connection: Connection

    def list_decision_ids_for_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[TypedId]:
        rows = self.connection.execute(
            text(
                """
                SELECT decision_id
                FROM core_audit.decisions
                WHERE record_owner_organization_id = :org_id
                  AND subject_id = :subject_id
                ORDER BY issued_at DESC
                """
            ),
            {"org_id": organization_id.value, "subject_id": subject_id.value},
        ).fetchall()
        return [TypedId(entity_type="decision", value=row.decision_id) for row in rows]


__all__ = [
    "PostgresAffectedDecisionLookup",
    "TransactionalRecallRepository",
    "recalls_table",
]
