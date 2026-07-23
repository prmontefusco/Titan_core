"""Repositório PostgreSQL com RLS para sincronização offline (Passo 7.9)."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_domain.synchronization import (
    DeviceClockReading,
    OfflineOperation,
    OperationManifestEntry,
    SynchronizationBatch,
    SynchronizationBatchResult,
    SynchronizationBatchState,
    SynchronizationConflict,
    SynchronizationConflictReason,
    SynchronizationResult,
    SynchronizationResultStatus,
    TimeConfidenceLevel,
)
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

offline_operations_table = Table(
    "offline_operations",
    organization_metadata,
    Column("operation_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("device_id", PG_UUID(as_uuid=True), nullable=False),
    Column("device_contract_version", Integer, nullable=False),
    Column("actor_entity_type", String(100), nullable=False),
    Column("actor_id", PG_UUID(as_uuid=True), nullable=False),
    Column("actor_contract_version", Integer, nullable=False),
    Column("semantic_identity", String(255), nullable=False),
    Column("idempotency_key", String(200), nullable=False),
    Column("operation_type", String(100), nullable=False),
    Column("contract_version", Integer, nullable=False),
    Column("local_sequence", Integer, nullable=False),
    Column("intent_digest", String(64), nullable=False),
    Column("client_observed_at", DateTime(timezone=True), nullable=False),
    Column("claimed_occurred_at", DateTime(timezone=True), nullable=False),
    Column("timezone_name", String(100), nullable=False),
    Column("time_confidence", String(40), nullable=False),
    Column("monotonic_continuity_id", String(100), nullable=False, server_default=""),
    Column("monotonic_elapsed_ms", BigInteger, nullable=True),
    Column("last_server_contact_at", DateTime(timezone=True), nullable=True),
    Column("payload_schema", String(100), nullable=False),
    Column("payload_version", Integer, nullable=False),
    Column("payload_canonical_bytes", LargeBinary, nullable=False),
    Column("depends_on", JSONB, nullable=False, server_default="[]"),
    Column("evidence_references", JSONB, nullable=False, server_default="[]"),
    Column("correlation_id", PG_UUID(as_uuid=True), nullable=True),
    Column("server_received_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("local_sequence >= 1", name="ck_offline_operations_local_sequence"),
    CheckConstraint("contract_version >= 1", name="ck_offline_operations_contract_version"),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_offline_operations_organization",
    ),
    # Sem UNIQUE em (organization, idempotency_key): a segunda captura com a mesma
    # chave e intenção divergente precisa ser preservada para virar conflito
    # explícito. Uma constraint aqui apagaria a captura em vez de explicá-la.
    Index(
        "ix_offline_operations_idempotency",
        "record_owner_organization_id",
        "idempotency_key",
        "server_received_at",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

synchronization_results_table = Table(
    "synchronization_results",
    organization_metadata,
    Column("operation_id", PG_UUID(as_uuid=True), nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("batch_id", PG_UUID(as_uuid=True), nullable=False),
    Column("status", String(40), nullable=False),
    Column("decided_at", DateTime(timezone=True), nullable=False),
    Column("reason_codes", JSONB, nullable=False, server_default="[]"),
    Column("produced_references", JSONB, nullable=False, server_default="[]"),
    Column("conflict", JSONB, nullable=True),
    Column("pending_dependencies", JSONB, nullable=False, server_default="[]"),
    Column("reconciliation_deadline", DateTime(timezone=True), nullable=True),
    Column("limitations", JSONB, nullable=False, server_default="[]"),
    PrimaryKeyConstraint("operation_id", "attempt", name="pk_synchronization_results"),
    CheckConstraint("attempt >= 1", name="ck_synchronization_results_attempt"),
    CheckConstraint(
        "status <> 'RESULTADO_DESCONHECIDO' OR reconciliation_deadline IS NOT NULL",
        name="ck_synchronization_results_reconciliation",
    ),
    CheckConstraint(
        "(status = 'CONFLITANTE') = (conflict IS NOT NULL)",
        name="ck_synchronization_results_conflict",
    ),
    CheckConstraint(
        "status <> 'ACEITA' OR jsonb_array_length(produced_references) > 0",
        name="ck_synchronization_results_efeito",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_synchronization_results_organization",
    ),
    Index("ix_synchronization_results_batch", "record_owner_organization_id", "batch_id"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

synchronization_batches_table = Table(
    "synchronization_batches",
    organization_metadata,
    Column("batch_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("device_id", PG_UUID(as_uuid=True), nullable=False),
    Column("batch_version", Integer, nullable=False),
    Column("manifest", JSONB, nullable=False),
    Column("manifest_digest", String(64), nullable=False),
    Column("operation_count", Integer, nullable=False),
    Column("sequence_first", Integer, nullable=False),
    Column("sequence_last", Integer, nullable=False),
    Column("created_at_device", DateTime(timezone=True), nullable=False),
    Column("first_received_at", DateTime(timezone=True), nullable=False),
    Column("attempts", Integer, nullable=False, server_default="1"),
    Column("state", String(40), nullable=False),
    Column("examined_count", Integer, nullable=False, server_default="0"),
    Column("counts", JSONB, nullable=False, server_default="{}"),
    Column("gaps", JSONB, nullable=False, server_default="[]"),
    Column("limitations", JSONB, nullable=False, server_default="[]"),
    Column("processed_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("attempts >= 1", name="ck_synchronization_batches_attempts"),
    CheckConstraint("operation_count >= 1", name="ck_synchronization_batches_count"),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_synchronization_batches_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class StoredOfflineOperation:
    """Envelope como gravado, com o payload preservado em bytes canônicos.

    A releitura não reconstrói `CanonicalPayload`: o contrato do Passo 2.4 impede
    construir payload a partir de bytes arbitrários, e a persistência não é
    exceção. Quem precisar do conteúdo interpreta os bytes com o schema declarado.
    """

    operation_id: TypedId
    organization_id: OrganizationId
    device_reference: UniversalReference
    actor_reference: UniversalReference
    semantic_identity: str
    idempotency_key: str
    operation_type: str
    contract_version: int
    local_sequence: int
    intent_digest: str
    clock: DeviceClockReading
    payload_schema: str
    payload_version: int
    payload_canonical_bytes: bytes
    depends_on: tuple[TypedId, ...]
    evidence_references: tuple[UniversalReference, ...]
    correlation_id: TypedId | None


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _loaded(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


@dataclass(frozen=True, slots=True)
class TransactionalSynchronizationRepository:
    """Persistência transacional dos envelopes, resultados e lotes.

    O envelope e o resultado são gravados na mesma transação do efeito oficial:
    é essa fronteira que sustenta `ACEITA`. Resultado é append-only por tentativa,
    de modo que a retomada acrescenta histórico em vez de reescrever a decisão.
    """

    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalSynchronizationRepository exige transacao ativa.")

    def get_batch_manifest_digest(self, batch_id: TypedId) -> str | None:
        row = self.connection.execute(
            text(
                """
                SELECT manifest_digest
                FROM core_audit.synchronization_batches
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id.value},
        ).first()
        return None if row is None else str(row.manifest_digest)

    def register_batch(self, batch: SynchronizationBatch, received_at: datetime) -> int:
        row = self.connection.execute(
            text(
                """
                INSERT INTO core_audit.synchronization_batches (
                    batch_id,
                    record_owner_organization_id,
                    device_id,
                    batch_version,
                    manifest,
                    manifest_digest,
                    operation_count,
                    sequence_first,
                    sequence_last,
                    created_at_device,
                    first_received_at,
                    attempts,
                    state
                ) VALUES (
                    :batch_id,
                    :org_id,
                    :device_id,
                    :batch_version,
                    :manifest,
                    :manifest_digest,
                    :operation_count,
                    :sequence_first,
                    :sequence_last,
                    :created_at_device,
                    :received_at,
                    1,
                    :state
                )
                ON CONFLICT (batch_id) DO UPDATE SET
                    attempts = core_audit.synchronization_batches.attempts + 1
                RETURNING attempts
                """
            ),
            {
                "batch_id": batch.batch_id.value,
                "org_id": batch.organization_id.value,
                "device_id": batch.device_reference.target_id.value,
                "batch_version": batch.batch_version,
                "manifest": json.dumps([dict(entry.to_canonical()) for entry in batch.manifest]),
                "manifest_digest": batch.manifest_digest,
                "operation_count": batch.operation_count,
                "sequence_first": batch.sequence_boundary[0],
                "sequence_last": batch.sequence_boundary[1],
                "created_at_device": batch.created_at_device,
                "received_at": received_at,
                "state": SynchronizationBatchState.RECEBIDO.value,
            },
        ).first()
        assert row is not None
        return int(row.attempts)

    def save_operation(self, operation: OfflineOperation) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.offline_operations (
                    operation_id,
                    record_owner_organization_id,
                    device_id,
                    device_contract_version,
                    actor_entity_type,
                    actor_id,
                    actor_contract_version,
                    semantic_identity,
                    idempotency_key,
                    operation_type,
                    contract_version,
                    local_sequence,
                    intent_digest,
                    client_observed_at,
                    claimed_occurred_at,
                    timezone_name,
                    time_confidence,
                    monotonic_continuity_id,
                    monotonic_elapsed_ms,
                    last_server_contact_at,
                    payload_schema,
                    payload_version,
                    payload_canonical_bytes,
                    depends_on,
                    evidence_references,
                    correlation_id,
                    server_received_at
                ) VALUES (
                    :operation_id,
                    :org_id,
                    :device_id,
                    :device_contract_version,
                    :actor_entity_type,
                    :actor_id,
                    :actor_contract_version,
                    :semantic_identity,
                    :idempotency_key,
                    :operation_type,
                    :contract_version,
                    :local_sequence,
                    :intent_digest,
                    :client_observed_at,
                    :claimed_occurred_at,
                    :timezone_name,
                    :time_confidence,
                    :monotonic_continuity_id,
                    :monotonic_elapsed_ms,
                    :last_server_contact_at,
                    :payload_schema,
                    :payload_version,
                    :payload_canonical_bytes,
                    :depends_on,
                    :evidence_references,
                    :correlation_id,
                    NOW()
                )
                ON CONFLICT (operation_id) DO NOTHING
                """
            ),
            {
                "operation_id": operation.operation_id.value,
                "org_id": operation.organization_id.value,
                "device_id": operation.device_reference.target_id.value,
                "device_contract_version": operation.device_reference.contract_version,
                "actor_entity_type": operation.actor_reference.target_id.entity_type,
                "actor_id": operation.actor_reference.target_id.value,
                "actor_contract_version": operation.actor_reference.contract_version,
                "semantic_identity": operation.semantic_identity,
                "idempotency_key": operation.idempotency_key,
                "operation_type": operation.operation_type,
                "contract_version": operation.contract_version,
                "local_sequence": operation.local_sequence,
                "intent_digest": operation.intent_digest,
                "client_observed_at": operation.clock.client_observed_at,
                "claimed_occurred_at": operation.clock.claimed_occurred_at,
                "timezone_name": operation.clock.timezone_name,
                "time_confidence": operation.clock.confidence.value,
                "monotonic_continuity_id": operation.clock.monotonic_continuity_id,
                "monotonic_elapsed_ms": operation.clock.monotonic_elapsed_ms,
                "last_server_contact_at": operation.clock.last_server_contact_at,
                "payload_schema": operation.payload.schema,
                "payload_version": operation.payload.version,
                "payload_canonical_bytes": operation.payload.canonical_bytes,
                "depends_on": json.dumps([str(d.value) for d in operation.depends_on]),
                "evidence_references": json.dumps(
                    [reference_to_dict(r) for r in operation.evidence_references]
                ),
                "correlation_id": (
                    operation.correlation_id.value if operation.correlation_id else None
                ),
            },
        )

    def save_result(self, result: SynchronizationResult) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.synchronization_results (
                    operation_id,
                    attempt,
                    record_owner_organization_id,
                    batch_id,
                    status,
                    decided_at,
                    reason_codes,
                    produced_references,
                    conflict,
                    pending_dependencies,
                    reconciliation_deadline,
                    limitations
                ) VALUES (
                    :operation_id,
                    :attempt,
                    :org_id,
                    :batch_id,
                    :status,
                    :decided_at,
                    :reason_codes,
                    :produced_references,
                    :conflict,
                    :pending_dependencies,
                    :reconciliation_deadline,
                    :limitations
                )
                ON CONFLICT (operation_id, attempt) DO NOTHING
                """
            ),
            {
                "operation_id": result.operation_id.value,
                "attempt": result.attempt,
                "org_id": result.organization_id.value,
                "batch_id": result.batch_id.value,
                "status": result.status.value,
                "decided_at": result.decided_at,
                "reason_codes": json.dumps(list(result.reason_codes)),
                "produced_references": json.dumps(
                    [reference_to_dict(r) for r in result.produced_references]
                ),
                "conflict": (
                    None
                    if result.conflict is None
                    else json.dumps(_conflict_to_dict(result.conflict))
                ),
                "pending_dependencies": json.dumps(
                    [str(d.value) for d in result.pending_dependencies]
                ),
                "reconciliation_deadline": result.reconciliation_deadline,
                "limitations": json.dumps(list(result.limitations)),
            },
        )

    def save_batch_result(self, batch_result: SynchronizationBatchResult) -> None:
        self.connection.execute(
            text(
                """
                UPDATE core_audit.synchronization_batches SET
                    state = :state,
                    examined_count = :examined_count,
                    counts = :counts,
                    gaps = :gaps,
                    limitations = :limitations,
                    processed_at = :processed_at
                WHERE batch_id = :batch_id
                """
            ),
            {
                "batch_id": batch_result.batch_id.value,
                "state": batch_result.state.value,
                "examined_count": batch_result.examined_count,
                "counts": json.dumps(
                    {status.value: count for status, count in batch_result.counts.items()}
                ),
                "gaps": json.dumps([str(g.value) for g in batch_result.gaps]),
                "limitations": json.dumps(list(batch_result.limitations)),
                "processed_at": batch_result.processed_at,
            },
        )

    def get_result(self, operation_id: TypedId) -> SynchronizationResult | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    operation_id,
                    attempt,
                    record_owner_organization_id,
                    batch_id,
                    status,
                    decided_at,
                    reason_codes,
                    produced_references,
                    conflict,
                    pending_dependencies,
                    reconciliation_deadline,
                    limitations
                FROM core_audit.synchronization_results
                WHERE operation_id = :operation_id
                ORDER BY attempt DESC
                LIMIT 1
                """
            ),
            {"operation_id": operation_id.value},
        ).first()
        if row is None:
            return None

        decided_at = _aware(row.decided_at)
        assert decided_at is not None
        raw_conflict = _loaded(row.conflict)
        return SynchronizationResult(
            operation_id=TypedId(entity_type="offline_operation", value=row.operation_id),
            batch_id=TypedId(entity_type="synchronization_batch", value=row.batch_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            attempt=row.attempt,
            status=SynchronizationResultStatus(row.status),
            decided_at=decided_at,
            reason_codes=tuple(_loaded(row.reason_codes)),
            produced_references=tuple(
                reference
                for reference in (
                    reference_from_dict(item) for item in _loaded(row.produced_references)
                )
                if reference is not None
            ),
            conflict=(None if raw_conflict is None else _conflict_from_dict(raw_conflict)),
            pending_dependencies=tuple(
                TypedId(entity_type="offline_operation", value=UUID(value))
                for value in _loaded(row.pending_dependencies)
            ),
            reconciliation_deadline=_aware(row.reconciliation_deadline),
            limitations=tuple(_loaded(row.limitations)),
        )

    def find_by_idempotency_key(
        self, organization_id: OrganizationId, idempotency_key: str
    ) -> tuple[TypedId, str] | None:
        row = self.connection.execute(
            text(
                """
                SELECT operation_id, intent_digest
                FROM core_audit.offline_operations
                WHERE record_owner_organization_id = :org_id
                  AND idempotency_key = :idempotency_key
                ORDER BY server_received_at ASC, operation_id ASC
                LIMIT 1
                """
            ),
            {"org_id": organization_id.value, "idempotency_key": idempotency_key},
        ).first()
        if row is None:
            return None
        return (
            TypedId(entity_type="offline_operation", value=row.operation_id),
            str(row.intent_digest),
        )

    def get_operation(self, operation_id: TypedId) -> StoredOfflineOperation | None:
        row = self.connection.execute(
            text(
                """
                SELECT *
                FROM core_audit.offline_operations
                WHERE operation_id = :operation_id
                """
            ),
            {"operation_id": operation_id.value},
        ).first()
        if row is None:
            return None

        organization_id = OrganizationId(row.record_owner_organization_id)
        client_observed_at = _aware(row.client_observed_at)
        claimed_occurred_at = _aware(row.claimed_occurred_at)
        assert client_observed_at is not None
        assert claimed_occurred_at is not None

        return StoredOfflineOperation(
            operation_id=TypedId(entity_type="offline_operation", value=row.operation_id),
            organization_id=organization_id,
            device_reference=UniversalReference(
                target_id=TypedId(entity_type="device", value=row.device_id),
                organization_id=organization_id,
                contract_version=row.device_contract_version,
            ),
            actor_reference=UniversalReference(
                target_id=TypedId(entity_type=row.actor_entity_type, value=row.actor_id),
                organization_id=organization_id,
                contract_version=row.actor_contract_version,
            ),
            semantic_identity=row.semantic_identity,
            idempotency_key=row.idempotency_key,
            operation_type=row.operation_type,
            contract_version=row.contract_version,
            local_sequence=row.local_sequence,
            intent_digest=row.intent_digest,
            clock=DeviceClockReading(
                client_observed_at=client_observed_at,
                claimed_occurred_at=claimed_occurred_at,
                timezone_name=row.timezone_name,
                confidence=TimeConfidenceLevel(row.time_confidence),
                monotonic_continuity_id=row.monotonic_continuity_id,
                monotonic_elapsed_ms=row.monotonic_elapsed_ms,
                last_server_contact_at=_aware(row.last_server_contact_at),
            ),
            payload_schema=row.payload_schema,
            payload_version=row.payload_version,
            payload_canonical_bytes=bytes(row.payload_canonical_bytes),
            depends_on=tuple(
                TypedId(entity_type="offline_operation", value=UUID(value))
                for value in _loaded(row.depends_on)
            ),
            evidence_references=tuple(
                reference
                for reference in (
                    reference_from_dict(item) for item in _loaded(row.evidence_references)
                )
                if reference is not None
            ),
            correlation_id=(
                None
                if row.correlation_id is None
                else TypedId(entity_type="correlation", value=row.correlation_id)
            ),
        )

    def get_batch_manifest(self, batch_id: TypedId) -> tuple[OperationManifestEntry, ...]:
        row = self.connection.execute(
            text(
                """
                SELECT manifest
                FROM core_audit.synchronization_batches
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id.value},
        ).first()
        if row is None:
            return ()
        return tuple(
            OperationManifestEntry(
                operation_id=TypedId(
                    entity_type="offline_operation", value=UUID(entry["operation_id"])
                ),
                semantic_identity=entry["semantic_identity"],
                intent_digest=entry["intent_digest"],
                position=entry["position"],
                depends_on=tuple(
                    TypedId(entity_type="offline_operation", value=UUID(value))
                    for value in entry["depends_on"]
                ),
            )
            for entry in _loaded(row.manifest)
        )


def _conflict_to_dict(conflict: SynchronizationConflict) -> dict[str, Any]:
    return {
        "operation_id": str(conflict.operation_id.value),
        "reason": conflict.reason.value,
        "observed_state": conflict.observed_state,
        "detected_at": conflict.detected_at.isoformat(),
        "alternatives": list(conflict.alternatives),
        "responsible_actor_reference": (
            None
            if conflict.responsible_actor_reference is None
            else reference_to_dict(conflict.responsible_actor_reference)
        ),
    }


def _conflict_from_dict(data: dict[str, Any]) -> SynchronizationConflict:
    return SynchronizationConflict(
        operation_id=TypedId(entity_type="offline_operation", value=UUID(data["operation_id"])),
        reason=SynchronizationConflictReason(data["reason"]),
        observed_state=data["observed_state"],
        detected_at=datetime.fromisoformat(data["detected_at"]),
        alternatives=tuple(data.get("alternatives", [])),
        responsible_actor_reference=reference_from_dict(data.get("responsible_actor_reference")),
    )
