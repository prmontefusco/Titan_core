"""Handler de eventos de inventário para recalcular `WAITING_MATERIAL`.

Este módulo é a ponte application-only entre eventos já registrados no Core e o
`MaterialReadinessRecalculator`. Ele não é worker, não consome fila e não abre
transação; a composição futura decide quando chamá-lo.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_application.material_readiness_recalculator import (
    MaterialReadinessRecalculation,
    MaterialReadinessRecalculator,
)
from packages.asset_domain.events import (
    INVENTORY_STOCK_CONSUMED,
    INVENTORY_STOCK_RESERVATION_RELEASED,
    INVENTORY_STOCK_RESERVED,
    INVENTORY_TRANSFER_RECEIVED,
)
from packages.core_domain.events import CanonicalPayload, DomainEvent
from packages.shared_kernel import TypedId


class MaterialReadinessEventHandlingOutcome(StrEnum):
    HANDLED = "HANDLED"
    IGNORED = "IGNORED"


@dataclass(frozen=True, slots=True)
class MaterialReadinessEventHandlingResult:
    outcome: MaterialReadinessEventHandlingOutcome
    recalculation: MaterialReadinessRecalculation | None = None


def _payload_data(payload: CanonicalPayload) -> dict[str, Any]:
    decoded = json.loads(payload.canonical_bytes.decode("utf-8"))
    normalized_envelope = decoded[1]
    envelope = _denormalize(normalized_envelope)
    data = envelope["data"]
    if not isinstance(data, dict):
        raise TypeError("payload.data deve ser mapa.")
    return data


def _denormalize(value: Any) -> Any:
    tag = value[0]
    payload = value[1] if len(value) > 1 else None
    if tag == "map":
        if not isinstance(payload, list):
            raise TypeError("Payload canônico 'map' deve conter lista de pares.")
        return {key: _denormalize(item) for key, item in payload}
    if tag == "list":
        if not isinstance(payload, list):
            raise TypeError("Payload canônico 'list' deve conter lista.")
        return [_denormalize(item) for item in payload]
    if tag in {"string", "integer", "decimal", "datetime"}:
        return payload
    if tag == "boolean":
        return payload == "true"
    if tag == "null":
        return None
    raise ValueError(f"Tag canônica desconhecida: {tag!r}.")


def _typed_id_from_payload(data: dict[str, Any], key: str, *, entity_type: str) -> TypedId:
    raw_value = data[key]
    if not isinstance(raw_value, str):
        raise TypeError(f"{key} deve ser string UUID no payload.")
    return TypedId(entity_type=entity_type, value=UUID(raw_value))


def _context_from_event(event: DomainEvent) -> AssetOperationContext:
    return AssetOperationContext(
        organization_id=event.organization_id,
        actor_reference=event.actor_reference,
        source_reference=event.source_reference,
        correlation_id=event.correlation_id,
    )


@dataclass(frozen=True, slots=True)
class MaterialReadinessEventHandler:
    recalculator: MaterialReadinessRecalculator

    def handle(self, event: DomainEvent) -> MaterialReadinessEventHandlingResult:
        if event.event_type not in _HANDLED_EVENT_TYPES:
            return MaterialReadinessEventHandlingResult(
                outcome=MaterialReadinessEventHandlingOutcome.IGNORED
            )
        data = _payload_data(event.payload)
        context = _context_from_event(event)
        if event.event_type == INVENTORY_TRANSFER_RECEIVED:
            recalculation = self.recalculator.recalculate_for_transfer(
                context,
                _typed_id_from_payload(data, "transfer_id", entity_type="stock_transfer"),
                occurred_at=event.timestamps.occurred_at,
            )
        else:
            recalculation = self.recalculator.recalculate_for_reservation(
                context,
                _typed_id_from_payload(data, "reservation_id", entity_type="stock_reservation"),
                occurred_at=event.timestamps.occurred_at,
            )
        return MaterialReadinessEventHandlingResult(
            outcome=MaterialReadinessEventHandlingOutcome.HANDLED,
            recalculation=recalculation,
        )


_HANDLED_EVENT_TYPES = frozenset(
    {
        INVENTORY_STOCK_RESERVED,
        INVENTORY_STOCK_RESERVATION_RELEASED,
        INVENTORY_STOCK_CONSUMED,
        INVENTORY_TRANSFER_RECEIVED,
    }
)
