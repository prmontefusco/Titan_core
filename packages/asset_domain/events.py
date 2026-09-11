"""Contrato de eventos de domínio da vertical Titan Asset (A2, primeiro slice).

Mesmo padrão de `packages/livestock_domain/events.py`: um evento da vertical é um
`DomainEvent` do Core (não subclasse) — `event_type` + payload canônico. Namespace
`asset.` (`docs/asset/08_DOMAIN_EVENTS.md`; manifesto `docs/architecture/verticals.toml`).

Este arquivo cobre `Vehicle` (`vehicle.py`), `Part`/`InterchangeabilityGroup`
(`part.py`) e `Applicability` (`applicability.py`). Os demais eventos de
`08_DOMAIN_EVENTS.md` (Inventory/CustomerSite/sustainment) entram junto dos
respectivos agregados.
"""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from packages.core_domain.events import CanonicalPayload
from packages.shared_kernel import TypedId
from packages.shared_kernel.serialization import CanonicalValue

VEHICLE_REGISTERED = "asset.vehicle.registered"
VEHICLE_CONFIGURATION_BASELINE_SET = "asset.vehicle.configuration_baseline_set"
VEHICLE_METER_READING_RECORDED = "asset.vehicle.meter_reading_recorded"
VEHICLE_METER_READING_CORRECTED = "asset.vehicle.meter_reading_corrected"
VEHICLE_LIFECYCLE_STATE_CHANGED = "asset.vehicle.lifecycle_state_changed"
VEHICLE_RETURNED_TO_SERVICE = "asset.vehicle.returned_to_service"

ASSET_VEHICLE_EVENT_TYPES = frozenset(
    {
        VEHICLE_REGISTERED,
        VEHICLE_CONFIGURATION_BASELINE_SET,
        VEHICLE_METER_READING_RECORDED,
        VEHICLE_METER_READING_CORRECTED,
        VEHICLE_LIFECYCLE_STATE_CHANGED,
        VEHICLE_RETURNED_TO_SERVICE,
    }
)

CONFIGURATION_BASELINE_PUBLISHED = "asset.configuration.baseline_published"
CONFIGURATION_BASELINE_SUPERSEDED = "asset.configuration.baseline_superseded"

ASSET_CONFIGURATION_EVENT_TYPES = frozenset(
    {
        CONFIGURATION_BASELINE_PUBLISHED,
        CONFIGURATION_BASELINE_SUPERSEDED,
    }
)

SITE_REGISTERED = "asset.site.registered"

ASSET_SITE_EVENT_TYPES = frozenset({SITE_REGISTERED})

SUSTAINMENT_CONTRACT_REGISTERED = "asset.sustainment.contract_registered"
SUSTAINMENT_CONTRACT_VERSION_ISSUED = "asset.sustainment.contract_version_issued"

ASSET_SUSTAINMENT_CONTRACT_EVENT_TYPES = frozenset(
    {
        SUSTAINMENT_CONTRACT_REGISTERED,
        SUSTAINMENT_CONTRACT_VERSION_ISSUED,
    }
)

PART_REGISTERED = "asset.part.registered"
PART_REVISION_ADDED = "asset.part.revision_added"
PART_REVISION_SUPERSEDED = "asset.part.revision_superseded"
PART_LIFECYCLE_STATE_CHANGED = "asset.part.lifecycle_state_changed"
PART_INTERCHANGEABILITY_GROUP_CHANGED = "asset.part.interchangeability_group_changed"
APPLICABILITY_ASSERTED = "asset.applicability.asserted"
APPLICABILITY_WITHDRAWN = "asset.applicability.withdrawn"

ASSET_PART_EVENT_TYPES = frozenset(
    {
        PART_REGISTERED,
        PART_REVISION_ADDED,
        PART_REVISION_SUPERSEDED,
        PART_LIFECYCLE_STATE_CHANGED,
        PART_INTERCHANGEABILITY_GROUP_CHANGED,
        APPLICABILITY_ASSERTED,
        APPLICABILITY_WITHDRAWN,
    }
)

INVENTORY_STOCK_POSITION_OPENED = "asset.inventory.stock_position_opened"
INVENTORY_STOCK_ADJUSTED = "asset.inventory.stock_adjusted"
INVENTORY_STOCK_RESERVED = "asset.inventory.stock_reserved"
INVENTORY_STOCK_RESERVATION_ALLOCATED = "asset.inventory.stock_reservation_allocated"
INVENTORY_STOCK_RESERVATION_RELEASED = "asset.inventory.stock_reservation_released"
INVENTORY_STOCK_CONSUMED = "asset.inventory.stock_consumed"
INVENTORY_ALLOCATION_DECIDED = "asset.inventory.allocation_decided"
INVENTORY_TRANSFER_REQUESTED = "asset.inventory.transfer_requested"
INVENTORY_TRANSFER_DISPATCHED = "asset.inventory.transfer_dispatched"
INVENTORY_TRANSFER_RECEIVED = "asset.inventory.transfer_received"

ASSET_INVENTORY_EVENT_TYPES = frozenset(
    {
        INVENTORY_STOCK_POSITION_OPENED,
        INVENTORY_STOCK_ADJUSTED,
        INVENTORY_STOCK_RESERVED,
        INVENTORY_STOCK_RESERVATION_ALLOCATED,
        INVENTORY_STOCK_RESERVATION_RELEASED,
        INVENTORY_STOCK_CONSUMED,
        INVENTORY_ALLOCATION_DECIDED,
        INVENTORY_TRANSFER_REQUESTED,
        INVENTORY_TRANSFER_DISPATCHED,
        INVENTORY_TRANSFER_RECEIVED,
    }
)

PAYLOAD_VERSION = 1


def _payload(event_type: str, value: Mapping[str, CanonicalValue]) -> CanonicalPayload:
    schema = f"{event_type.replace('.', '_')}_payload"
    return CanonicalPayload.from_mapping(schema=schema, version=PAYLOAD_VERSION, value=value)


def _id(value: TypedId) -> str:
    return str(value.value)


def _optional_id(value: TypedId | None) -> str | None:
    return None if value is None else _id(value)


def _decimal(value: Decimal | float | None) -> Decimal | None:
    """O serializador canônico recusa float; área/quantidade viram Decimal."""
    return None if value is None else Decimal(str(value))


def _ids(values: tuple[TypedId, ...]) -> list[str]:
    return [_id(value) for value in values]


def vehicle_registered_payload(
    *,
    vehicle_id: TypedId,
    model_ref: TypedId,
    variant_ref: TypedId | None,
    serial_number: str,
    chassis: str | None,
    fleet_number: str | None,
    site_ref: TypedId | None,
    ownership: str,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_REGISTERED,
        {
            "chassis": chassis,
            "fleet_number": fleet_number,
            "model_ref": _id(model_ref),
            "ownership": ownership,
            "serial_number": serial_number,
            "site_ref": _optional_id(site_ref),
            "variant_ref": _optional_id(variant_ref),
            "vehicle_id": _id(vehicle_id),
        },
    )


def vehicle_configuration_baseline_set_payload(
    *,
    vehicle_id: TypedId,
    baseline_ref: TypedId,
    valid_from: datetime,
    previous_baseline_ref: TypedId | None,
    previous_valid_from: datetime | None,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_CONFIGURATION_BASELINE_SET,
        {
            "baseline_ref": _id(baseline_ref),
            "previous_baseline_ref": _optional_id(previous_baseline_ref),
            "previous_valid_from": previous_valid_from,
            "valid_from": valid_from,
            "vehicle_id": _id(vehicle_id),
        },
    )


def vehicle_meter_reading_recorded_payload(
    *,
    vehicle_id: TypedId,
    reading_id: TypedId,
    kind: str,
    value: Decimal,
    observed_at: datetime,
    source: str,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_METER_READING_RECORDED,
        {
            "kind": kind,
            "observed_at": observed_at,
            "reading_id": _id(reading_id),
            "source": source,
            "value": _decimal(value),
            "vehicle_id": _id(vehicle_id),
        },
    )


def vehicle_meter_reading_corrected_payload(
    *,
    vehicle_id: TypedId,
    correction_id: TypedId,
    original_reading_id: TypedId,
    corrected_value: Decimal,
    reason: str,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_METER_READING_CORRECTED,
        {
            "corrected_value": _decimal(corrected_value),
            "correction_id": _id(correction_id),
            "original_reading_id": _id(original_reading_id),
            "reason": reason,
            "vehicle_id": _id(vehicle_id),
        },
    )


def vehicle_lifecycle_state_changed_payload(
    *,
    vehicle_id: TypedId,
    from_state: str,
    to_state: str,
    reason: str | None,
    work_order_ref: TypedId | None,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_LIFECYCLE_STATE_CHANGED,
        {
            "from_state": from_state,
            "reason": reason,
            "to_state": to_state,
            "vehicle_id": _id(vehicle_id),
            "work_order_ref": _optional_id(work_order_ref),
        },
    )


def vehicle_returned_to_service_payload(
    *,
    vehicle_id: TypedId,
    work_order_ref: TypedId,
    validation_ref: TypedId,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_RETURNED_TO_SERVICE,
        {
            "validation_ref": _id(validation_ref),
            "vehicle_id": _id(vehicle_id),
            "work_order_ref": _id(work_order_ref),
        },
    )


def configuration_baseline_published_payload(
    *,
    baseline_id: TypedId,
    model_ref: TypedId,
    variant_ref: TypedId | None,
    revision_number: int,
    supersedes_ref: TypedId | None,
    valid_from: datetime,
) -> CanonicalPayload:
    return _payload(
        CONFIGURATION_BASELINE_PUBLISHED,
        {
            "baseline_id": _id(baseline_id),
            "model_ref": _id(model_ref),
            "revision_number": revision_number,
            "supersedes_ref": _optional_id(supersedes_ref),
            "valid_from": valid_from,
            "variant_ref": _optional_id(variant_ref),
        },
    )


def configuration_baseline_superseded_payload(
    *,
    baseline_id: TypedId,
    superseded_by_ref: TypedId,
    reason: str,
) -> CanonicalPayload:
    return _payload(
        CONFIGURATION_BASELINE_SUPERSEDED,
        {
            "baseline_id": _id(baseline_id),
            "reason": reason,
            "superseded_by_ref": _id(superseded_by_ref),
        },
    )


def sustainment_contract_registered_payload(
    *, contract_id: TypedId, customer_ref: TypedId
) -> CanonicalPayload:
    return _payload(
        SUSTAINMENT_CONTRACT_REGISTERED,
        {"contract_id": _id(contract_id), "customer_ref": _id(customer_ref)},
    )


def sustainment_contract_version_issued_payload(
    *,
    contract_id: TypedId,
    version_no: int,
    valid_from: datetime,
    coverage_summary: str,
    amendment_ref: TypedId | None,
) -> CanonicalPayload:
    return _payload(
        SUSTAINMENT_CONTRACT_VERSION_ISSUED,
        {
            "amendment_ref": _optional_id(amendment_ref),
            "contract_id": _id(contract_id),
            "coverage_summary": coverage_summary,
            "valid_from": valid_from,
            "version_no": version_no,
        },
    )


def site_registered_payload(
    *,
    site_id: TypedId,
    customer_ref: TypedId,
    code: str,
    kind: str,
) -> CanonicalPayload:
    return _payload(
        SITE_REGISTERED,
        {
            "code": code,
            "customer_ref": _id(customer_ref),
            "kind": kind,
            "site_id": _id(site_id),
        },
    )


def inventory_stock_position_opened_payload(
    *,
    stock_position_id: TypedId,
    part_ref: TypedId,
    location_ref: TypedId,
    purpose: str,
    ownership: str,
) -> CanonicalPayload:
    return _payload(
        INVENTORY_STOCK_POSITION_OPENED,
        {
            "location_ref": _id(location_ref),
            "ownership": ownership,
            "part_ref": _id(part_ref),
            "purpose": purpose,
            "stock_position_id": _id(stock_position_id),
        },
    )


def inventory_stock_adjusted_payload(
    *,
    stock_position_id: TypedId,
    delta_by_status: Mapping[str, Decimal],
    reason: str,
    actor_ref: TypedId,
) -> CanonicalPayload:
    return _payload(
        INVENTORY_STOCK_ADJUSTED,
        {
            "actor_ref": _id(actor_ref),
            "delta_by_status": {
                bucket: _decimal(delta) for bucket, delta in delta_by_status.items()
            },
            "reason": reason,
            "stock_position_id": _id(stock_position_id),
        },
    )


def inventory_stock_reserved_payload(
    *,
    reservation_id: TypedId,
    stock_position_ref: TypedId,
    demand_kind: str,
    demand_ref: TypedId,
    qty: Decimal,
    purpose: str,
    priority: int,
    decision_ref: TypedId | None,
) -> CanonicalPayload:
    return _payload(
        INVENTORY_STOCK_RESERVED,
        {
            "decision_ref": _optional_id(decision_ref),
            "demand_kind": demand_kind,
            "demand_ref": _id(demand_ref),
            "priority": priority,
            "purpose": purpose,
            "qty": _decimal(qty),
            "reservation_id": _id(reservation_id),
            "stock_position_ref": _id(stock_position_ref),
        },
    )


def inventory_stock_reservation_allocated_payload(*, reservation_id: TypedId) -> CanonicalPayload:
    return _payload(
        INVENTORY_STOCK_RESERVATION_ALLOCATED,
        {"reservation_id": _id(reservation_id)},
    )


def inventory_stock_reservation_released_payload(
    *, reservation_id: TypedId, reason: str
) -> CanonicalPayload:
    return _payload(
        INVENTORY_STOCK_RESERVATION_RELEASED,
        {"reason": reason, "reservation_id": _id(reservation_id)},
    )


def inventory_stock_consumed_payload(
    *,
    reservation_id: TypedId,
    work_order_ref: TypedId,
    qty: Decimal,
    lot: str | None,
    serial: str | None,
) -> CanonicalPayload:
    return _payload(
        INVENTORY_STOCK_CONSUMED,
        {
            "lot": lot,
            "qty": _decimal(qty),
            "reservation_id": _id(reservation_id),
            "serial": serial,
            "work_order_ref": _id(work_order_ref),
        },
    )


def inventory_allocation_decided_payload(
    *,
    part_ref: TypedId,
    location_ref: TypedId,
    winning_demand_ref: TypedId,
    losing_demand_refs: tuple[TypedId, ...],
    decision_ref: TypedId,
) -> CanonicalPayload:
    return _payload(
        INVENTORY_ALLOCATION_DECIDED,
        {
            "decision_ref": _id(decision_ref),
            "location_ref": _id(location_ref),
            "losing_demand_refs": _ids(losing_demand_refs),
            "part_ref": _id(part_ref),
            "winning_demand_ref": _id(winning_demand_ref),
        },
    )


def inventory_transfer_requested_payload(
    *,
    transfer_id: TypedId,
    part_ref: TypedId,
    from_location_ref: TypedId,
    to_location_ref: TypedId,
    qty: Decimal,
    linked_reservation_ref: TypedId | None,
) -> CanonicalPayload:
    return _payload(
        INVENTORY_TRANSFER_REQUESTED,
        {
            "from_location_ref": _id(from_location_ref),
            "linked_reservation_ref": _optional_id(linked_reservation_ref),
            "part_ref": _id(part_ref),
            "qty": _decimal(qty),
            "to_location_ref": _id(to_location_ref),
            "transfer_id": _id(transfer_id),
        },
    )


def inventory_transfer_dispatched_payload(
    *, transfer_id: TypedId, qty: Decimal, from_location_ref: TypedId
) -> CanonicalPayload:
    return _payload(
        INVENTORY_TRANSFER_DISPATCHED,
        {
            "from_location_ref": _id(from_location_ref),
            "qty": _decimal(qty),
            "transfer_id": _id(transfer_id),
        },
    )


def inventory_transfer_received_payload(
    *,
    transfer_id: TypedId,
    qty_received: Decimal,
    to_location_ref: TypedId,
    partial: bool,
) -> CanonicalPayload:
    return _payload(
        INVENTORY_TRANSFER_RECEIVED,
        {
            "partial": partial,
            "qty_received": _decimal(qty_received),
            "to_location_ref": _id(to_location_ref),
            "transfer_id": _id(transfer_id),
        },
    )


def part_registered_payload(
    *,
    part_id: TypedId,
    part_number: str,
    description: str,
    manufacturer: str,
    manufacturer_pn: str | None,
    nsn: str | None,
) -> CanonicalPayload:
    return _payload(
        PART_REGISTERED,
        {
            "description": description,
            "manufacturer": manufacturer,
            "manufacturer_pn": manufacturer_pn,
            "nsn": nsn,
            "part_id": _id(part_id),
            "part_number": part_number,
        },
    )


def part_revision_added_payload(
    *,
    part_id: TypedId,
    revision_id: TypedId,
    revision_code: str,
    spec_ref: TypedId | None,
    drawing_ref: TypedId | None,
) -> CanonicalPayload:
    return _payload(
        PART_REVISION_ADDED,
        {
            "drawing_ref": _optional_id(drawing_ref),
            "part_id": _id(part_id),
            "revision_code": revision_code,
            "revision_id": _id(revision_id),
            "spec_ref": _optional_id(spec_ref),
        },
    )


def part_revision_superseded_payload(
    *,
    part_id: TypedId,
    predecessor_revision_id: TypedId,
    successor_revision_id: TypedId,
    reason: str,
) -> CanonicalPayload:
    return _payload(
        PART_REVISION_SUPERSEDED,
        {
            "part_id": _id(part_id),
            "predecessor_revision_id": _id(predecessor_revision_id),
            "reason": reason,
            "successor_revision_id": _id(successor_revision_id),
        },
    )


def part_lifecycle_state_changed_payload(
    *,
    part_id: TypedId,
    revision_id: TypedId,
    from_state: str,
    to_state: str,
) -> CanonicalPayload:
    return _payload(
        PART_LIFECYCLE_STATE_CHANGED,
        {
            "from_state": from_state,
            "part_id": _id(part_id),
            "revision_id": _id(revision_id),
            "to_state": to_state,
        },
    )


def part_interchangeability_group_changed_payload(
    *,
    group_id: TypedId,
    part_revision_ref: TypedId,
    change: str,
) -> CanonicalPayload:
    """`change` é `"ADDED"` ou `"REMOVED"` (`08_DOMAIN_EVENTS.md` §1)."""
    return _payload(
        PART_INTERCHANGEABILITY_GROUP_CHANGED,
        {
            "change": change,
            "group_id": _id(group_id),
            "part_revision_ref": _id(part_revision_ref),
        },
    )


def applicability_asserted_payload(
    *,
    applicability_id: TypedId,
    part_ref: TypedId,
    part_revision_ref: TypedId,
    model_ref: TypedId,
    variant_ref: TypedId | None,
    evidence_ref: TypedId,
    asserted_at: datetime,
) -> CanonicalPayload:
    return _payload(
        APPLICABILITY_ASSERTED,
        {
            "applicability_id": _id(applicability_id),
            "asserted_at": asserted_at,
            "evidence_ref": _id(evidence_ref),
            "model_ref": _id(model_ref),
            "part_ref": _id(part_ref),
            "part_revision_ref": _id(part_revision_ref),
            "variant_ref": _optional_id(variant_ref),
        },
    )


def applicability_withdrawn_payload(
    *,
    applicability_id: TypedId,
    reason: str,
    correction_ref: TypedId | None,
) -> CanonicalPayload:
    return _payload(
        APPLICABILITY_WITHDRAWN,
        {
            "applicability_id": _id(applicability_id),
            "correction_ref": _optional_id(correction_ref),
            "reason": reason,
        },
    )
