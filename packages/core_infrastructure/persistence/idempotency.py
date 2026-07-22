"""Registro transacional e durável de idempotência no PostgreSQL."""

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    Integer,
    LargeBinary,
    String,
    Table,
    UniqueConstraint,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID, insert
from sqlalchemy.sql.elements import ColumnElement

from packages.core_application.idempotency import IdempotencyRequest, StoredIdempotencyResult
from packages.core_domain import CanonicalPayload
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata

idempotency_records_table = Table(
    "idempotency_records",
    organization_metadata,
    Column("idempotency_record_id", UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("idempotency_key", String(200), nullable=False),
    Column("principal_type", String(100), nullable=False),
    Column("principal_id", UUID(as_uuid=True), nullable=False),
    Column("purpose", String(100), nullable=False),
    Column("operation", String(100), nullable=False),
    Column("intent_digest", LargeBinary, nullable=False),
    Column("requested_at", DateTime(timezone=True), nullable=False),
    Column("status", String(20), nullable=False),
    Column("result_schema", String(100), nullable=True),
    Column("result_version", Integer, nullable=True),
    Column("result_canonical_bytes", LargeBinary, nullable=True),
    CheckConstraint("octet_length(intent_digest) = 32", name="ck_idempotency_intent_digest"),
    CheckConstraint("status IN ('EM_PROCESSAMENTO', 'CONCLUIDA')", name="ck_idempotency_status"),
    CheckConstraint(
        "(status = 'EM_PROCESSAMENTO' AND result_schema IS NULL AND result_version IS NULL "
        "AND result_canonical_bytes IS NULL) OR "
        "(status = 'CONCLUIDA' AND result_schema IS NOT NULL "
        "AND result_version > 0 AND result_canonical_bytes IS NOT NULL)",
        name="ck_idempotency_result_state",
    ),
    UniqueConstraint(
        "record_owner_organization_id",
        "principal_type",
        "principal_id",
        "purpose",
        "operation",
        "idempotency_key",
        name="uq_idempotency_semantic_scope",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class IdempotencyRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("IdempotencyRepository exige transação ativa.")

    def acquire(self, request: IdempotencyRequest) -> StoredIdempotencyResult | None:
        principal = request.principal_reference.target_id
        inserted = self.connection.execute(
            insert(idempotency_records_table)
            .values(
                idempotency_record_id=uuid4(),
                record_owner_organization_id=request.organization_id.value,
                idempotency_key=request.key,
                principal_type=principal.entity_type,
                principal_id=principal.value,
                purpose=request.purpose,
                operation=request.operation,
                intent_digest=request.intent_digest,
                requested_at=request.requested_at,
                status="EM_PROCESSAMENTO",
            )
            .on_conflict_do_nothing(constraint="uq_idempotency_semantic_scope")
            .returning(idempotency_records_table.c.idempotency_record_id)
        ).scalar_one_or_none()
        if inserted is not None:
            return None

        row = self.connection.execute(
            select(
                idempotency_records_table.c.intent_digest,
                idempotency_records_table.c.result_schema,
                idempotency_records_table.c.result_version,
                idempotency_records_table.c.result_canonical_bytes,
            )
            .where(*_scope(request))
            .with_for_update()
        ).one()
        return StoredIdempotencyResult(*row)

    def complete(self, request: IdempotencyRequest, result: CanonicalPayload) -> None:
        changed = self.connection.execute(
            update(idempotency_records_table)
            .where(*_scope(request), idempotency_records_table.c.status == "EM_PROCESSAMENTO")
            .values(
                status="CONCLUIDA",
                result_schema=result.schema,
                result_version=result.version,
                result_canonical_bytes=result.canonical_bytes,
            )
        ).rowcount
        if changed != 1:
            raise RuntimeError("REGISTRO_IDEMPOTENTE_NAO_ADQUIRIDO")


def _scope(request: IdempotencyRequest) -> tuple[ColumnElement[bool], ...]:
    principal = request.principal_reference.target_id
    return (
        idempotency_records_table.c.record_owner_organization_id == request.organization_id.value,
        idempotency_records_table.c.principal_type == principal.entity_type,
        idempotency_records_table.c.principal_id == principal.value,
        idempotency_records_table.c.purpose == request.purpose,
        idempotency_records_table.c.operation == request.operation,
        idempotency_records_table.c.idempotency_key == request.key,
    )
