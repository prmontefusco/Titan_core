"""Repositório PostgreSQL com RLS para Gestão de Regras Versionadas (ADR-0038/Passo 6.2)."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
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

from packages.core_domain.rule import Rule, RuleCondition, SeverityLevel
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

rules_table = Table(
    "rules",
    organization_metadata,
    Column("rule_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("policy_id", PG_UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("code", String(100), nullable=False),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=False),
    Column("version", Integer, nullable=False),
    Column("severity", String(30), nullable=False),
    Column("normative_source", String(255), nullable=False, server_default=""),
    Column("required_evidence_types", JSONB, nullable=False, server_default="[]"),
    Column("conditions", JSONB, nullable=False, server_default="[]"),
    Column("justification", Text, nullable=False, server_default=""),
    Column("corrective_action", Text, nullable=False, server_default=""),
    Column("valid_from", DateTime(timezone=True), nullable=True),
    Column("valid_to", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "record_owner_organization_id",
        "policy_id",
        "code",
        "version",
        name="uq_rules_policy_code_version",
    ),
    CheckConstraint("version >= 1", name="ck_rules_version"),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_rules_organization",
    ),
    ForeignKeyConstraint(
        ["policy_id"],
        ["core_audit.policies.policy_id"],
        name="fk_rules_policy",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TransactionalRuleRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalRuleRepository exige transacao ativa.")

    def save(self, rule: Rule) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.rules (
                    rule_id,
                    policy_id,
                    record_owner_organization_id,
                    code,
                    name,
                    description,
                    version,
                    severity,
                    normative_source,
                    required_evidence_types,
                    conditions,
                    justification,
                    corrective_action,
                    valid_from,
                    valid_to,
                    created_at
                ) VALUES (
                    :rule_id,
                    :policy_id,
                    :org_id,
                    :code,
                    :name,
                    :description,
                    :version,
                    :severity,
                    :normative_source,
                    :required_evidence_types,
                    :conditions,
                    :justification,
                    :corrective_action,
                    :valid_from,
                    :valid_to,
                    :created_at
                )
                ON CONFLICT (rule_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    severity = EXCLUDED.severity,
                    normative_source = EXCLUDED.normative_source,
                    required_evidence_types = EXCLUDED.required_evidence_types,
                    conditions = EXCLUDED.conditions,
                    justification = EXCLUDED.justification,
                    corrective_action = EXCLUDED.corrective_action,
                    valid_from = EXCLUDED.valid_from,
                    valid_to = EXCLUDED.valid_to
                """
            ),
            {
                "rule_id": rule.rule_id.value,
                "policy_id": rule.policy_id.value,
                "org_id": rule.organization_id.value,
                "code": rule.code,
                "name": rule.name,
                "description": rule.description,
                "version": rule.version,
                "severity": rule.severity.value,
                "normative_source": rule.normative_source,
                "required_evidence_types": json.dumps(list(rule.required_evidence_types)),
                "conditions": json.dumps([c.to_dict() for c in rule.conditions]),
                "justification": rule.justification,
                "corrective_action": rule.corrective_action,
                "valid_from": rule.valid_from,
                "valid_to": rule.valid_to,
                "created_at": rule.created_at,
            },
        )

    def get_by_id(self, rule_id: TypedId) -> Rule | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    rule_id,
                    policy_id,
                    record_owner_organization_id,
                    code,
                    name,
                    description,
                    version,
                    severity,
                    normative_source,
                    required_evidence_types,
                    conditions,
                    justification,
                    corrective_action,
                    valid_from,
                    valid_to,
                    created_at
                FROM core_audit.rules
                WHERE rule_id = :rule_id
                """
            ),
            {"rule_id": rule_id.value},
        ).first()

        if row is None:
            return None

        return self._map_row_to_rule(row)

    def get_by_policy_code_and_version(
        self,
        organization_id: OrganizationId,
        policy_id: TypedId,
        code: str,
        version: int,
    ) -> Rule | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    rule_id,
                    policy_id,
                    record_owner_organization_id,
                    code,
                    name,
                    description,
                    version,
                    severity,
                    normative_source,
                    required_evidence_types,
                    conditions,
                    justification,
                    corrective_action,
                    valid_from,
                    valid_to,
                    created_at
                FROM core_audit.rules
                WHERE record_owner_organization_id = :org_id
                  AND policy_id = :policy_id
                  AND code = :code
                  AND version = :version
                """
            ),
            {
                "org_id": organization_id.value,
                "policy_id": policy_id.value,
                "code": code,
                "version": version,
            },
        ).first()

        if row is None:
            return None

        return self._map_row_to_rule(row)

    def list_active_rules_for_policy_at(
        self,
        organization_id: OrganizationId,
        policy_id: TypedId,
        at_time: datetime,
    ) -> list[Rule]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    rule_id,
                    policy_id,
                    record_owner_organization_id,
                    code,
                    name,
                    description,
                    version,
                    severity,
                    normative_source,
                    required_evidence_types,
                    conditions,
                    justification,
                    corrective_action,
                    valid_from,
                    valid_to,
                    created_at
                FROM core_audit.rules
                WHERE record_owner_organization_id = :org_id
                  AND policy_id = :policy_id
                  AND (valid_from IS NULL OR valid_from <= :at_time)
                  AND (valid_to IS NULL OR valid_to >= :at_time)
                ORDER BY code ASC, version DESC
                """
            ),
            {
                "org_id": organization_id.value,
                "policy_id": policy_id.value,
                "at_time": at_time,
            },
        ).fetchall()

        return [self._map_row_to_rule(row) for row in rows]

    def list_by_policy(
        self,
        organization_id: OrganizationId,
        policy_id: TypedId,
    ) -> list[Rule]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    rule_id,
                    policy_id,
                    record_owner_organization_id,
                    code,
                    name,
                    description,
                    version,
                    severity,
                    normative_source,
                    required_evidence_types,
                    conditions,
                    justification,
                    corrective_action,
                    valid_from,
                    valid_to,
                    created_at
                FROM core_audit.rules
                WHERE record_owner_organization_id = :org_id
                  AND policy_id = :policy_id
                ORDER BY code ASC, version DESC
                """
            ),
            {"org_id": organization_id.value, "policy_id": policy_id.value},
        ).fetchall()

        return [self._map_row_to_rule(row) for row in rows]

    def _map_row_to_rule(self, row: object) -> Rule:
        cr_at = (
            row.created_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
            if row.created_at.tzinfo is None  # type: ignore[attr-defined]
            else row.created_at  # type: ignore[attr-defined]
        )

        vf = None
        if row.valid_from is not None:  # type: ignore[attr-defined]
            vf = (
                row.valid_from.replace(tzinfo=UTC)  # type: ignore[attr-defined]
                if row.valid_from.tzinfo is None  # type: ignore[attr-defined]
                else row.valid_from  # type: ignore[attr-defined]
            )

        vt = None
        if row.valid_to is not None:  # type: ignore[attr-defined]
            vt = (
                row.valid_to.replace(tzinfo=UTC)  # type: ignore[attr-defined]
                if row.valid_to.tzinfo is None  # type: ignore[attr-defined]
                else row.valid_to  # type: ignore[attr-defined]
            )

        raw_ev = row.required_evidence_types  # type: ignore[attr-defined]
        ev_types: tuple[str, ...] = ()
        if isinstance(raw_ev, list):
            ev_types = tuple(raw_ev)
        elif isinstance(raw_ev, str):
            ev_types = tuple(json.loads(raw_ev))

        raw_conditions = row.conditions  # type: ignore[attr-defined]
        if isinstance(raw_conditions, str):
            raw_conditions = json.loads(raw_conditions)
        conditions: tuple[RuleCondition, ...] = ()
        if isinstance(raw_conditions, list):
            conditions = tuple(RuleCondition.from_dict(item) for item in raw_conditions)

        return Rule(
            rule_id=TypedId(entity_type="rule", value=row.rule_id),  # type: ignore[attr-defined]
            policy_id=TypedId(entity_type="policy", value=row.policy_id),  # type: ignore[attr-defined]
            organization_id=OrganizationId(row.record_owner_organization_id),  # type: ignore[attr-defined]
            code=row.code,  # type: ignore[attr-defined]
            name=row.name,  # type: ignore[attr-defined]
            description=row.description,  # type: ignore[attr-defined]
            version=row.version,  # type: ignore[attr-defined]
            severity=SeverityLevel(row.severity),  # type: ignore[attr-defined]
            normative_source=row.normative_source,  # type: ignore[attr-defined]
            required_evidence_types=ev_types,
            conditions=conditions,
            justification=row.justification,  # type: ignore[attr-defined]
            corrective_action=row.corrective_action,  # type: ignore[attr-defined]
            valid_from=vf,
            valid_to=vt,
            created_at=cr_at,
        )
