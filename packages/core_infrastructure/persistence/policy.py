"""Repositório PostgreSQL com RLS para Gestão de Políticas Versionadas (ADR-0038/Passo 6.1)."""

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
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

policies_table = Table(
    "policies",
    organization_metadata,
    Column("policy_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("code", String(100), nullable=False),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=False),
    Column("version", Integer, nullable=False),
    Column("status", String(30), nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=True),
    Column("valid_to", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("published_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint(
        "record_owner_organization_id",
        "code",
        "version",
        name="uq_policies_code_version",
    ),
    CheckConstraint("version >= 1", name="ck_policies_version"),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_policies_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TransactionalPolicyRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalPolicyRepository exige transacao ativa.")

    def save(self, policy: Policy) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.policies (
                    policy_id,
                    record_owner_organization_id,
                    code,
                    name,
                    description,
                    version,
                    status,
                    valid_from,
                    valid_to,
                    created_at,
                    published_at
                ) VALUES (
                    :policy_id,
                    :org_id,
                    :code,
                    :name,
                    :description,
                    :version,
                    :status,
                    :valid_from,
                    :valid_to,
                    :created_at,
                    :published_at
                )
                ON CONFLICT (policy_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    status = EXCLUDED.status,
                    valid_from = EXCLUDED.valid_from,
                    valid_to = EXCLUDED.valid_to,
                    published_at = EXCLUDED.published_at
                """
            ),
            {
                "policy_id": policy.policy_id.value,
                "org_id": policy.organization_id.value,
                "code": policy.code,
                "name": policy.name,
                "description": policy.description,
                "version": policy.version,
                "status": policy.status.value,
                "valid_from": policy.valid_from,
                "valid_to": policy.valid_to,
                "created_at": policy.created_at,
                "published_at": policy.published_at,
            },
        )

    def get_by_id(self, policy_id: TypedId) -> Policy | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    policy_id,
                    record_owner_organization_id,
                    code,
                    name,
                    description,
                    version,
                    status,
                    valid_from,
                    valid_to,
                    created_at,
                    published_at
                FROM core_audit.policies
                WHERE policy_id = :policy_id
                """
            ),
            {"policy_id": policy_id.value},
        ).first()

        if row is None:
            return None

        return self._map_row_to_policy(row)

    def get_by_code_and_version(
        self, organization_id: OrganizationId, code: str, version: int
    ) -> Policy | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    policy_id,
                    record_owner_organization_id,
                    code,
                    name,
                    description,
                    version,
                    status,
                    valid_from,
                    valid_to,
                    created_at,
                    published_at
                FROM core_audit.policies
                WHERE record_owner_organization_id = :org_id
                  AND code = :code
                  AND version = :version
                """
            ),
            {"org_id": organization_id.value, "code": code, "version": version},
        ).first()

        if row is None:
            return None

        return self._map_row_to_policy(row)

    def get_active_at(
        self, organization_id: OrganizationId, code: str, at_time: datetime
    ) -> Policy | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    policy_id,
                    record_owner_organization_id,
                    code,
                    name,
                    description,
                    version,
                    status,
                    valid_from,
                    valid_to,
                    created_at,
                    published_at
                FROM core_audit.policies
                WHERE record_owner_organization_id = :org_id
                  AND code = :code
                  AND status IN ('published', 'superseded')
                  AND (valid_from IS NULL OR valid_from <= :at_time)
                  AND (valid_to IS NULL OR valid_to >= :at_time)
                ORDER BY version DESC
                LIMIT 1
                """
            ),
            {"org_id": organization_id.value, "code": code, "at_time": at_time},
        ).first()

        if row is None:
            return None

        return self._map_row_to_policy(row)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Policy]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    policy_id,
                    record_owner_organization_id,
                    code,
                    name,
                    description,
                    version,
                    status,
                    valid_from,
                    valid_to,
                    created_at,
                    published_at
                FROM core_audit.policies
                WHERE record_owner_organization_id = :org_id
                ORDER BY code ASC, version DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"org_id": organization_id.value, "limit": limit, "offset": offset},
        ).fetchall()

        return [self._map_row_to_policy(row) for row in rows]

    def _map_row_to_policy(self, row: object) -> Policy:
        cr_at = (
            row.created_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
            if row.created_at.tzinfo is None  # type: ignore[attr-defined]
            else row.created_at  # type: ignore[attr-defined]
        )
        pub_at = None
        if row.published_at is not None:  # type: ignore[attr-defined]
            pub_at = (
                row.published_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
                if row.published_at.tzinfo is None  # type: ignore[attr-defined]
                else row.published_at  # type: ignore[attr-defined]
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

        return Policy(
            policy_id=TypedId(entity_type="policy", value=row.policy_id),  # type: ignore[attr-defined]
            organization_id=OrganizationId(row.record_owner_organization_id),  # type: ignore[attr-defined]
            code=row.code,  # type: ignore[attr-defined]
            name=row.name,  # type: ignore[attr-defined]
            description=row.description,  # type: ignore[attr-defined]
            version=row.version,  # type: ignore[attr-defined]
            status=PolicyStatus(row.status),  # type: ignore[attr-defined]
            valid_from=vf,
            valid_to=vt,
            created_at=cr_at,
            published_at=pub_at,
        )
