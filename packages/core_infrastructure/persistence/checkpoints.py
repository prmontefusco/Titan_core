"""Persistência append-only dos checkpoints de integridade."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.core_integrity import CheckpointEventReference, IntegrityCheckpoint
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

integrity_checkpoints_table = Table(
    "integrity_checkpoints",
    organization_metadata,
    Column("checkpoint_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "record_owner_organization_id",
        UUID(as_uuid=True),
        ForeignKey(
            "core_identity.organizations.organization_id",
            name="fk_integrity_checkpoints_owner",
        ),
        nullable=False,
    ),
    Column("aggregate_type", String(100), nullable=False),
    Column("aggregate_id", UUID(as_uuid=True), nullable=False),
    Column("aggregate_contract_version", Integer, nullable=False),
    Column("first_sequence", Integer, nullable=False),
    Column("last_sequence", Integer, nullable=False),
    Column("record_count", Integer, nullable=False),
    Column("initial_hash", LargeBinary, nullable=False),
    Column("final_hash", LargeBinary, nullable=False),
    Column("hash_algorithm", String(30), nullable=False),
    Column("event_chain_profile", String(100), nullable=False),
    Column("event_chain_profile_version", Integer, nullable=False),
    Column("checkpoint_profile", String(100), nullable=False),
    Column("checkpoint_profile_version", Integer, nullable=False),
    Column("canonical_serialization_version", String(50), nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("producer_type", String(100), nullable=False),
    Column("producer_id", UUID(as_uuid=True), nullable=False),
    Column("producer_organization_id", UUID(as_uuid=True), nullable=True),
    Column("producer_contract_version", Integer, nullable=False),
    Column("correlation_id", UUID(as_uuid=True), nullable=False),
    Column("causation_id", UUID(as_uuid=True), nullable=True),
    Column("checkpoint_canonical_bytes", LargeBinary, nullable=False),
    Column("checkpoint_digest", LargeBinary, nullable=False),
    CheckConstraint("first_sequence = 1", name="ck_checkpoints_first_sequence"),
    CheckConstraint("record_count = last_sequence", name="ck_checkpoints_count"),
    CheckConstraint("octet_length(initial_hash) = 32", name="ck_checkpoints_initial_hash"),
    CheckConstraint("octet_length(final_hash) = 32", name="ck_checkpoints_final_hash"),
    CheckConstraint("octet_length(checkpoint_digest) = 32", name="ck_checkpoints_digest"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

checkpoint_events_table = Table(
    "integrity_checkpoint_events",
    organization_metadata,
    Column("checkpoint_id", UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("event_id", UUID(as_uuid=True), nullable=False),
    Column("event_hash", LargeBinary, nullable=False),
    ForeignKeyConstraint(
        ["checkpoint_id"],
        ["core_audit.integrity_checkpoints.checkpoint_id"],
        name="fk_checkpoint_events_checkpoint",
    ),
    ForeignKeyConstraint(
        ["event_id"],
        ["core_audit.domain_event_integrity.event_id"],
        name="fk_checkpoint_events_event",
    ),
    CheckConstraint("sequence > 0", name="ck_checkpoint_events_sequence"),
    CheckConstraint("octet_length(event_hash) = 32", name="ck_checkpoint_events_hash"),
    UniqueConstraint("checkpoint_id", "sequence", name="uq_checkpoint_events_sequence"),
    UniqueConstraint("checkpoint_id", "event_id", name="uq_checkpoint_events_event"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class IntegrityCheckpointRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("IntegrityCheckpointRepository exige transação ativa.")

    def add(self, checkpoint: IntegrityCheckpoint) -> None:
        if not isinstance(checkpoint, IntegrityCheckpoint):
            raise TypeError("checkpoint deve ser IntegrityCheckpoint.")
        aggregate = checkpoint.aggregate_reference
        producer = checkpoint.producer_reference
        self.connection.execute(
            insert(integrity_checkpoints_table).values(
                checkpoint_id=checkpoint.checkpoint_id.value,
                record_owner_organization_id=checkpoint.organization_id.value,
                aggregate_type=aggregate.target_id.entity_type,
                aggregate_id=aggregate.target_id.value,
                aggregate_contract_version=aggregate.contract_version,
                first_sequence=checkpoint.first_sequence,
                last_sequence=checkpoint.last_sequence,
                record_count=checkpoint.record_count,
                initial_hash=checkpoint.initial_hash,
                final_hash=checkpoint.final_hash,
                hash_algorithm=checkpoint.hash_algorithm,
                event_chain_profile=checkpoint.event_chain_profile,
                event_chain_profile_version=checkpoint.event_chain_profile_version,
                checkpoint_profile=checkpoint.checkpoint_profile,
                checkpoint_profile_version=checkpoint.checkpoint_profile_version,
                canonical_serialization_version=checkpoint.canonical_serialization_version,
                observed_at=checkpoint.observed_at,
                producer_type=producer.target_id.entity_type,
                producer_id=producer.target_id.value,
                producer_organization_id=(
                    None if producer.organization_id is None else producer.organization_id.value
                ),
                producer_contract_version=producer.contract_version,
                correlation_id=checkpoint.correlation_id.value,
                causation_id=(
                    None if checkpoint.causation_id is None else checkpoint.causation_id.value
                ),
                checkpoint_canonical_bytes=checkpoint.checkpoint_canonical_bytes,
                checkpoint_digest=checkpoint.checkpoint_digest,
            )
        )
        self.connection.execute(
            insert(checkpoint_events_table),
            [
                {
                    "checkpoint_id": checkpoint.checkpoint_id.value,
                    "record_owner_organization_id": checkpoint.organization_id.value,
                    "sequence": reference.sequence,
                    "event_id": reference.event_id.value,
                    "event_hash": reference.event_hash,
                }
                for reference in checkpoint.event_references
            ],
        )

    def get(self, checkpoint_id: TypedId) -> IntegrityCheckpoint | None:
        if (
            not isinstance(checkpoint_id, TypedId)
            or checkpoint_id.entity_type != "integrity_checkpoint"
        ):
            raise ValueError("checkpoint_id deve possuir tipo lógico 'integrity_checkpoint'.")
        row = self.connection.execute(
            select(integrity_checkpoints_table).where(
                integrity_checkpoints_table.c.checkpoint_id == checkpoint_id.value
            )
        ).one_or_none()
        if row is None:
            return None
        event_rows = self.connection.execute(
            select(checkpoint_events_table)
            .where(checkpoint_events_table.c.checkpoint_id == checkpoint_id.value)
            .order_by(checkpoint_events_table.c.sequence)
        ).all()
        return _from_rows(row, event_rows)


def _from_rows(row: Row[Any], event_rows: Sequence[Row[Any]]) -> IntegrityCheckpoint:
    organization_id = OrganizationId(row.record_owner_organization_id)
    return IntegrityCheckpoint(
        checkpoint_id=TypedId("integrity_checkpoint", row.checkpoint_id),
        organization_id=organization_id,
        aggregate_reference=UniversalReference(
            TypedId(row.aggregate_type, row.aggregate_id),
            organization_id,
            row.aggregate_contract_version,
        ),
        first_sequence=row.first_sequence,
        last_sequence=row.last_sequence,
        record_count=row.record_count,
        event_references=tuple(
            CheckpointEventReference(
                event_id=TypedId("domain_event", item.event_id),
                sequence=item.sequence,
                event_hash=bytes(item.event_hash),
            )
            for item in event_rows
        ),
        initial_hash=bytes(row.initial_hash),
        final_hash=bytes(row.final_hash),
        hash_algorithm=row.hash_algorithm,
        event_chain_profile=row.event_chain_profile,
        event_chain_profile_version=row.event_chain_profile_version,
        checkpoint_profile=row.checkpoint_profile,
        checkpoint_profile_version=row.checkpoint_profile_version,
        canonical_serialization_version=row.canonical_serialization_version,
        observed_at=row.observed_at,
        producer_reference=UniversalReference(
            TypedId(row.producer_type, row.producer_id),
            (
                None
                if row.producer_organization_id is None
                else OrganizationId(row.producer_organization_id)
            ),
            row.producer_contract_version,
        ),
        correlation_id=TypedId("correlation", row.correlation_id),
        causation_id=(
            None if row.causation_id is None else TypedId("domain_event", row.causation_id)
        ),
        checkpoint_canonical_bytes=bytes(row.checkpoint_canonical_bytes),
        checkpoint_digest=bytes(row.checkpoint_digest),
    )
