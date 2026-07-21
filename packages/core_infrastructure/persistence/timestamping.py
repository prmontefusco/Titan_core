"""Persistência append-only de tentativas, validações e âncoras temporais."""

from dataclasses import dataclass

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    LargeBinary,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import UUID

from packages.core_application import TemporalAnchor, TimestampAttempt, TimestampValidation
from packages.core_infrastructure.persistence.checkpoints import integrity_checkpoints_table
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata

timestamp_attempts_table = Table(
    "timestamp_attempts",
    organization_metadata,
    Column("attempt_id", UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("checkpoint_id", UUID(as_uuid=True), nullable=False),
    Column("message_imprint", LargeBinary, nullable=False),
    Column("digest_algorithm", String(30), nullable=False),
    Column("policy", String(200), nullable=False),
    Column("nonce", LargeBinary, nullable=False),
    Column("correlation_id", UUID(as_uuid=True), nullable=False),
    Column("requested_at", DateTime(timezone=True), nullable=False),
    Column("status", String(30), nullable=False),
    Column("provider_id", String(100), nullable=False),
    Column("raw_token", LargeBinary, nullable=True),
    Column("received_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("octet_length(message_imprint) = 32", name="ck_attempts_imprint"),
    CheckConstraint("octet_length(nonce) >= 16", name="ck_attempts_nonce"),
    CheckConstraint(
        "status IN ('PENDENTE', 'RESULTADO_DESCONHECIDO', 'TOKEN_RECEBIDO')",
        name="ck_attempts_status",
    ),
    CheckConstraint(
        "(status = 'TOKEN_RECEBIDO' AND raw_token IS NOT NULL AND received_at IS NOT NULL) OR "
        "(status <> 'TOKEN_RECEBIDO' AND raw_token IS NULL AND received_at IS NULL)",
        name="ck_attempts_token_state",
    ),
    ForeignKeyConstraint(
        ["checkpoint_id"],
        ["core_audit.integrity_checkpoints.checkpoint_id"],
        name="fk_timestamp_attempts_checkpoint",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

timestamp_validations_table = Table(
    "timestamp_validations",
    organization_metadata,
    Column("validation_id", UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("attempt_id", UUID(as_uuid=True), nullable=False),
    Column("status", String(20), nullable=False),
    Column("reason_code", String(100), nullable=False),
    Column("validated_at", DateTime(timezone=True), nullable=False),
    Column("proved_at", DateTime(timezone=True), nullable=True),
    Column("token_digest", LargeBinary, nullable=False),
    CheckConstraint(
        "status IN ('VALIDO', 'INVALIDO', 'INDETERMINADO')", name="ck_validations_status"
    ),
    CheckConstraint("octet_length(token_digest) = 32", name="ck_validations_digest"),
    CheckConstraint(
        "(status = 'VALIDO' AND proved_at IS NOT NULL) OR status <> 'VALIDO'",
        name="ck_validations_proved_at",
    ),
    ForeignKeyConstraint(
        ["attempt_id"],
        ["core_audit.timestamp_attempts.attempt_id"],
        name="fk_timestamp_validations_attempt",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

temporal_anchors_table = Table(
    "temporal_anchors",
    organization_metadata,
    Column("anchor_id", UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("checkpoint_id", UUID(as_uuid=True), nullable=False),
    Column("attempt_id", UUID(as_uuid=True), nullable=False),
    Column("validation_id", UUID(as_uuid=True), nullable=False),
    Column("message_imprint", LargeBinary, nullable=False),
    Column("proved_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("octet_length(message_imprint) = 32", name="ck_anchors_imprint"),
    ForeignKeyConstraint(
        ["checkpoint_id"],
        ["core_audit.integrity_checkpoints.checkpoint_id"],
        name="fk_temporal_anchors_checkpoint",
    ),
    ForeignKeyConstraint(
        ["attempt_id"],
        ["core_audit.timestamp_attempts.attempt_id"],
        name="fk_temporal_anchors_attempt",
    ),
    ForeignKeyConstraint(
        ["validation_id"],
        ["core_audit.timestamp_validations.validation_id"],
        name="fk_temporal_anchors_validation",
    ),
    UniqueConstraint("validation_id", name="uq_temporal_anchors_validation"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TimestampAuditRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TimestampAuditRepository exige transação ativa.")

    def add_attempt(self, attempt: TimestampAttempt) -> None:
        owner = self.connection.execute(
            select(integrity_checkpoints_table.c.record_owner_organization_id).where(
                integrity_checkpoints_table.c.checkpoint_id == attempt.request.checkpoint_id.value
            )
        ).scalar_one()
        self.connection.execute(
            insert(timestamp_attempts_table).values(
                attempt_id=attempt.request.attempt_id.value,
                record_owner_organization_id=owner,
                checkpoint_id=attempt.request.checkpoint_id.value,
                message_imprint=attempt.request.message_imprint,
                digest_algorithm=attempt.request.digest_algorithm,
                policy=attempt.request.policy,
                nonce=attempt.request.nonce,
                correlation_id=attempt.request.correlation_id.value,
                requested_at=attempt.request.requested_at,
                status=attempt.status.value,
                provider_id=attempt.provider_id,
                raw_token=attempt.raw_token,
                received_at=attempt.received_at,
            )
        )

    def add_validation(self, validation: TimestampValidation) -> None:
        owner = self.connection.execute(
            select(timestamp_attempts_table.c.record_owner_organization_id).where(
                timestamp_attempts_table.c.attempt_id == validation.attempt_id.value
            )
        ).scalar_one()
        self.connection.execute(
            insert(timestamp_validations_table).values(
                validation_id=validation.validation_id.value,
                record_owner_organization_id=owner,
                attempt_id=validation.attempt_id.value,
                status=validation.status.value,
                reason_code=validation.reason_code,
                validated_at=validation.validated_at,
                proved_at=validation.proved_at,
                token_digest=validation.token_digest,
            )
        )

    def add_anchor(self, anchor: TemporalAnchor) -> None:
        owner = self.connection.execute(
            select(integrity_checkpoints_table.c.record_owner_organization_id).where(
                integrity_checkpoints_table.c.checkpoint_id == anchor.checkpoint_id.value
            )
        ).scalar_one()
        self.connection.execute(
            insert(temporal_anchors_table).values(
                anchor_id=anchor.anchor_id.value,
                record_owner_organization_id=owner,
                checkpoint_id=anchor.checkpoint_id.value,
                attempt_id=anchor.attempt_id.value,
                validation_id=anchor.validation_id.value,
                message_imprint=anchor.message_imprint,
                proved_at=anchor.proved_at,
            )
        )
