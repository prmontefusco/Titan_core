"""Repositório PostgreSQL com RLS para Relações Universais e Temporais (Passo 7.1)."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier, ValidityPeriod
from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_domain.relations import UniversalRelation
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

relations_table = Table(
    "relations",
    organization_metadata,
    Column("relation_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("source_entity_type", String(100), nullable=False),
    Column("source_id", PG_UUID(as_uuid=True), nullable=False),
    Column("source_contract_version", Integer, nullable=False),
    Column("target_entity_type", String(100), nullable=False),
    Column("target_id", PG_UUID(as_uuid=True), nullable=False),
    Column("target_contract_version", Integer, nullable=False),
    Column("relation_type", String(100), nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=True),
    Column("valid_until", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("confidence_tier", String(30), nullable=False),
    Column("confidence_reason", String(255), nullable=False),
    Column("created_by_event", PG_UUID(as_uuid=True), nullable=True),
    Column("evidence_references", JSONB, nullable=False, server_default="[]"),
    Column("quantity", Numeric, nullable=True),
    Column("unit", String(50), nullable=False, server_default=""),
    Column("relation_metadata", JSONB, nullable=False, server_default="{}"),
    Column("metadata_version", Integer, nullable=False, server_default="1"),
    CheckConstraint("metadata_version >= 1", name="ck_relations_metadata_version"),
    CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_relations_quantity"),
    CheckConstraint(
        "valid_from IS NULL OR valid_until IS NULL OR valid_until >= valid_from",
        name="ck_relations_period",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_relations_organization",
    ),
    Index("ix_relations_source", "record_owner_organization_id", "source_id"),
    Index("ix_relations_target", "record_owner_organization_id", "target_id"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

_SELECT_COLUMNS = """
    relation_id,
    record_owner_organization_id,
    source_entity_type,
    source_id,
    source_contract_version,
    target_entity_type,
    target_id,
    target_contract_version,
    relation_type,
    valid_from,
    valid_until,
    created_at,
    confidence_tier,
    confidence_reason,
    created_by_event,
    evidence_references,
    quantity,
    unit,
    relation_metadata,
    metadata_version
"""

# Relação sem início declarado vale desde sempre; sem fim, vale até hoje.
# O cast é obrigatório: sem ele o PostgreSQL não infere o tipo do parâmetro nulo
# usado para pedir o histórico completo.
_TEMPORAL_FILTER = """
    AND (CAST(:at_time AS timestamptz) IS NULL OR (
        (valid_from IS NULL OR valid_from <= CAST(:at_time AS timestamptz))
        AND (valid_until IS NULL OR valid_until >= CAST(:at_time AS timestamptz))
    ))
"""


@dataclass(frozen=True, slots=True)
class TransactionalRelationRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalRelationRepository exige transacao ativa.")

    def save(self, relation: UniversalRelation) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.relations (
                    relation_id,
                    record_owner_organization_id,
                    source_entity_type,
                    source_id,
                    source_contract_version,
                    target_entity_type,
                    target_id,
                    target_contract_version,
                    relation_type,
                    valid_from,
                    valid_until,
                    created_at,
                    confidence_tier,
                    confidence_reason,
                    created_by_event,
                    evidence_references,
                    quantity,
                    unit,
                    relation_metadata,
                    metadata_version
                ) VALUES (
                    :relation_id,
                    :org_id,
                    :source_entity_type,
                    :source_id,
                    :source_contract_version,
                    :target_entity_type,
                    :target_id,
                    :target_contract_version,
                    :relation_type,
                    :valid_from,
                    :valid_until,
                    :created_at,
                    :confidence_tier,
                    :confidence_reason,
                    :created_by_event,
                    :evidence_references,
                    :quantity,
                    :unit,
                    :relation_metadata,
                    :metadata_version
                )
                ON CONFLICT (relation_id) DO UPDATE SET
                    valid_until = EXCLUDED.valid_until,
                    confidence_tier = EXCLUDED.confidence_tier,
                    confidence_reason = EXCLUDED.confidence_reason,
                    evidence_references = EXCLUDED.evidence_references,
                    relation_metadata = EXCLUDED.relation_metadata,
                    metadata_version = EXCLUDED.metadata_version
                """
            ),
            {
                "relation_id": relation.relation_id.value,
                "org_id": relation.organization_id.value,
                "source_entity_type": relation.source_reference.target_id.entity_type,
                "source_id": relation.source_reference.target_id.value,
                "source_contract_version": relation.source_reference.contract_version,
                "target_entity_type": relation.target_reference.target_id.entity_type,
                "target_id": relation.target_reference.target_id.value,
                "target_contract_version": relation.target_reference.contract_version,
                "relation_type": relation.relation_type,
                "valid_from": relation.period.valid_from,
                "valid_until": relation.period.valid_until,
                "created_at": relation.created_at,
                "confidence_tier": relation.confidence.tier.value,
                "confidence_reason": relation.confidence.reason,
                "created_by_event": (
                    relation.created_by_event.value if relation.created_by_event else None
                ),
                "evidence_references": json.dumps(
                    [reference_to_dict(r) for r in relation.evidence_references]
                ),
                "quantity": relation.quantity,
                "unit": relation.unit,
                "relation_metadata": json.dumps(relation.metadata),
                "metadata_version": relation.metadata_version,
            },
        )

    def get_by_id(self, relation_id: TypedId) -> UniversalRelation | None:
        row = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.relations
                WHERE relation_id = :relation_id
                """
            ),
            {"relation_id": relation_id.value},
        ).first()

        if row is None:
            return None
        return self._map_row_to_relation(row)

    def list_outgoing(
        self,
        organization_id: OrganizationId,
        source_id: TypedId,
        at_time: datetime | None = None,
    ) -> list[UniversalRelation]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.relations
                WHERE record_owner_organization_id = :org_id
                  AND source_id = :source_id
                  {_TEMPORAL_FILTER}
                ORDER BY created_at ASC, relation_id ASC
                """
            ),
            {
                "org_id": organization_id.value,
                "source_id": source_id.value,
                "at_time": at_time,
            },
        ).fetchall()
        return [self._map_row_to_relation(row) for row in rows]

    def list_incoming(
        self,
        organization_id: OrganizationId,
        target_id: TypedId,
        at_time: datetime | None = None,
    ) -> list[UniversalRelation]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.relations
                WHERE record_owner_organization_id = :org_id
                  AND target_id = :target_id
                  {_TEMPORAL_FILTER}
                ORDER BY created_at ASC, relation_id ASC
                """
            ),
            {
                "org_id": organization_id.value,
                "target_id": target_id.value,
                "at_time": at_time,
            },
        ).fetchall()
        return [self._map_row_to_relation(row) for row in rows]

    def _map_row_to_relation(self, row: object) -> UniversalRelation:
        def _aware(value: datetime | None) -> datetime | None:
            if value is None:
                return None
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        def _loaded(value: Any) -> Any:
            return json.loads(value) if isinstance(value, str) else value

        organization_id = OrganizationId(row.record_owner_organization_id)  # type: ignore[attr-defined]
        created_at = _aware(row.created_at)  # type: ignore[attr-defined]
        assert created_at is not None

        raw_event = row.created_by_event  # type: ignore[attr-defined]
        raw_quantity = row.quantity  # type: ignore[attr-defined]

        return UniversalRelation(
            relation_id=TypedId(entity_type="relation", value=row.relation_id),  # type: ignore[attr-defined]
            organization_id=organization_id,
            source_reference=UniversalReference(
                target_id=TypedId(
                    entity_type=row.source_entity_type,  # type: ignore[attr-defined]
                    value=row.source_id,  # type: ignore[attr-defined]
                ),
                organization_id=organization_id,
                contract_version=row.source_contract_version,  # type: ignore[attr-defined]
            ),
            target_reference=UniversalReference(
                target_id=TypedId(
                    entity_type=row.target_entity_type,  # type: ignore[attr-defined]
                    value=row.target_id,  # type: ignore[attr-defined]
                ),
                organization_id=organization_id,
                contract_version=row.target_contract_version,  # type: ignore[attr-defined]
            ),
            relation_type=row.relation_type,  # type: ignore[attr-defined]
            period=ValidityPeriod(
                valid_from=_aware(row.valid_from),  # type: ignore[attr-defined]
                valid_until=_aware(row.valid_until),  # type: ignore[attr-defined]
            ),
            created_at=created_at,
            confidence=ConfidenceLevel(
                tier=ConfidenceTier(row.confidence_tier),  # type: ignore[attr-defined]
                reason=row.confidence_reason,  # type: ignore[attr-defined]
            ),
            created_by_event=(
                TypedId(entity_type="domain_event", value=raw_event)
                if raw_event is not None
                else None
            ),
            evidence_references=tuple(
                ref
                for ref in (
                    reference_from_dict(i)
                    for i in _loaded(row.evidence_references)  # type: ignore[attr-defined]
                )
                if ref is not None
            ),
            quantity=Decimal(raw_quantity) if raw_quantity is not None else None,
            unit=row.unit,  # type: ignore[attr-defined]
            metadata=dict(_loaded(row.relation_metadata)),  # type: ignore[attr-defined]
            metadata_version=row.metadata_version,  # type: ignore[attr-defined]
        )
