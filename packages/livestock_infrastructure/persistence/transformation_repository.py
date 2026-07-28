"""Persistência de TransformationEvent e TraceableItem (ADR-0046, Passo 11.2).

`inputs`/`outputs` são guardados como JSONB dentro da própria linha do evento —
não uma tabela de participantes à parte — porque a ADR já decidiu que o evento
é a fonte autoritativa e a única forma que reconstrói um `TransformationEvent`.
Uma tabela normalizada de participantes criaria uma segunda leitura possível do
mesmo fato, que é exatamente o que a ADR pediu para evitar (item 5/13).
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.transformation_service import (
    TraceableItemRepositoryPort,
    TransformationEventRepositoryPort,
)
from packages.livestock_domain.transformation import (
    BalanceResult,
    BalanceStatus,
    ConsumptionMode,
    ParticipantRole,
    ProcessType,
    TraceableItem,
    TraceableItemType,
    TransformationBalance,
    TransformationEvent,
    TransformationParticipant,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

transformation_events_table = Table(
    "transformation_events",
    livestock_metadata,
    Column("event_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("process_type", String(40), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("facility_reference", JSONB, nullable=False),
    Column("operator_reference", JSONB, nullable=True),
    Column("source_artifact_references", JSONB, nullable=False, server_default="[]"),
    Column("inputs", JSONB, nullable=False),
    Column("outputs", JSONB, nullable=False),
    Column("balance", JSONB, nullable=True),
    Column("evidence_references", JSONB, nullable=False, server_default="[]"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("corrects_transformation_id", PG_UUID(as_uuid=True), nullable=True),
    Column("correction_reason", Text, nullable=True),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_transformation_events_organization",
    ),
    ForeignKeyConstraint(
        ["corrects_transformation_id"],
        [f"{CORE_AUDIT_SCHEMA}.transformation_events.event_id"],
        name="fk_transformation_events_corrects",
    ),
    UniqueConstraint(
        "corrects_transformation_id",
        name="uq_transformation_events_corrects_transformation_id",
    ),
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    schema=CORE_AUDIT_SCHEMA,
)

traceable_items_table = Table(
    "traceable_items",
    livestock_metadata,
    Column("item_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("item_type", String(40), nullable=False),
    Column("created_by_transformation_id", PG_UUID(as_uuid=True), nullable=True),
    Column("label", String(255), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_traceable_items_organization",
    ),
    ForeignKeyConstraint(
        ["created_by_transformation_id"],
        [f"{CORE_AUDIT_SCHEMA}.transformation_events.event_id"],
        name="fk_traceable_items_transformation",
    ),
    Index(
        "ix_traceable_items_transformation",
        "record_owner_organization_id",
        "created_by_transformation_id",
    ),
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    schema=CORE_AUDIT_SCHEMA,
)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _decimal_to_str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _decimal_from_str(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _participant_to_dict(participant: TransformationParticipant) -> dict[str, Any]:
    return {
        "subject_reference": reference_to_dict(participant.subject_reference),
        "role": participant.role.value,
        "quantity": _decimal_to_str(participant.quantity),
        "unit": participant.unit,
        "measurement_basis": participant.measurement_basis,
        "consumption_mode": (
            participant.consumption_mode.value if participant.consumption_mode is not None else None
        ),
        "lot_or_batch_reference": reference_to_dict(participant.lot_or_batch_reference),
    }


def _balance_to_dict(balance: TransformationBalance | None) -> dict[str, Any] | None:
    if balance is None:
        return None
    return {
        "status": balance.status.value,
        "result": balance.result.value,
        "measurement_basis": balance.measurement_basis,
        "input_total": _decimal_to_str(balance.input_total),
        "output_total": _decimal_to_str(balance.output_total),
        "declared_loss": _decimal_to_str(balance.declared_loss),
        "unaccounted_quantity": _decimal_to_str(balance.unaccounted_quantity),
        "tolerance": _decimal_to_str(balance.tolerance),
        "reasons": list(balance.reasons),
        "evidence_references": [reference_to_dict(r) for r in balance.evidence_references],
    }


def _balance_from_dict(data: dict[str, Any] | None) -> TransformationBalance | None:
    if data is None:
        return None
    return TransformationBalance(
        status=BalanceStatus(data["status"]),
        result=BalanceResult(data["result"]),
        measurement_basis=data.get("measurement_basis"),
        input_total=_decimal_from_str(data.get("input_total")),
        output_total=_decimal_from_str(data.get("output_total")),
        declared_loss=_decimal_from_str(data.get("declared_loss")),
        unaccounted_quantity=_decimal_from_str(data.get("unaccounted_quantity")),
        tolerance=_decimal_from_str(data.get("tolerance")),
        reasons=tuple(data.get("reasons", [])),
        evidence_references=tuple(
            ref
            for ref in (reference_from_dict(item) for item in data.get("evidence_references", []))
            if ref is not None
        ),
    )


def _participant_from_dict(data: dict[str, Any]) -> TransformationParticipant:
    subject = reference_from_dict(data["subject_reference"])
    if subject is None:
        raise ValueError("Participante persistido sem subject_reference.")
    consumption_mode_raw = data.get("consumption_mode")
    return TransformationParticipant(
        subject_reference=subject,
        role=ParticipantRole(data["role"]),
        quantity=_decimal_from_str(data.get("quantity")),
        unit=data.get("unit", ""),
        measurement_basis=data.get("measurement_basis"),
        consumption_mode=(
            ConsumptionMode(consumption_mode_raw) if consumption_mode_raw is not None else None
        ),
        lot_or_batch_reference=reference_from_dict(data.get("lot_or_batch_reference")),
    )


@dataclass(frozen=True, slots=True)
class TransactionalTransformationEventRepository(TransformationEventRepositoryPort):
    connection: Connection

    def save(self, event: TransformationEvent) -> None:
        self.connection.execute(
            insert(transformation_events_table).values(
                event_id=event.event_id.value,
                record_owner_organization_id=event.organization_id.value,
                process_type=event.process_type.value,
                occurred_at=event.occurred_at,
                facility_reference=json.dumps(reference_to_dict(event.facility_reference)),
                operator_reference=(
                    json.dumps(reference_to_dict(event.operator_reference))
                    if event.operator_reference is not None
                    else None
                ),
                source_artifact_references=json.dumps(
                    [reference_to_dict(r) for r in event.source_artifact_references]
                ),
                inputs=json.dumps([_participant_to_dict(p) for p in event.inputs]),
                outputs=json.dumps([_participant_to_dict(p) for p in event.outputs]),
                balance=(
                    json.dumps(_balance_to_dict(event.balance))
                    if event.balance is not None
                    else None
                ),
                evidence_references=json.dumps(
                    [reference_to_dict(r) for r in event.evidence_references]
                ),
                created_at=event.created_at,
                corrects_transformation_id=(
                    event.corrects_transformation_id.value
                    if event.corrects_transformation_id is not None
                    else None
                ),
                correction_reason=event.correction_reason,
            )
        )

    def get_by_id(self, event_id: TypedId) -> TransformationEvent | None:
        row = self.connection.execute(
            select(transformation_events_table).where(
                transformation_events_table.c.event_id == event_id.value
            )
        ).one_or_none()
        return None if row is None else self._map(row)

    def get_correction_of(self, event_id: TypedId) -> TransformationEvent | None:
        row = self.connection.execute(
            select(transformation_events_table).where(
                transformation_events_table.c.corrects_transformation_id == event_id.value
            )
        ).one_or_none()
        return None if row is None else self._map(row)

    def _map(self, row: Row[Any]) -> TransformationEvent:
        def _load(bruto: Any) -> Any:
            return json.loads(bruto) if isinstance(bruto, str) else bruto

        facility = reference_from_dict(_load(row.facility_reference))
        if facility is None:
            raise ValueError("transformation_events.facility_reference corrompido.")
        operator_raw = _load(row.operator_reference)
        source_artifacts_raw = _load(row.source_artifact_references) or []
        evidence_raw = _load(row.evidence_references) or []

        return TransformationEvent(
            event_id=TypedId(entity_type="transformation_event", value=row.event_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            process_type=ProcessType(row.process_type),
            occurred_at=_aware(row.occurred_at),
            facility_reference=facility,
            operator_reference=reference_from_dict(operator_raw) if operator_raw else None,
            source_artifact_references=tuple(
                ref
                for ref in (reference_from_dict(item) for item in source_artifacts_raw)
                if ref is not None
            ),
            inputs=tuple(_participant_from_dict(item) for item in _load(row.inputs)),
            outputs=tuple(_participant_from_dict(item) for item in _load(row.outputs)),
            created_at=_aware(row.created_at),
            balance=_balance_from_dict(_load(row.balance)),
            evidence_references=tuple(
                ref
                for ref in (reference_from_dict(item) for item in evidence_raw)
                if ref is not None
            ),
            corrects_transformation_id=(
                TypedId(entity_type="transformation_event", value=row.corrects_transformation_id)
                if row.corrects_transformation_id is not None
                else None
            ),
            correction_reason=row.correction_reason,
        )


@dataclass(frozen=True, slots=True)
class TransactionalTraceableItemRepository(TraceableItemRepositoryPort):
    connection: Connection

    def save(self, item: TraceableItem) -> None:
        self.connection.execute(
            insert(traceable_items_table).values(
                item_id=item.item_id.value,
                record_owner_organization_id=item.organization_id.value,
                item_type=item.item_type.value,
                created_by_transformation_id=(
                    item.created_by_transformation_id.value
                    if item.created_by_transformation_id is not None
                    else None
                ),
                label=item.label,
                created_at=item.created_at,
            )
        )

    def get_by_id(self, item_id: TypedId) -> TraceableItem | None:
        row = self.connection.execute(
            select(traceable_items_table).where(traceable_items_table.c.item_id == item_id.value)
        ).one_or_none()
        return None if row is None else self._map(row)

    def _map(self, row: Row[Any]) -> TraceableItem:
        return TraceableItem(
            item_id=TypedId(entity_type="traceable_item", value=row.item_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            item_type=TraceableItemType(row.item_type),
            created_by_transformation_id=(
                TypedId(entity_type="transformation_event", value=row.created_by_transformation_id)
                if row.created_by_transformation_id is not None
                else None
            ),
            label=row.label,
            created_at=_aware(row.created_at),
        )
