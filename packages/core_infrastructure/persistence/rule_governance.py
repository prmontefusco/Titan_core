"""Repositorios PostgreSQL para governanca de regras (ADR-0043)."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_domain.rule_governance import (
    RuleIdentity,
    RuleSourceType,
    RuleTimelineEvent,
    RuleTimelineEventType,
)
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

rule_identities_table = Table(
    "rule_identities",
    organization_metadata,
    Column("rule_identity_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("code", String(100), nullable=False),
    Column("purpose", String(120), nullable=False),
    Column("scope", String(160), nullable=False),
    Column("source_type", String(40), nullable=False),
    Column("created_by_target_type", String(100), nullable=False),
    Column("created_by_target_id", PG_UUID(as_uuid=True), nullable=False),
    Column("created_by_organization_id", PG_UUID(as_uuid=True), nullable=True),
    Column("created_by_contract_version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("vertical", String(80), nullable=False, server_default=""),
    Column("description", Text, nullable=False, server_default=""),
    UniqueConstraint(
        "record_owner_organization_id",
        "code",
        name="uq_rule_identities_organization_code",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_rule_identities_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

rule_timeline_events_table = Table(
    "rule_timeline_events",
    organization_metadata,
    Column("event_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("rule_identity_id", PG_UUID(as_uuid=True), nullable=False),
    Column("event_type", String(80), nullable=False),
    Column("actor_target_type", String(100), nullable=False),
    Column("actor_target_id", PG_UUID(as_uuid=True), nullable=False),
    Column("actor_organization_id", PG_UUID(as_uuid=True), nullable=True),
    Column("actor_contract_version", Integer, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("rule_version_id", PG_UUID(as_uuid=True), nullable=True),
    Column("reason", Text, nullable=False, server_default=""),
    Column("evidence_references", JSONB, nullable=False, server_default="[]"),
    Column("correlation_id", PG_UUID(as_uuid=True), nullable=True),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_rule_timeline_organization",
    ),
    ForeignKeyConstraint(
        ["rule_identity_id"],
        ["core_audit.rule_identities.rule_identity_id"],
        name="fk_rule_timeline_identity",
    ),
    ForeignKeyConstraint(
        ["rule_version_id"],
        ["core_audit.rules.rule_id"],
        name="fk_rule_timeline_rule_version",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TransactionalRuleIdentityRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalRuleIdentityRepository exige transacao ativa.")

    def save(self, identity: RuleIdentity) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.rule_identities (
                    rule_identity_id,
                    record_owner_organization_id,
                    code,
                    purpose,
                    scope,
                    source_type,
                    created_by_target_type,
                    created_by_target_id,
                    created_by_organization_id,
                    created_by_contract_version,
                    created_at,
                    vertical,
                    description
                ) VALUES (
                    :rule_identity_id,
                    :org_id,
                    :code,
                    :purpose,
                    :scope,
                    :source_type,
                    :created_by_target_type,
                    :created_by_target_id,
                    :created_by_organization_id,
                    :created_by_contract_version,
                    :created_at,
                    :vertical,
                    :description
                )
                ON CONFLICT (rule_identity_id) DO NOTHING
                """
            ),
            {
                "rule_identity_id": identity.rule_identity_id.value,
                "org_id": identity.organization_id.value,
                "code": identity.code,
                "purpose": identity.purpose,
                "scope": identity.scope,
                "source_type": identity.source_type.value,
                "created_by_target_type": identity.created_by.target_id.entity_type,
                "created_by_target_id": identity.created_by.target_id.value,
                "created_by_organization_id": (
                    identity.created_by.organization_id.value
                    if identity.created_by.organization_id is not None
                    else None
                ),
                "created_by_contract_version": identity.created_by.contract_version,
                "created_at": identity.created_at,
                "vertical": identity.vertical,
                "description": identity.description,
            },
        )

    def get_by_organization_and_code(
        self, organization_id: OrganizationId, code: str
    ) -> RuleIdentity | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    rule_identity_id,
                    record_owner_organization_id,
                    code,
                    purpose,
                    scope,
                    source_type,
                    created_by_target_type,
                    created_by_target_id,
                    created_by_organization_id,
                    created_by_contract_version,
                    created_at,
                    vertical,
                    description
                FROM core_audit.rule_identities
                WHERE record_owner_organization_id = :org_id
                  AND code = :code
                """
            ),
            {"org_id": organization_id.value, "code": code.strip().lower()},
        ).first()
        if row is None:
            return None
        return _map_identity(row)


@dataclass(frozen=True, slots=True)
class TransactionalRuleTimelineRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalRuleTimelineRepository exige transacao ativa.")

    def append(self, event: RuleTimelineEvent) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.rule_timeline_events (
                    event_id,
                    record_owner_organization_id,
                    rule_identity_id,
                    event_type,
                    actor_target_type,
                    actor_target_id,
                    actor_organization_id,
                    actor_contract_version,
                    occurred_at,
                    rule_version_id,
                    reason,
                    evidence_references,
                    correlation_id
                ) VALUES (
                    :event_id,
                    :org_id,
                    :rule_identity_id,
                    :event_type,
                    :actor_target_type,
                    :actor_target_id,
                    :actor_organization_id,
                    :actor_contract_version,
                    :occurred_at,
                    :rule_version_id,
                    :reason,
                    :evidence_references,
                    :correlation_id
                )
                """
            ),
            {
                "event_id": event.event_id.value,
                "org_id": event.organization_id.value,
                "rule_identity_id": event.rule_identity_id.value,
                "event_type": event.event_type.value,
                "actor_target_type": event.actor.target_id.entity_type,
                "actor_target_id": event.actor.target_id.value,
                "actor_organization_id": (
                    event.actor.organization_id.value
                    if event.actor.organization_id is not None
                    else None
                ),
                "actor_contract_version": event.actor.contract_version,
                "occurred_at": event.occurred_at,
                "rule_version_id": (
                    event.rule_version_id.value if event.rule_version_id is not None else None
                ),
                "reason": event.reason,
                "evidence_references": json.dumps(
                    [_reference_to_dict(ref) for ref in event.evidence_references]
                ),
                "correlation_id": event.correlation_id.value if event.correlation_id else None,
            },
        )

    def list_by_identity(
        self, organization_id: OrganizationId, rule_identity_id: TypedId
    ) -> list[RuleTimelineEvent]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    event_id,
                    record_owner_organization_id,
                    rule_identity_id,
                    event_type,
                    actor_target_type,
                    actor_target_id,
                    actor_organization_id,
                    actor_contract_version,
                    occurred_at,
                    rule_version_id,
                    reason,
                    evidence_references,
                    correlation_id
                FROM core_audit.rule_timeline_events
                WHERE record_owner_organization_id = :org_id
                  AND rule_identity_id = :rule_identity_id
                ORDER BY occurred_at ASC, event_id ASC
                """
            ),
            {"org_id": organization_id.value, "rule_identity_id": rule_identity_id.value},
        ).fetchall()
        return [_map_timeline_event(row) for row in rows]


def _normalize_required_datetime(value: Any) -> datetime:
    parsed = cast(datetime, value)
    if parsed.tzinfo is not None:
        return parsed
    return parsed.replace(tzinfo=UTC)


def _reference_to_dict(reference: UniversalReference) -> dict[str, object]:
    return {
        "target_type": reference.target_id.entity_type,
        "target_id": str(reference.target_id.value),
        "organization_id": str(reference.organization_id.value)
        if reference.organization_id is not None
        else None,
        "contract_version": reference.contract_version,
    }


def _map_reference(
    target_type: str, target_id: Any, organization_id: Any, contract_version: int
) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId(entity_type=target_type, value=target_id),
        organization_id=OrganizationId(organization_id) if organization_id is not None else None,
        contract_version=contract_version,
    )


def _map_identity(row: object) -> RuleIdentity:
    return RuleIdentity(
        rule_identity_id=TypedId(entity_type="rule_identity", value=row.rule_identity_id),  # type: ignore[attr-defined]
        organization_id=OrganizationId(row.record_owner_organization_id),  # type: ignore[attr-defined]
        code=row.code,  # type: ignore[attr-defined]
        purpose=row.purpose,  # type: ignore[attr-defined]
        scope=row.scope,  # type: ignore[attr-defined]
        source_type=RuleSourceType(row.source_type),  # type: ignore[attr-defined]
        created_by=_map_reference(
            row.created_by_target_type,  # type: ignore[attr-defined]
            row.created_by_target_id,  # type: ignore[attr-defined]
            row.created_by_organization_id,  # type: ignore[attr-defined]
            row.created_by_contract_version,  # type: ignore[attr-defined]
        ),
        created_at=_normalize_required_datetime(row.created_at),  # type: ignore[attr-defined]
        vertical=row.vertical,  # type: ignore[attr-defined]
        description=row.description,  # type: ignore[attr-defined]
    )


def _map_timeline_event(row: object) -> RuleTimelineEvent:
    raw_evidence = row.evidence_references  # type: ignore[attr-defined]
    if isinstance(raw_evidence, str):
        raw_evidence = json.loads(raw_evidence)
    evidence_refs: tuple[UniversalReference, ...] = ()
    if isinstance(raw_evidence, list):
        evidence_refs = tuple(
            _map_reference(
                item["target_type"],
                item["target_id"],
                item.get("organization_id"),
                item["contract_version"],
            )
            for item in raw_evidence
        )
    return RuleTimelineEvent(
        event_id=TypedId(entity_type="rule_timeline_event", value=row.event_id),  # type: ignore[attr-defined]
        organization_id=OrganizationId(row.record_owner_organization_id),  # type: ignore[attr-defined]
        rule_identity_id=TypedId(entity_type="rule_identity", value=row.rule_identity_id),  # type: ignore[attr-defined]
        event_type=RuleTimelineEventType(row.event_type),  # type: ignore[attr-defined]
        actor=_map_reference(
            row.actor_target_type,  # type: ignore[attr-defined]
            row.actor_target_id,  # type: ignore[attr-defined]
            row.actor_organization_id,  # type: ignore[attr-defined]
            row.actor_contract_version,  # type: ignore[attr-defined]
        ),
        occurred_at=_normalize_required_datetime(row.occurred_at),  # type: ignore[attr-defined]
        rule_version_id=(
            TypedId(entity_type="rule", value=row.rule_version_id)  # type: ignore[attr-defined]
            if row.rule_version_id is not None  # type: ignore[attr-defined]
            else None
        ),
        reason=row.reason,  # type: ignore[attr-defined]
        evidence_references=evidence_refs,
        correlation_id=(
            TypedId(entity_type="correlation", value=row.correlation_id)  # type: ignore[attr-defined]
            if row.correlation_id is not None  # type: ignore[attr-defined]
            else None
        ),
    )
