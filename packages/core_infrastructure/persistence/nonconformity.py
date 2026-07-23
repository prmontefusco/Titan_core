"""Repositório PostgreSQL com RLS para NonConformity (Passo 7.3)."""

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

from packages.core_domain.evidence import ValidityPeriod
from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_domain.nonconformity import (
    NonConformity,
    NonConformityOrigin,
    NonConformityStatus,
    NonConformityTransition,
)
from packages.core_domain.rule import SeverityLevel
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

nonconformities_table = Table(
    "nonconformities",
    organization_metadata,
    Column("nonconformity_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("subject_entity_type", String(100), nullable=False),
    Column("subject_id", PG_UUID(as_uuid=True), nullable=False),
    Column("subject_contract_version", Integer, nullable=False),
    Column("origin", String(50), nullable=False),
    Column("severity", String(30), nullable=False),
    Column("status", String(40), nullable=False),
    Column("description", Text, nullable=False),
    Column("detected_at", DateTime(timezone=True), nullable=False),
    Column("affected_from", DateTime(timezone=True), nullable=True),
    Column("affected_until", DateTime(timezone=True), nullable=True),
    Column("origin_reference", JSONB, nullable=True),
    Column("responsible_reference", JSONB, nullable=True),
    Column("due_date", DateTime(timezone=True), nullable=True),
    Column("corrective_action", Text, nullable=False, server_default=""),
    Column("correction_evidence_references", JSONB, nullable=False, server_default="[]"),
    Column("reevaluation_id", PG_UUID(as_uuid=True), nullable=True),
    Column("closed_at", DateTime(timezone=True), nullable=True),
    Column("closure_note", Text, nullable=False, server_default=""),
    Column("transitions", JSONB, nullable=False, server_default="[]"),
    # Encerramento nunca remove histórico: encerrada exige instante e trilha.
    CheckConstraint(
        "status <> 'encerrada' OR closed_at IS NOT NULL",
        name="ck_nonconformities_closed_at",
    ),
    CheckConstraint("jsonb_array_length(transitions) > 0", name="ck_nonconformities_has_history"),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_nonconformities_organization",
    ),
    Index("ix_nonconformities_subject", "record_owner_organization_id", "subject_id"),
    Index("ix_nonconformities_status", "record_owner_organization_id", "status"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

_SELECT_COLUMNS = """
    nonconformity_id,
    record_owner_organization_id,
    subject_entity_type,
    subject_id,
    subject_contract_version,
    origin,
    severity,
    status,
    description,
    detected_at,
    affected_from,
    affected_until,
    origin_reference,
    responsible_reference,
    due_date,
    corrective_action,
    correction_evidence_references,
    reevaluation_id,
    closed_at,
    closure_note,
    transitions
"""


@dataclass(frozen=True, slots=True)
class TransactionalNonConformityRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalNonConformityRepository exige transacao ativa.")

    def save(self, nonconformity: NonConformity) -> None:
        # O estado avança e o histórico só cresce: nenhuma coluna de trilha é
        # sobrescrita por conteúdo menor do que o já gravado.
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.nonconformities (
                    nonconformity_id, record_owner_organization_id,
                    subject_entity_type, subject_id, subject_contract_version,
                    origin, severity, status, description, detected_at,
                    affected_from, affected_until, origin_reference,
                    responsible_reference, due_date, corrective_action,
                    correction_evidence_references, reevaluation_id,
                    closed_at, closure_note, transitions
                ) VALUES (
                    :nonconformity_id, :org_id,
                    :subject_entity_type, :subject_id, :subject_contract_version,
                    :origin, :severity, :status, :description, :detected_at,
                    :affected_from, :affected_until, :origin_reference,
                    :responsible_reference, :due_date, :corrective_action,
                    :correction_evidence_references, :reevaluation_id,
                    :closed_at, :closure_note, :transitions
                )
                ON CONFLICT (nonconformity_id) DO UPDATE SET
                    severity = EXCLUDED.severity,
                    status = EXCLUDED.status,
                    affected_from = EXCLUDED.affected_from,
                    affected_until = EXCLUDED.affected_until,
                    responsible_reference = EXCLUDED.responsible_reference,
                    due_date = EXCLUDED.due_date,
                    corrective_action = EXCLUDED.corrective_action,
                    correction_evidence_references =
                        EXCLUDED.correction_evidence_references,
                    reevaluation_id = EXCLUDED.reevaluation_id,
                    closed_at = EXCLUDED.closed_at,
                    closure_note = EXCLUDED.closure_note,
                    transitions = EXCLUDED.transitions
                """
            ),
            {
                "nonconformity_id": nonconformity.nonconformity_id.value,
                "org_id": nonconformity.organization_id.value,
                "subject_entity_type": nonconformity.subject_reference.target_id.entity_type,
                "subject_id": nonconformity.subject_reference.target_id.value,
                "subject_contract_version": nonconformity.subject_reference.contract_version,
                "origin": nonconformity.origin.value,
                "severity": nonconformity.severity.value,
                "status": nonconformity.status.value,
                "description": nonconformity.description,
                "detected_at": nonconformity.detected_at,
                "affected_from": nonconformity.affected_period.valid_from,
                "affected_until": nonconformity.affected_period.valid_until,
                "origin_reference": json.dumps(reference_to_dict(nonconformity.origin_reference)),
                "responsible_reference": json.dumps(
                    reference_to_dict(nonconformity.responsible_reference)
                ),
                "due_date": nonconformity.due_date,
                "corrective_action": nonconformity.corrective_action,
                "correction_evidence_references": json.dumps(
                    [reference_to_dict(r) for r in nonconformity.correction_evidence_references]
                ),
                "reevaluation_id": (
                    nonconformity.reevaluation_id.value if nonconformity.reevaluation_id else None
                ),
                "closed_at": nonconformity.closed_at,
                "closure_note": nonconformity.closure_note,
                "transitions": json.dumps([t.to_dict() for t in nonconformity.transitions]),
            },
        )

    def get_by_id(self, nonconformity_id: TypedId) -> NonConformity | None:
        row = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.nonconformities
                WHERE nonconformity_id = :nonconformity_id
                """
            ),
            {"nonconformity_id": nonconformity_id.value},
        ).first()
        if row is None:
            return None
        return self._map_row(row)

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[NonConformity]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.nonconformities
                WHERE record_owner_organization_id = :org_id
                  AND subject_id = :subject_id
                ORDER BY detected_at DESC, nonconformity_id ASC
                """
            ),
            {"org_id": organization_id.value, "subject_id": subject_id.value},
        ).fetchall()
        return [self._map_row(row) for row in rows]

    def list_open(self, organization_id: OrganizationId) -> list[NonConformity]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.nonconformities
                WHERE record_owner_organization_id = :org_id
                  AND status <> 'encerrada'
                ORDER BY detected_at ASC, nonconformity_id ASC
                """
            ),
            {"org_id": organization_id.value},
        ).fetchall()
        return [self._map_row(row) for row in rows]

    def _map_row(self, row: object) -> NonConformity:
        def _aware(value: datetime | None) -> datetime | None:
            if value is None:
                return None
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        def _loaded(value: Any) -> Any:
            return json.loads(value) if isinstance(value, str) else value

        organization_id = OrganizationId(row.record_owner_organization_id)  # type: ignore[attr-defined]
        detected_at = _aware(row.detected_at)  # type: ignore[attr-defined]
        assert detected_at is not None

        subject = reference_from_dict(
            {
                "entity_type": row.subject_entity_type,  # type: ignore[attr-defined]
                "value": str(row.subject_id),  # type: ignore[attr-defined]
                "organization_id": str(organization_id.value),
                "contract_version": row.subject_contract_version,  # type: ignore[attr-defined]
            }
        )
        assert subject is not None

        raw_reevaluation = row.reevaluation_id  # type: ignore[attr-defined]

        return NonConformity(
            nonconformity_id=TypedId(
                entity_type="nonconformity",
                value=row.nonconformity_id,  # type: ignore[attr-defined]
            ),
            organization_id=organization_id,
            subject_reference=subject,
            origin=NonConformityOrigin(row.origin),  # type: ignore[attr-defined]
            severity=SeverityLevel(row.severity),  # type: ignore[attr-defined]
            description=row.description,  # type: ignore[attr-defined]
            detected_at=detected_at,
            status=NonConformityStatus(row.status),  # type: ignore[attr-defined]
            affected_period=ValidityPeriod(
                valid_from=_aware(row.affected_from),  # type: ignore[attr-defined]
                valid_until=_aware(row.affected_until),  # type: ignore[attr-defined]
            ),
            origin_reference=reference_from_dict(_loaded(row.origin_reference)),  # type: ignore[attr-defined]
            responsible_reference=reference_from_dict(
                _loaded(row.responsible_reference)  # type: ignore[attr-defined]
            ),
            due_date=_aware(row.due_date),  # type: ignore[attr-defined]
            corrective_action=row.corrective_action,  # type: ignore[attr-defined]
            correction_evidence_references=tuple(
                ref
                for ref in (
                    reference_from_dict(i)
                    for i in _loaded(row.correction_evidence_references)  # type: ignore[attr-defined]
                )
                if ref is not None
            ),
            reevaluation_id=(
                TypedId(entity_type="evaluation", value=raw_reevaluation)
                if raw_reevaluation is not None
                else None
            ),
            closed_at=_aware(row.closed_at),  # type: ignore[attr-defined]
            closure_note=row.closure_note,  # type: ignore[attr-defined]
            transitions=tuple(
                NonConformityTransition.from_dict(t)
                for t in _loaded(row.transitions)  # type: ignore[attr-defined]
            ),
        )
