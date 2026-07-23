"""Repositório PostgreSQL com RLS para Dossiers (Passo 7.5)."""

import json
from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
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

from packages.core_domain.dossier import Dossier
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

dossiers_table = Table(
    "dossiers",
    organization_metadata,
    Column("dossier_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("subject_entity_type", String(100), nullable=False),
    Column("subject_id", PG_UUID(as_uuid=True), nullable=False),
    Column("subject_contract_version", Integer, nullable=False),
    Column("purpose", String(255), nullable=False),
    Column("decision_id", PG_UUID(as_uuid=True), nullable=False),
    Column("evaluation_id", PG_UUID(as_uuid=True), nullable=False),
    Column("generated_at", DateTime(timezone=True), nullable=False),
    Column("serialization_version", String(50), nullable=False),
    Column("document_version", Integer, nullable=False),
    Column("dossier_hash", String(64), nullable=False),
    Column("document", JSONB, nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_dossiers_organization",
    ),
    ForeignKeyConstraint(
        ["decision_id"], ["core_audit.decisions.decision_id"], name="fk_dossiers_decision"
    ),
    Index("ix_dossiers_subject", "record_owner_organization_id", "subject_id"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

_SELECT_COLUMNS = """
    dossier_id,
    record_owner_organization_id,
    subject_entity_type,
    subject_id,
    subject_contract_version,
    purpose,
    decision_id,
    evaluation_id,
    generated_at,
    serialization_version,
    document_version,
    dossier_hash,
    document
"""


@dataclass(frozen=True, slots=True)
class TransactionalDossierRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalDossierRepository exige transacao ativa.")

    def save(self, dossier: Dossier) -> None:
        # Dossiê é snapshot imutável: gravação append-only.
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.dossiers (
                    dossier_id, record_owner_organization_id,
                    subject_entity_type, subject_id, subject_contract_version,
                    purpose, decision_id, evaluation_id, generated_at,
                    serialization_version, document_version, dossier_hash, document
                ) VALUES (
                    :dossier_id, :org_id,
                    :subject_entity_type, :subject_id, :subject_contract_version,
                    :purpose, :decision_id, :evaluation_id, :generated_at,
                    :serialization_version, :document_version, :dossier_hash, :document
                )
                """
            ),
            {
                "dossier_id": dossier.dossier_id.value,
                "org_id": dossier.organization_id.value,
                "subject_entity_type": dossier.subject_reference.target_id.entity_type,
                "subject_id": dossier.subject_reference.target_id.value,
                "subject_contract_version": dossier.subject_reference.contract_version,
                "purpose": dossier.purpose,
                "decision_id": dossier.decision_id.value,
                "evaluation_id": dossier.evaluation_id.value,
                "generated_at": dossier.generated_at,
                "serialization_version": dossier.serialization_version,
                "document_version": dossier.document_version,
                "dossier_hash": dossier.dossier_hash,
                "document": json.dumps(dossier.document),
            },
        )

    def get_by_id(self, dossier_id: TypedId) -> Dossier | None:
        row = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.dossiers
                WHERE dossier_id = :dossier_id
                """
            ),
            {"dossier_id": dossier_id.value},
        ).first()
        if row is None:
            return None
        return self._map_row(row)

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[Dossier]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.dossiers
                WHERE record_owner_organization_id = :org_id
                  AND subject_id = :subject_id
                ORDER BY generated_at DESC
                """
            ),
            {"org_id": organization_id.value, "subject_id": subject_id.value},
        ).fetchall()
        return [self._map_row(row) for row in rows]

    def _map_row(self, row: object) -> Dossier:
        organization_id = OrganizationId(row.record_owner_organization_id)  # type: ignore[attr-defined]
        generated_at = row.generated_at  # type: ignore[attr-defined]
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=UTC)

        raw_document: Any = row.document  # type: ignore[attr-defined]
        if isinstance(raw_document, str):
            raw_document = json.loads(raw_document)

        return Dossier(
            dossier_id=TypedId(entity_type="dossier", value=row.dossier_id),  # type: ignore[attr-defined]
            organization_id=organization_id,
            subject_reference=UniversalReference(
                target_id=TypedId(
                    entity_type=row.subject_entity_type,  # type: ignore[attr-defined]
                    value=row.subject_id,  # type: ignore[attr-defined]
                ),
                organization_id=organization_id,
                contract_version=row.subject_contract_version,  # type: ignore[attr-defined]
            ),
            purpose=row.purpose,  # type: ignore[attr-defined]
            decision_id=TypedId(entity_type="decision", value=row.decision_id),  # type: ignore[attr-defined]
            evaluation_id=TypedId(entity_type="evaluation", value=row.evaluation_id),  # type: ignore[attr-defined]
            generated_at=generated_at,
            document=dict(raw_document),
            dossier_hash=row.dossier_hash,  # type: ignore[attr-defined]
            serialization_version=row.serialization_version,  # type: ignore[attr-defined]
            document_version=row.document_version,  # type: ignore[attr-defined]
        )
