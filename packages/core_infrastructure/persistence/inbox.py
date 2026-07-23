"""Persistencia do mecanismo de mensageria assincrona, Inbox e quarentena (ADR-0038)."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID as PyUUID

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
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_application import (
    AuthorizationEvaluationMode,
    ConsumerReceipt,
    DeliveryHandlingOutcome,
    InboxStatus,
    IncomingMessageEnvelope,
    MessageHandler,
    ProcessingOutcome,
    QuarantinedMessageRecord,
    ReplayRequest,
    ReplayResult,
)
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

CORE_MESSAGING_SCHEMA = "core_messaging"

inbox_messages_table = Table(
    "inbox_messages",
    organization_metadata,
    Column("message_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("message_type", String(100), nullable=False),
    Column("schema_version", Integer, nullable=False),
    Column("semantic_operation_id", PG_UUID(as_uuid=True), nullable=False),
    Column("producer_identity", String(100), nullable=False),
    Column("semantic_message_digest", LargeBinary, nullable=False),
    Column("authorization_evaluation_mode", String(50), nullable=False),
    Column("status", String(30), nullable=False),
    Column("available_at", DateTime(timezone=True), nullable=True),
    Column("attempt_number", Integer, nullable=False, server_default="1"),
    Column("received_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("completion_result_code", String(30), nullable=True),
    Column("effect_reference", String(200), nullable=True),
    Column("decision_reference", String(200), nullable=True),
    Column("result_digest", LargeBinary, nullable=True),
    CheckConstraint("schema_version > 0", name="ck_inbox_schema_version"),
    CheckConstraint("attempt_number >= 1", name="ck_inbox_attempt_number"),
    CheckConstraint(
        "status IN ('EM_PROCESSAMENTO', 'AGUARDANDO_RETRY', 'CONCLUIDA', "
        "'EM_QUARENTENA', 'RECONCILIACAO_PENDENTE')",
        name="ck_inbox_status",
    ),
    CheckConstraint(
        "completion_result_code IS NULL OR completion_result_code IN "
        "('SUCCESS', 'BUSINESS_REJECTION', 'NO_OP', 'AUTHORIZATION_REJECTED')",
        name="ck_inbox_completion_result_code",
    ),
    UniqueConstraint(
        "message_id",
        "record_owner_organization_id",
        name="uq_inbox_messages_message_owner",
    ),
    schema=CORE_MESSAGING_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_messaging",
)

inbox_delivery_attempts_table = Table(
    "inbox_delivery_attempts",
    organization_metadata,
    Column("attempt_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("message_id", PG_UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("consumer_id", String(100), nullable=False),
    Column("attempt_number", Integer, nullable=False),
    Column("handling_result", String(30), nullable=False),
    Column("attempted_at", DateTime(timezone=True), nullable=False),
    Column("reason", String(200), nullable=True),
    CheckConstraint("attempt_number >= 1", name="ck_inbox_attempts_number"),
    CheckConstraint(
        "handling_result IN ('PROCESSED', 'DUPLICATE_RECOVERED', "
        "'RETRY_SCHEDULED', 'CONFLICT_DETECTED', 'QUARANTINED', 'REPLAY_REQUESTED')",
        name="ck_inbox_attempts_handling_result",
    ),
    ForeignKeyConstraint(
        ["message_id", "record_owner_organization_id"],
        [
            "core_messaging.inbox_messages.message_id",
            "core_messaging.inbox_messages.record_owner_organization_id",
        ],
        name="fk_inbox_attempts_message_owner",
    ),
    schema=CORE_MESSAGING_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_messaging",
)

inbox_conflicts_table = Table(
    "inbox_conflicts",
    organization_metadata,
    Column("conflict_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("message_id", PG_UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("received_digest", LargeBinary, nullable=False),
    Column("expected_digest", LargeBinary, nullable=False),
    Column("handling_result", String(30), nullable=False, server_default="CONFLICT_DETECTED"),
    Column("detected_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["message_id", "record_owner_organization_id"],
        [
            "core_messaging.inbox_messages.message_id",
            "core_messaging.inbox_messages.record_owner_organization_id",
        ],
        name="fk_inbox_conflicts_message_owner",
    ),
    schema=CORE_MESSAGING_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_messaging",
)

untrusted_message_quarantine_table = Table(
    "untrusted_message_quarantine",
    organization_metadata,
    Column("quarantine_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("message_id", PG_UUID(as_uuid=True), nullable=False),
    Column("alleged_producer", String(100), nullable=True),
    Column("alleged_organization", String(100), nullable=True),
    Column("received_bytes_digest", LargeBinary, nullable=False),
    Column("rejection_reason_code", String(50), nullable=False),
    Column("sanitized_routing_metadata", String(200), nullable=True),
    Column("quarantined_at", DateTime(timezone=True), nullable=False),
    schema=CORE_MESSAGING_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_messaging",
)


@dataclass(frozen=True, slots=True)
class TransactionalInboxRepository:
    connection: Connection
    consumer_id: str = "worker_default"

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalInboxRepository exige transacao ativa.")
        if not self.consumer_id:
            raise ValueError("consumer_id deve ser informado.")

    def record_untrusted_quarantine(
        self,
        envelope_bytes: bytes,
        alleged_producer: str | None,
        alleged_org: str | None,
        reason_code: str,
    ) -> ConsumerReceipt:
        return self._record_untrusted_quarantine_in_transaction(
            envelope_bytes=envelope_bytes,
            alleged_producer=alleged_producer,
            alleged_org=alleged_org,
            reason_code=reason_code,
        )

    def process_message(
        self, envelope: IncomingMessageEnvelope, handler: MessageHandler
    ) -> ConsumerReceipt:
        # Validação pré-tenant (produtor e modo de autorização)
        if not self._validate_producer_authority(envelope):
            return self._record_untrusted_quarantine_in_transaction(
                envelope_bytes=envelope.compute_semantic_digest(),
                alleged_producer=str(envelope.producer_reference.target_id.value),
                alleged_org=str(envelope.organization_id.value),
                reason_code="PRODUCER_AUTHORITY_INVALID",
            )

        # RLS SET LOCAL escopado estritamente à transação
        self.connection.execute(
            text("SELECT set_config('titan.organization_id', :org_id, true)"),
            {"org_id": str(envelope.organization_id.value)},
        )

        digest = envelope.compute_semantic_digest()
        now_utc = datetime.now(UTC)

        # Tentativa de aquisição atômica na Inbox
        inserted_id = self.connection.execute(
            text(
                """
                INSERT INTO core_messaging.inbox_messages (
                    message_id,
                    record_owner_organization_id,
                    message_type,
                    schema_version,
                    semantic_operation_id,
                    producer_identity,
                    semantic_message_digest,
                    authorization_evaluation_mode,
                    status,
                    received_at,
                    attempt_number
                ) VALUES (
                    :message_id,
                    :org_id,
                    :message_type,
                    :schema_version,
                    :semantic_operation_id,
                    :producer_identity,
                    :digest,
                    :auth_mode,
                    'EM_PROCESSAMENTO',
                    :now_utc,
                    1
                )
                ON CONFLICT (message_id) DO NOTHING
                RETURNING message_id
                """
            ),
            {
                "message_id": envelope.message_id.value,
                "org_id": envelope.organization_id.value,
                "message_type": envelope.contract_type,
                "schema_version": envelope.contract_version,
                "semantic_operation_id": envelope.semantic_operation_id.value,
                "producer_identity": str(envelope.producer_reference.target_id.value),
                "digest": digest,
                "auth_mode": envelope.auth_evaluation_mode.value,
                "now_utc": now_utc,
            },
        ).scalar_one_or_none()

        if inserted_id is None:
            # Registro já existia na Inbox
            return self._handle_existing_inbox_row(envelope, digest, now_utc, handler)

        # Nova mensagem inserida (EM_PROCESSAMENTO): executa o handler sob a mesma transação
        processing_outcome, effect_ref, decision_ref = handler.handle(envelope)
        result_digest = hashlib.sha256(
            f"{processing_outcome.value}:{effect_ref}:{decision_ref}".encode()
        ).digest()

        self.connection.execute(
            update(inbox_messages_table)
            .where(inbox_messages_table.c.message_id == envelope.message_id.value)
            .values(
                status=InboxStatus.CONCLUIDA.value,
                completion_result_code=processing_outcome.value,
                effect_reference=effect_ref,
                decision_reference=decision_ref,
                completed_at=now_utc,
                result_digest=result_digest,
            )
        )

        self._record_attempt(
            envelope=envelope,
            attempt_number=1,
            handling_result=DeliveryHandlingOutcome.PROCESSED.value,
            attempted_at=now_utc,
            reason=None,
        )

        return ConsumerReceipt(
            message_id=envelope.message_id,
            organization_id=envelope.organization_id,
            handling_outcome=DeliveryHandlingOutcome.PROCESSED,
            processing_outcome=processing_outcome,
            effect_reference=effect_ref,
            decision_reference=decision_ref,
            completed_at=now_utc,
        )

    def _handle_existing_inbox_row(
        self,
        envelope: IncomingMessageEnvelope,
        digest: bytes,
        now_utc: datetime,
        handler: MessageHandler,
    ) -> ConsumerReceipt:
        row = self.connection.execute(
            select(inbox_messages_table).where(
                inbox_messages_table.c.message_id == envelope.message_id.value
            )
        ).first()

        if row is None:
            raise RuntimeError("INBOX_REGISTRO_NAO_ENCONTRADO")

        status = row.status
        stored_digest = bytes(row.semantic_message_digest)

        if status == InboxStatus.CONCLUIDA.value:
            if stored_digest == digest:
                # Duplicata legítima pós-commit
                self._record_attempt(
                    envelope=envelope,
                    attempt_number=row.attempt_number + 1,
                    handling_result=DeliveryHandlingOutcome.DUPLICATE_RECOVERED.value,
                    attempted_at=now_utc,
                    reason="DUPLICATE_RECOVERED",
                )
                return ConsumerReceipt(
                    message_id=envelope.message_id,
                    organization_id=envelope.organization_id,
                    handling_outcome=DeliveryHandlingOutcome.DUPLICATE_RECOVERED,
                    processing_outcome=ProcessingOutcome(row.completion_result_code)
                    if row.completion_result_code
                    else None,
                    effect_reference=row.effect_reference,
                    decision_reference=row.decision_reference,
                    completed_at=row.completed_at,
                )
            else:
                # Divergência de digest: registra conflito separado sem alterar o original
                self.connection.execute(
                    insert(inbox_conflicts_table).values(
                        conflict_id=TypedId.new("inbox_conflict").value,
                        message_id=envelope.message_id.value,
                        record_owner_organization_id=envelope.organization_id.value,
                        received_digest=digest,
                        expected_digest=stored_digest,
                        handling_result=DeliveryHandlingOutcome.CONFLICT_DETECTED.value,
                        detected_at=now_utc,
                    )
                )
                self._record_attempt(
                    envelope=envelope,
                    attempt_number=row.attempt_number + 1,
                    handling_result=DeliveryHandlingOutcome.CONFLICT_DETECTED.value,
                    attempted_at=now_utc,
                    reason="DIGEST_MISMATCH",
                )
                return ConsumerReceipt(
                    message_id=envelope.message_id,
                    organization_id=envelope.organization_id,
                    handling_outcome=DeliveryHandlingOutcome.CONFLICT_DETECTED,
                    reason="DIGEST_MISMATCH",
                )

        if status == InboxStatus.AGUARDANDO_RETRY.value:
            if stored_digest == digest and row.available_at and row.available_at <= now_utc:
                # Retry elegível: transita para EM_PROCESSAMENTO e executa
                self.connection.execute(
                    update(inbox_messages_table)
                    .where(inbox_messages_table.c.message_id == envelope.message_id.value)
                    .values(status=InboxStatus.EM_PROCESSAMENTO.value)
                )
                processing_outcome, effect_ref, decision_ref = handler.handle(envelope)
                result_digest = hashlib.sha256(
                    f"{processing_outcome.value}:{effect_ref}:{decision_ref}".encode()
                ).digest()

                self.connection.execute(
                    update(inbox_messages_table)
                    .where(inbox_messages_table.c.message_id == envelope.message_id.value)
                    .values(
                        status=InboxStatus.CONCLUIDA.value,
                        completion_result_code=processing_outcome.value,
                        effect_reference=effect_ref,
                        decision_reference=decision_ref,
                        completed_at=now_utc,
                        result_digest=result_digest,
                    )
                )
                self._record_attempt(
                    envelope=envelope,
                    attempt_number=row.attempt_number + 1,
                    handling_result=DeliveryHandlingOutcome.PROCESSED.value,
                    attempted_at=now_utc,
                    reason="RETRY_SUCCEEDED",
                )
                return ConsumerReceipt(
                    message_id=envelope.message_id,
                    organization_id=envelope.organization_id,
                    handling_outcome=DeliveryHandlingOutcome.PROCESSED,
                    processing_outcome=processing_outcome,
                    effect_reference=effect_ref,
                    decision_reference=decision_ref,
                    completed_at=now_utc,
                )

        if status == InboxStatus.EM_QUARENTENA.value:
            self._record_attempt(
                envelope=envelope,
                attempt_number=row.attempt_number + 1,
                handling_result=DeliveryHandlingOutcome.QUARANTINED.value,
                attempted_at=now_utc,
                reason="EM_QUARENTENA",
            )
            return ConsumerReceipt(
                message_id=envelope.message_id,
                organization_id=envelope.organization_id,
                handling_outcome=DeliveryHandlingOutcome.QUARANTINED,
                reason="EM_QUARENTENA",
            )

        # Outros estados ou retry ainda não disponível
        self._record_attempt(
            envelope=envelope,
            attempt_number=row.attempt_number + 1,
            handling_result=DeliveryHandlingOutcome.RETRY_SCHEDULED.value,
            attempted_at=now_utc,
            reason="RETRY_NOT_YET_AVAILABLE",
        )
        return ConsumerReceipt(
            message_id=envelope.message_id,
            organization_id=envelope.organization_id,
            handling_outcome=DeliveryHandlingOutcome.RETRY_SCHEDULED,
            reason="RETRY_NOT_YET_AVAILABLE",
        )

    def record_retry_control_transaction(
        self, envelope: IncomingMessageEnvelope, reason: str, backoff_seconds: int
    ) -> ConsumerReceipt:
        now_utc = datetime.now(UTC)
        available_at = now_utc + timedelta(seconds=backoff_seconds)

        self.connection.execute(
            text("SELECT set_config('titan.organization_id', :org_id, true)"),
            {"org_id": str(envelope.organization_id.value)},
        )

        self.connection.execute(
            update(inbox_messages_table)
            .where(inbox_messages_table.c.message_id == envelope.message_id.value)
            .values(
                status=InboxStatus.AGUARDANDO_RETRY.value,
                available_at=available_at,
                attempt_number=inbox_messages_table.c.attempt_number + 1,
            )
        )

        self._record_attempt(
            envelope=envelope,
            attempt_number=2,
            handling_result=DeliveryHandlingOutcome.RETRY_SCHEDULED.value,
            attempted_at=now_utc,
            reason=reason,
        )

        return ConsumerReceipt(
            message_id=envelope.message_id,
            organization_id=envelope.organization_id,
            handling_outcome=DeliveryHandlingOutcome.RETRY_SCHEDULED,
            reason=reason,
        )

    def _record_untrusted_quarantine_in_transaction(
        self,
        envelope_bytes: bytes,
        alleged_producer: str | None,
        alleged_org: str | None,
        reason_code: str,
    ) -> ConsumerReceipt:
        now_utc = datetime.now(UTC)
        quarantine_id = TypedId.new("untrusted_quarantine")
        message_id = TypedId.new("incoming_message")
        digest = hashlib.sha256(envelope_bytes).digest()

        self.connection.execute(
            insert(untrusted_message_quarantine_table).values(
                quarantine_id=quarantine_id.value,
                message_id=message_id.value,
                alleged_producer=alleged_producer,
                alleged_organization=alleged_org,
                received_bytes_digest=digest,
                rejection_reason_code=reason_code,
                sanitized_routing_metadata=None,
                quarantined_at=now_utc,
            )
        )

        return ConsumerReceipt(
            message_id=message_id,
            organization_id=OrganizationId.new(),
            handling_outcome=DeliveryHandlingOutcome.QUARANTINED,
            reason=reason_code,
        )

    def _validate_producer_authority(self, envelope: IncomingMessageEnvelope) -> bool:
        # Valida que o produtor não é vazio e o modo de autorização atende às regras
        if not envelope.producer_reference.target_id.value:
            return False
        if (
            envelope.auth_evaluation_mode is AuthorizationEvaluationMode.AT_ACCEPTANCE
            and envelope.auth_reference is None
        ):
            return False
        return True

    def _record_attempt(
        self,
        *,
        envelope: IncomingMessageEnvelope,
        attempt_number: int,
        handling_result: str,
        attempted_at: datetime,
        reason: str | None,
    ) -> None:
        self.connection.execute(
            insert(inbox_delivery_attempts_table).values(
                attempt_id=TypedId.new("inbox_delivery_attempt").value,
                message_id=envelope.message_id.value,
                record_owner_organization_id=envelope.organization_id.value,
                consumer_id=self.consumer_id,
                attempt_number=attempt_number,
                handling_result=handling_result,
                attempted_at=attempted_at,
                reason=reason,
            )
        )


@dataclass(frozen=True, slots=True)
class TransactionalInboxQuarantineRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalInboxQuarantineRepository exige transacao ativa.")

    def list_quarantined(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[QuarantinedMessageRecord]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    quarantine_id,
                    message_id,
                    alleged_organization,
                    alleged_producer,
                    rejection_reason_code,
                    quarantined_at
                FROM core_messaging.untrusted_message_quarantine
                ORDER BY quarantined_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        ).fetchall()

        records: list[QuarantinedMessageRecord] = []
        for r in rows:
            q_at = (
                r.quarantined_at.replace(tzinfo=UTC)
                if r.quarantined_at.tzinfo is None
                else r.quarantined_at
            )
            org_id = None
            if r.alleged_organization:
                try:
                    uuid_val = (
                        r.alleged_organization
                        if isinstance(r.alleged_organization, PyUUID)
                        else PyUUID(str(r.alleged_organization))
                    )
                    org_id = OrganizationId(uuid_val)
                except (ValueError, TypeError):
                    org_id = None

            records.append(
                QuarantinedMessageRecord(
                    quarantine_id=TypedId(entity_type="quarantine", value=r.quarantine_id),
                    message_id=TypedId(entity_type="outbox_message", value=r.message_id)
                    if r.message_id
                    else None,
                    organization_id=org_id,
                    alleged_producer=r.alleged_producer,
                    reason_code=r.rejection_reason_code,
                    quarantined_at=q_at,
                )
            )
        return records

    def replay_message(self, request: ReplayRequest) -> ReplayResult:
        operator_id = request.operator_actor_reference.target_id.value
        row = self.connection.execute(
            text(
                """
                SELECT
                    quarantine_id,
                    message_id,
                    alleged_organization,
                    alleged_producer,
                    received_bytes_digest,
                    rejection_reason_code
                FROM core_messaging.untrusted_message_quarantine
                WHERE quarantine_id = :quarantine_id
                """
            ),
            {"quarantine_id": request.quarantine_id.value},
        ).first()

        if row is None:
            return ReplayResult(
                quarantine_id=request.quarantine_id,
                status="NOT_FOUND",
                processed_at=datetime.now(UTC),
                reason="Registro de quarentena nao localizado.",
            )

        target_org_id = None
        if row.alleged_organization:
            try:
                target_org_id = (
                    row.alleged_organization
                    if isinstance(row.alleged_organization, PyUUID)
                    else PyUUID(str(row.alleged_organization))
                )
            except (ValueError, TypeError):
                target_org_id = None

        msg_id = row.message_id if row.message_id else row.quarantine_id
        operator_org = request.operator_actor_reference.organization_id
        fallback_org_id = (
            operator_org.value if operator_org else PyUUID("00000000-0000-0000-0000-000000000000")
        )
        final_org_id = target_org_id if target_org_id else fallback_org_id

        self.connection.execute(
            text(
                """
                INSERT INTO core_messaging.inbox_messages (
                    message_id,
                    record_owner_organization_id,
                    message_type,
                    schema_version,
                    semantic_operation_id,
                    producer_identity,
                    semantic_message_digest,
                    authorization_evaluation_mode,
                    status,
                    received_at,
                    attempt_number
                ) VALUES (
                    :msg_id,
                    :org_id,
                    'titan.quarantine.untrusted',
                    1,
                    :quarantine_id,
                    :producer,
                    :digest,
                    'SERVICE_AUTHORITY_ONLY',
                    'EM_PROCESSAMENTO',
                    CURRENT_TIMESTAMP,
                    1
                )
                ON CONFLICT (message_id) DO UPDATE
                SET status = 'EM_PROCESSAMENTO'
                """
            ),
            {
                "msg_id": msg_id,
                "org_id": final_org_id,
                "quarantine_id": row.quarantine_id,
                "producer": row.alleged_producer or "unknown",
                "digest": row.received_bytes_digest or b"",
            },
        )

        self.connection.execute(
            text(
                """
                INSERT INTO core_messaging.inbox_delivery_attempts (
                    attempt_id,
                    message_id,
                    record_owner_organization_id,
                    consumer_id,
                    attempt_number,
                    handling_result,
                    attempted_at,
                    reason
                ) VALUES (
                    :attempt_id,
                    :msg_id,
                    :org_id,
                    :consumer_id,
                    1,
                    'QUARANTINED',
                    CURRENT_TIMESTAMP,
                    :reason
                )
                """
            ),
            {
                "attempt_id": TypedId.new("inbox_delivery_attempt").value,
                "msg_id": msg_id,
                "org_id": final_org_id,
                "consumer_id": f"operator:{operator_id}",
                "reason": f"REPLAY_REQUESTED por {operator_id}: {request.reason}",
            },
        )

        return ReplayResult(
            quarantine_id=request.quarantine_id,
            status="REQUEUED",
            processed_at=datetime.now(UTC),
            reason=f"Replay autorizado pelo operador {operator_id}",
        )
