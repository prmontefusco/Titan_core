"""Persistência PostgreSQL de metadados de chaves sob RLS (ADR-0038/Passo 5.5)."""

from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Connection

from packages.core_domain.crypto import KeyIdentifier, KeyRecord, KeyState
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

CORE_AUDIT_SCHEMA = "core_audit"

key_registry_table = Table(
    "key_registry",
    organization_metadata,
    Column("key_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("purpose", String(100), nullable=False),
    Column("public_key_fingerprint", String(255), nullable=False),
    Column("state", String(50), nullable=False),
    Column("activated_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    Column("revocation_reason", Text, nullable=True),
    Column("version", Integer, nullable=False, server_default="1"),
    CheckConstraint("version >= 1", name="ck_key_registry_version"),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_key_registry_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TransactionalKeyRegistryRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalKeyRegistryRepository exige transacao ativa.")

    def save(self, key_record: KeyRecord) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.key_registry (
                    key_id,
                    record_owner_organization_id,
                    purpose,
                    public_key_fingerprint,
                    state,
                    activated_at,
                    expires_at,
                    revoked_at,
                    revocation_reason,
                    version
                ) VALUES (
                    :key_id,
                    :org_id,
                    :purpose,
                    :public_key_fingerprint,
                    :state,
                    :activated_at,
                    :expires_at,
                    :revoked_at,
                    :revocation_reason,
                    :version
                )
                """
            ),
            {
                "key_id": key_record.key_identifier.key_id.value,
                "org_id": key_record.organization_id.value,
                "purpose": key_record.key_identifier.purpose,
                "public_key_fingerprint": key_record.public_key_fingerprint,
                "state": key_record.state.value,
                "activated_at": key_record.activated_at,
                "expires_at": key_record.expires_at,
                "revoked_at": key_record.revoked_at,
                "revocation_reason": key_record.revocation_reason,
                "version": key_record.version,
            },
        )

    def update(self, key_record: KeyRecord) -> None:
        self.connection.execute(
            text(
                """
                UPDATE core_audit.key_registry
                SET
                    state = :state,
                    expires_at = :expires_at,
                    revoked_at = :revoked_at,
                    revocation_reason = :revocation_reason,
                    version = :version
                WHERE key_id = :key_id
                """
            ),
            {
                "key_id": key_record.key_identifier.key_id.value,
                "state": key_record.state.value,
                "expires_at": key_record.expires_at,
                "revoked_at": key_record.revoked_at,
                "revocation_reason": key_record.revocation_reason,
                "version": key_record.version,
            },
        )

    def get_by_id(self, key_id: TypedId) -> KeyRecord | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    key_id,
                    record_owner_organization_id,
                    purpose,
                    public_key_fingerprint,
                    state,
                    activated_at,
                    expires_at,
                    revoked_at,
                    revocation_reason,
                    version
                FROM core_audit.key_registry
                WHERE key_id = :key_id
                """
            ),
            {"key_id": key_id.value},
        ).first()

        if row is None:
            return None

        return self._map_row_to_key_record(row)

    def get_active_key(self, organization_id: OrganizationId, purpose: str) -> KeyRecord | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    key_id,
                    record_owner_organization_id,
                    purpose,
                    public_key_fingerprint,
                    state,
                    activated_at,
                    expires_at,
                    revoked_at,
                    revocation_reason,
                    version
                FROM core_audit.key_registry
                WHERE record_owner_organization_id = :org_id
                  AND purpose = :purpose
                  AND state = 'ACTIVE'
                ORDER BY activated_at DESC
                LIMIT 1
                """
            ),
            {"org_id": organization_id.value, "purpose": purpose},
        ).first()

        if row is None:
            return None

        return self._map_row_to_key_record(row)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[KeyRecord]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    key_id,
                    record_owner_organization_id,
                    purpose,
                    public_key_fingerprint,
                    state,
                    activated_at,
                    expires_at,
                    revoked_at,
                    revocation_reason,
                    version
                FROM core_audit.key_registry
                WHERE record_owner_organization_id = :org_id
                ORDER BY activated_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"org_id": organization_id.value, "limit": limit, "offset": offset},
        ).fetchall()

        return [self._map_row_to_key_record(row) for row in rows]

    def _map_row_to_key_record(self, row: object) -> KeyRecord:
        act_at = (
            row.activated_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
            if row.activated_at.tzinfo is None  # type: ignore[attr-defined]
            else row.activated_at  # type: ignore[attr-defined]
        )
        exp_at = (
            row.expires_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
            if row.expires_at and row.expires_at.tzinfo is None  # type: ignore[attr-defined]
            else row.expires_at  # type: ignore[attr-defined]
        )
        rev_at = (
            row.revoked_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
            if row.revoked_at and row.revoked_at.tzinfo is None  # type: ignore[attr-defined]
            else row.revoked_at  # type: ignore[attr-defined]
        )

        key_identifier = KeyIdentifier(
            key_id=TypedId(entity_type="key", value=row.key_id),  # type: ignore[attr-defined]
            purpose=row.purpose,  # type: ignore[attr-defined]
        )

        return KeyRecord(
            key_identifier=key_identifier,
            organization_id=OrganizationId(row.record_owner_organization_id),  # type: ignore[attr-defined]
            public_key_fingerprint=row.public_key_fingerprint,  # type: ignore[attr-defined]
            state=KeyState(row.state),  # type: ignore[attr-defined]
            activated_at=act_at,
            expires_at=exp_at,
            revoked_at=rev_at,
            revocation_reason=row.revocation_reason,  # type: ignore[attr-defined]
            version=row.version,  # type: ignore[attr-defined]
        )
