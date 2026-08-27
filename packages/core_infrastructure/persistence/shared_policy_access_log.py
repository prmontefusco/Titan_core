"""Trilha append-only de acesso a Policy compartilhada (BuyerPolicy Fase 3).

A tabela responde a uma pergunta que o grant sozinho nao responde: o grant diz
que o acesso *era permitido*; a trilha diz que ele *aconteceu*, quando, sobre
qual sujeito e com que resultado. E a diferenca entre autorizacao e acesso
consumado da ADR-0019, aplicada a fronteira contratual da ADR-0065/0066.

Nenhum caminho reescreve linha: a migration cria somente policies de `SELECT` e
`INSERT`, entao `UPDATE` e `DELETE` sao recusados ao runtime pelo proprio
PostgreSQL, e nao apenas por disciplina de codigo.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

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
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_domain.policy_sharing import SharedPolicyAccessLogEntry
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

shared_policy_access_log_table = Table(
    "shared_policy_access_log",
    organization_metadata,
    Column("access_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("grant_id", PG_UUID(as_uuid=True), nullable=False),
    Column("policy_id", PG_UUID(as_uuid=True), nullable=False),
    Column("organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("action", String(50), nullable=False),
    # O sujeito chega pelo contrato HTTP como identificador opaco de ate 100
    # caracteres. Guardar como UUID transformaria entrada legitima do cliente em
    # erro de persistencia, entao a coluna preserva o texto recebido.
    Column("subject_type", String(100), nullable=True),
    Column("subject_id", String(100), nullable=True),
    Column("http_status_code", Integer, nullable=False),
    Column("accessed_at", DateTime(timezone=True), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    ForeignKeyConstraint(
        ["grant_id"],
        ["core_audit.authorization_grants.grant_id"],
        name="fk_shared_policy_access_log_grant",
    ),
    ForeignKeyConstraint(
        ["policy_id"],
        ["core_audit.policies.policy_id"],
        name="fk_shared_policy_access_log_policy",
    ),
    ForeignKeyConstraint(
        ["organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_shared_policy_access_log_org",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_shared_policy_access_log_record_owner_org",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

Index(
    "ix_shared_policy_access_log_policy_accessed_at",
    shared_policy_access_log_table.c.policy_id,
    shared_policy_access_log_table.c.accessed_at,
)
Index("ix_shared_policy_access_log_grant", shared_policy_access_log_table.c.grant_id)


class SharedPolicyAccessLogRepositoryPort(Protocol):
    def log_access(self, entry: SharedPolicyAccessLogEntry) -> None: ...

    def list_by_policy(
        self,
        policy_id: TypedId,
        *,
        http_status_code: int | None = None,
        limit: int,
        offset: int,
    ) -> list[SharedPolicyAccessLogEntry]: ...


_COLUNAS = """
    access_id,
    grant_id,
    policy_id,
    organization_id,
    action,
    subject_type,
    subject_id,
    http_status_code,
    accessed_at,
    record_owner_organization_id
"""


@dataclass(frozen=True, slots=True)
class TransactionalSharedPolicyAccessLogRepository:
    connection: Connection

    def log_access(self, entry: SharedPolicyAccessLogEntry) -> None:
        self.connection.execute(
            text(
                f"""
                INSERT INTO core_audit.shared_policy_access_log ({_COLUNAS})
                VALUES (
                    :access_id,
                    :grant_id,
                    :policy_id,
                    :organization_id,
                    :action,
                    :subject_type,
                    :subject_id,
                    :http_status_code,
                    :accessed_at,
                    :record_owner_organization_id
                )
                """
            ),
            {
                "access_id": entry.access_id.value,
                "grant_id": entry.grant_id,
                "policy_id": entry.policy_id.value,
                "organization_id": entry.organization_id.value,
                "action": entry.action,
                "subject_type": entry.subject_type,
                "subject_id": entry.subject_id,
                "http_status_code": entry.http_status_code,
                "accessed_at": entry.accessed_at,
                "record_owner_organization_id": entry.record_owner_organization_id.value,
            },
        )

    def list_by_policy(
        self,
        policy_id: TypedId,
        *,
        http_status_code: int | None = None,
        limit: int,
        offset: int,
    ) -> list[SharedPolicyAccessLogEntry]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_COLUNAS}
                FROM core_audit.shared_policy_access_log
                WHERE policy_id = :policy_id
                  AND (
                    CAST(:http_status_code AS INTEGER) IS NULL
                    OR http_status_code = CAST(:http_status_code AS INTEGER)
                  )
                ORDER BY accessed_at DESC, access_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {
                "policy_id": policy_id.value,
                "http_status_code": http_status_code,
                "limit": limit,
                "offset": offset,
            },
        ).fetchall()
        return [self._map(row) for row in rows]

    def _map(self, row: object) -> SharedPolicyAccessLogEntry:
        accessed_at: datetime = row.accessed_at  # type: ignore[attr-defined]
        if accessed_at.tzinfo is None:
            accessed_at = accessed_at.replace(tzinfo=UTC)
        return SharedPolicyAccessLogEntry(
            access_id=TypedId(
                "shared_policy_access",
                row.access_id,  # type: ignore[attr-defined]
            ),
            grant_id=row.grant_id,  # type: ignore[attr-defined]
            policy_id=TypedId("policy", row.policy_id),  # type: ignore[attr-defined]
            organization_id=OrganizationId(row.organization_id),  # type: ignore[attr-defined]
            action=row.action,  # type: ignore[attr-defined]
            subject_type=row.subject_type,  # type: ignore[attr-defined]
            subject_id=row.subject_id,  # type: ignore[attr-defined]
            http_status_code=row.http_status_code,  # type: ignore[attr-defined]
            accessed_at=accessed_at,
            record_owner_organization_id=OrganizationId(
                row.record_owner_organization_id  # type: ignore[attr-defined]
            ),
        )
