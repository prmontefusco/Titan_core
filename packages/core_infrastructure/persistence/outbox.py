"""Persistencia atomica de DomainEvent, OutboxMessage e estado de publicacao."""

from dataclasses import dataclass
from datetime import UTC, timedelta
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Table,
    UniqueConstraint,
    insert,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Row

from packages.core_application import (
    BrokerPublicationResult,
    ClaimedOutboxMessage,
    MessageKind,
    OutboxHealthSummary,
    OutboxMessage,
)
from packages.core_domain import CanonicalPayload, DomainEvent
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA, DomainEventRepository
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference

PUBLICATION_STATUS_CLAIMED = "CLAIMED"
PUBLICATION_STATUS_ACCEPTED = "ACEITA_PELO_BROKER"
PUBLICATION_STATUS_UNKNOWN = "RESULTADO_DESCONHECIDO"
PUBLICATION_STATUS_REJECTED = "REJEITADA_PELO_BROKER"

outbox_messages_table = Table(
    "outbox_messages",
    organization_metadata,
    Column("message_id", UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("kind", String(30), nullable=False),
    Column("contract_type", String(100), nullable=False),
    Column("contract_version", Integer, nullable=False),
    Column("actor_type", String(100), nullable=False),
    Column("actor_id", UUID(as_uuid=True), nullable=False),
    Column("producer_type", String(100), nullable=False),
    Column("producer_id", UUID(as_uuid=True), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("correlation_id", UUID(as_uuid=True), nullable=False),
    Column("causation_id", UUID(as_uuid=True), nullable=False),
    Column("idempotency_key", String(200), nullable=True),
    Column("payload_schema", String(100), nullable=False),
    Column("payload_version", Integer, nullable=False),
    Column("payload_canonical_bytes", LargeBinary, nullable=False),
    Column("classification", String(20), nullable=False),
    Column("status", String(20), nullable=False),
    CheckConstraint("contract_version > 0", name="ck_outbox_contract_version"),
    CheckConstraint("payload_version > 0", name="ck_outbox_payload_version"),
    CheckConstraint("status = 'PENDENTE'", name="ck_outbox_initial_status"),
    ForeignKeyConstraint(
        ["causation_id", "record_owner_organization_id"],
        [
            "core_audit.domain_events.event_id",
            "core_audit.domain_events.record_owner_organization_id",
        ],
        name="fk_outbox_causation_event_owner",
    ),
    UniqueConstraint(
        "message_id",
        "record_owner_organization_id",
        name="uq_outbox_messages_message_owner",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

outbox_publication_state_table = Table(
    "outbox_publication_state",
    organization_metadata,
    Column("message_id", UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("status", String(30), nullable=False),
    Column("claim_token", UUID(as_uuid=True), nullable=True),
    Column("publisher_id", String(100), nullable=True),
    Column("claimed_at", DateTime(timezone=True), nullable=True),
    Column("lease_expires_at", DateTime(timezone=True), nullable=True),
    Column("broker_accepted_at", DateTime(timezone=True), nullable=True),
    Column("attempt_count", Integer, nullable=False),
    Column("last_attempt_at", DateTime(timezone=True), nullable=True),
    Column("last_result_at", DateTime(timezone=True), nullable=True),
    Column("last_reason", String(200), nullable=True),
    CheckConstraint("attempt_count >= 0", name="ck_outbox_publication_attempt_count"),
    CheckConstraint(
        "status IN ('CLAIMED', 'ACEITA_PELO_BROKER', "
        "'RESULTADO_DESCONHECIDO', 'REJEITADA_PELO_BROKER')",
        name="ck_outbox_publication_status",
    ),
    ForeignKeyConstraint(
        ["message_id", "record_owner_organization_id"],
        [
            "core_audit.outbox_messages.message_id",
            "core_audit.outbox_messages.record_owner_organization_id",
        ],
        name="fk_outbox_publication_state_message_owner",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

outbox_publication_attempts_table = Table(
    "outbox_publication_attempts",
    organization_metadata,
    Column("attempt_id", UUID(as_uuid=True), primary_key=True),
    Column("message_id", UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("claim_token", UUID(as_uuid=True), nullable=False),
    Column("publisher_id", String(100), nullable=False),
    Column("result", String(30), nullable=False),
    Column("attempted_at", DateTime(timezone=True), nullable=False),
    Column("reason", String(200), nullable=True),
    CheckConstraint(
        "result IN ('ACEITA_PELO_BROKER', 'RESULTADO_DESCONHECIDO', 'REJEITADA_PELO_BROKER')",
        name="ck_outbox_publication_attempt_result",
    ),
    ForeignKeyConstraint(
        ["message_id", "record_owner_organization_id"],
        [
            "core_audit.outbox_messages.message_id",
            "core_audit.outbox_messages.record_owner_organization_id",
        ],
        name="fk_outbox_publication_attempt_message_owner",
    ),
    UniqueConstraint(
        "message_id",
        "claim_token",
        "result",
        name="uq_outbox_publication_attempt_claim_result",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TransactionalEventOutboxRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalEventOutboxRepository exige transacao ativa.")

    def append(self, event: DomainEvent, message: OutboxMessage) -> None:
        if (
            event.organization_id != message.organization_id
            or event.event_id != message.causation_id
        ):
            raise ValueError("EVENT_OUTBOX_DIVERGENTE")
        DomainEventRepository(self.connection).append(event)
        self.connection.execute(
            insert(outbox_messages_table).values(
                message_id=message.message_id.value,
                record_owner_organization_id=message.organization_id.value,
                kind=message.kind.value,
                contract_type=message.contract_type,
                contract_version=message.contract_version,
                actor_type=message.actor_reference.target_id.entity_type,
                actor_id=message.actor_reference.target_id.value,
                producer_type=message.producer_reference.target_id.entity_type,
                producer_id=message.producer_reference.target_id.value,
                occurred_at=message.timestamps.occurred_at,
                recorded_at=message.timestamps.recorded_at,
                correlation_id=message.correlation_id.value,
                causation_id=message.causation_id.value,
                idempotency_key=message.idempotency_key,
                payload_schema=message.payload.schema,
                payload_version=message.payload.version,
                payload_canonical_bytes=message.payload.canonical_bytes,
                classification=message.classification,
                status="PENDENTE",
            )
        )


@dataclass(frozen=True, slots=True)
class OutboxPublicationStateRepository:
    connection: Connection
    lease_duration: timedelta = timedelta(seconds=60)

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("OutboxPublicationStateRepository exige transacao ativa.")
        if self.lease_duration.total_seconds() == 0:
            raise ValueError("lease_duration nao pode ser zero.")

    def claim_next(self, *, publisher_id: str) -> ClaimedOutboxMessage | None:
        if not publisher_id:
            raise ValueError("publisher_id deve ser informado.")
        claim_token = TypedId.new("outbox_publication_claim")
        row = self.connection.execute(
            text(
                """
                WITH candidate AS (
                    SELECT message.message_id
                    FROM core_audit.outbox_messages AS message
                    LEFT JOIN core_audit.outbox_publication_state AS state
                        ON state.message_id = message.message_id
                    WHERE message.status = 'PENDENTE'
                      AND message.record_owner_organization_id =
                        NULLIF(current_setting('titan.organization_id', true), '')::uuid
                      AND (
                        state.message_id IS NULL
                        OR state.status = 'RESULTADO_DESCONHECIDO'
                        OR (
                            state.status = 'CLAIMED'
                            AND state.lease_expires_at < CURRENT_TIMESTAMP
                        )
                      )
                    ORDER BY message.recorded_at, message.message_id
                    LIMIT 1
                    FOR UPDATE OF message SKIP LOCKED
                ),
                claimed AS (
                    INSERT INTO core_audit.outbox_publication_state (
                        message_id,
                        record_owner_organization_id,
                        status,
                        claim_token,
                        publisher_id,
                        claimed_at,
                        lease_expires_at,
                        attempt_count,
                        last_attempt_at,
                        last_result_at,
                        last_reason
                    )
                    SELECT
                        message.message_id,
                        message.record_owner_organization_id,
                        'CLAIMED',
                        :claim_token,
                        :publisher_id,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP + (:lease_seconds * INTERVAL '1 second'),
                        COALESCE(state.attempt_count, 0) + 1,
                        CURRENT_TIMESTAMP,
                        state.last_result_at,
                        state.last_reason
                    FROM candidate
                    JOIN core_audit.outbox_messages AS message
                        ON message.message_id = candidate.message_id
                    LEFT JOIN core_audit.outbox_publication_state AS state
                        ON state.message_id = message.message_id
                    ON CONFLICT (message_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        claim_token = EXCLUDED.claim_token,
                        publisher_id = EXCLUDED.publisher_id,
                        claimed_at = EXCLUDED.claimed_at,
                        lease_expires_at = EXCLUDED.lease_expires_at,
                        attempt_count =
                            core_audit.outbox_publication_state.attempt_count + 1,
                        last_attempt_at = EXCLUDED.last_attempt_at
                    RETURNING message_id
                )
                SELECT message.*
                FROM core_audit.outbox_messages AS message
                JOIN claimed ON claimed.message_id = message.message_id
                """
            ),
            {
                "claim_token": claim_token.value,
                "publisher_id": publisher_id,
                "lease_seconds": int(self.lease_duration.total_seconds()),
            },
        ).first()
        if row is None:
            return None
        return ClaimedOutboxMessage(message=_message_from_row(row), claim_token=claim_token)

    def mark_broker_accepted(
        self, claimed_message: ClaimedOutboxMessage, result: BrokerPublicationResult
    ) -> None:
        self._record_result(
            claimed_message=claimed_message,
            result=result,
            status=PUBLICATION_STATUS_ACCEPTED,
        )

    def mark_unknown(
        self, claimed_message: ClaimedOutboxMessage, result: BrokerPublicationResult
    ) -> None:
        self._record_result(
            claimed_message=claimed_message,
            result=result,
            status=PUBLICATION_STATUS_UNKNOWN,
        )

    def mark_rejected(
        self, claimed_message: ClaimedOutboxMessage, result: BrokerPublicationResult
    ) -> None:
        self._record_result(
            claimed_message=claimed_message,
            result=result,
            status=PUBLICATION_STATUS_REJECTED,
        )

    def _record_result(
        self,
        *,
        claimed_message: ClaimedOutboxMessage,
        result: BrokerPublicationResult,
        status: str,
    ) -> None:
        publisher_id = self.connection.execute(
            text(
                """
                SELECT publisher_id
                FROM core_audit.outbox_publication_state
                WHERE message_id = :message_id
                  AND claim_token = :claim_token
                  AND status = 'CLAIMED'
                """
            ),
            {
                "message_id": claimed_message.message.message_id.value,
                "claim_token": claimed_message.claim_token.value,
            },
        ).scalar_one_or_none()
        if publisher_id is None:
            raise RuntimeError("OUTBOX_CLAIM_INVALIDO_OU_EXPIRADO")

        state = self.connection.execute(
            update(outbox_publication_state_table)
            .where(
                outbox_publication_state_table.c.message_id
                == claimed_message.message.message_id.value,
                outbox_publication_state_table.c.claim_token == claimed_message.claim_token.value,
                outbox_publication_state_table.c.status == PUBLICATION_STATUS_CLAIMED,
            )
            .values(
                status=status,
                broker_accepted_at=(
                    text("CURRENT_TIMESTAMP") if status == PUBLICATION_STATUS_ACCEPTED else None
                ),
                last_result_at=text("CURRENT_TIMESTAMP"),
                last_reason=result.reason,
            )
        )
        if state.rowcount != 1:
            raise RuntimeError("OUTBOX_CLAIM_INVALIDO_OU_EXPIRADO")

        self.connection.execute(
            insert(outbox_publication_attempts_table).values(
                attempt_id=TypedId.new("outbox_publication_attempt").value,
                message_id=claimed_message.message.message_id.value,
                record_owner_organization_id=claimed_message.message.organization_id.value,
                claim_token=claimed_message.claim_token.value,
                publisher_id=publisher_id,
                result=result.status.value,
                attempted_at=text("CURRENT_TIMESTAMP"),
                reason=result.reason,
            )
        )


def _payload_from_stored_bytes(
    *, schema: str, version: int, canonical_bytes: bytes
) -> CanonicalPayload:
    payload = object.__new__(CanonicalPayload)
    object.__setattr__(payload, "schema", schema)
    object.__setattr__(payload, "version", version)
    object.__setattr__(payload, "canonical_bytes", canonical_bytes)
    return payload


def _reference(
    *, entity_type: str, identifier: Any, organization_id: OrganizationId
) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId(entity_type=entity_type, value=identifier),
        organization_id=organization_id,
        contract_version=1,
    )


def _message_from_row(row: Row[Any]) -> OutboxMessage:
    organization_id = OrganizationId(row.record_owner_organization_id)
    return OutboxMessage(
        message_id=TypedId(entity_type="outbox_message", value=row.message_id),
        organization_id=organization_id,
        kind=MessageKind(row.kind),
        contract_type=row.contract_type,
        contract_version=row.contract_version,
        actor_reference=_reference(
            entity_type=row.actor_type,
            identifier=row.actor_id,
            organization_id=organization_id,
        ),
        producer_reference=_reference(
            entity_type=row.producer_type,
            identifier=row.producer_id,
            organization_id=organization_id,
        ),
        timestamps=RecordTimestamps(occurred_at=row.occurred_at, recorded_at=row.recorded_at),
        correlation_id=TypedId(entity_type="correlation", value=row.correlation_id),
        causation_id=TypedId(entity_type="domain_event", value=row.causation_id),
        idempotency_key=row.idempotency_key,
        payload=_payload_from_stored_bytes(
            schema=row.payload_schema,
            version=row.payload_version,
            canonical_bytes=bytes(row.payload_canonical_bytes),
        ),
        classification=row.classification,
    )


@dataclass(frozen=True, slots=True)
class TransactionalOutboxReconciliationRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalOutboxReconciliationRepository exige transacao ativa.")

    def get_health_summary(self) -> OutboxHealthSummary:
        row = self.connection.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE s.status IS NULL OR s.status <> 'ACEITA_PELO_BROKER'
                    ) AS total_pending,
                    COUNT(*) FILTER (
                        WHERE s.status = 'CLAIMED'
                          AND s.lease_expires_at >= CURRENT_TIMESTAMP
                    ) AS active_claims,
                    COUNT(*) FILTER (
                        WHERE s.status = 'CLAIMED'
                          AND s.lease_expires_at < CURRENT_TIMESTAMP
                    ) AS expired_claims,
                    COUNT(*) FILTER (
                        WHERE s.status = 'ACEITA_PELO_BROKER'
                    ) AS accepted_by_broker,
                    COUNT(*) FILTER (
                        WHERE s.status = 'RESULTADO_DESCONHECIDO'
                    ) AS unknown_results,
                    COUNT(*) FILTER (
                        WHERE s.status = 'REJEITADA_PELO_BROKER'
                    ) AS rejected_by_broker,
                    EXTRACT(
                        EPOCH FROM (
                            CURRENT_TIMESTAMP - MIN(m.recorded_at) FILTER (
                                WHERE s.status IS NULL OR s.status <> 'ACEITA_PELO_BROKER'
                            )
                        )
                    )::float AS oldest_pending_age_seconds,
                    EXTRACT(
                        EPOCH FROM (
                            CURRENT_TIMESTAMP - MIN(s.lease_expires_at) FILTER (
                                WHERE s.status = 'CLAIMED'
                                  AND s.lease_expires_at < CURRENT_TIMESTAMP
                            )
                        )
                    )::float AS oldest_expired_claim_age_seconds,
                    CURRENT_TIMESTAMP AS read_at
                FROM core_audit.outbox_messages AS m
                LEFT JOIN core_audit.outbox_publication_state AS s
                    ON s.message_id = m.message_id
                WHERE m.record_owner_organization_id =
                    NULLIF(current_setting('titan.organization_id', true), '')::uuid
                """
            )
        ).one()

        read_at_val = row.read_at.replace(tzinfo=UTC) if row.read_at.tzinfo is None else row.read_at

        return OutboxHealthSummary(
            total_pending=int(row.total_pending or 0),
            active_claims=int(row.active_claims or 0),
            expired_claims=int(row.expired_claims or 0),
            accepted_by_broker=int(row.accepted_by_broker or 0),
            unknown_results=int(row.unknown_results or 0),
            rejected_by_broker=int(row.rejected_by_broker or 0),
            oldest_pending_age_seconds=(
                float(row.oldest_pending_age_seconds)
                if row.oldest_pending_age_seconds is not None
                else None
            ),
            oldest_expired_claim_age_seconds=(
                float(row.oldest_expired_claim_age_seconds)
                if row.oldest_expired_claim_age_seconds is not None
                else None
            ),
            read_at=read_at_val,
        )

    def release_expired_claims(self) -> int:
        result = self.connection.execute(
            text(
                """
                UPDATE core_audit.outbox_publication_state
                SET status = 'RESULTADO_DESCONHECIDO',
                    last_reason = 'LEASE_EXPIRADA',
                    last_result_at = CURRENT_TIMESTAMP
                WHERE status = 'CLAIMED'
                  AND lease_expires_at < CURRENT_TIMESTAMP
                  AND record_owner_organization_id =
                      NULLIF(current_setting('titan.organization_id', true), '')::uuid
                """
            )
        )
        return result.rowcount
