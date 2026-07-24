"""Gravação de eventos da vertical no log do Core (Passo 10.1a)."""

from datetime import UTC, datetime

import pytest

from packages.livestock_application.event_recorder import (
    AGGREGATE_CONTRACT_VERSION,
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_domain.events import (
    ANIMAL_REGISTERED,
    LOT_CREATED,
    animal_registered_payload,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from tests.livestock_application.conftest import RECORDED_AT, FakeEventLog

OCCURRED_AT = datetime(2026, 7, 20, 9, 30, tzinfo=UTC)


def a_payload(animal_id: TypedId) -> object:
    return animal_registered_payload(
        animal_id=animal_id,
        birth_property_id=TypedId.new("rural_property"),
        sex="FEMEA",
        breed="Nelore",
        birth_date="2024-03-01",
    )


def test_records_event_with_authorship_correlation_and_first_version(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    animal_id = TypedId.new("animal")

    event = recorder.record(
        context=context,
        aggregate_id=animal_id,
        event_type=ANIMAL_REGISTERED,
        payload=a_payload(animal_id),  # type: ignore[arg-type]
        occurred_at=OCCURRED_AT,
    )

    assert event_log.events == [event]
    assert event.aggregate_version == 1
    assert event.event_type == ANIMAL_REGISTERED
    assert event.aggregate_reference.target_id == animal_id
    assert event.aggregate_reference.contract_version == AGGREGATE_CONTRACT_VERSION
    assert event.actor_reference == context.actor_reference
    assert event.source_reference == context.source_reference
    assert event.correlation_id == context.correlation_id
    assert event.causation_id is None


def test_separates_when_the_fact_occurred_from_when_it_was_recorded(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """O instante alegado é do operador; o de registro vem do relógio da Application."""
    animal_id = TypedId.new("animal")

    event = recorder.record(
        context=context,
        aggregate_id=animal_id,
        event_type=ANIMAL_REGISTERED,
        payload=a_payload(animal_id),  # type: ignore[arg-type]
        occurred_at=OCCURRED_AT,
    )

    assert event.timestamps.occurred_at == OCCURRED_AT
    assert event.timestamps.recorded_at == RECORDED_AT


def test_version_advances_per_aggregate_and_not_globally(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    first_animal = TypedId.new("animal")
    second_animal = TypedId.new("animal")

    one = recorder.record(
        context=context,
        aggregate_id=first_animal,
        event_type=ANIMAL_REGISTERED,
        payload=a_payload(first_animal),  # type: ignore[arg-type]
        occurred_at=OCCURRED_AT,
    )
    two = recorder.record(
        context=context,
        aggregate_id=second_animal,
        event_type=ANIMAL_REGISTERED,
        payload=a_payload(second_animal),  # type: ignore[arg-type]
        occurred_at=OCCURRED_AT,
    )
    three = recorder.record(
        context=context,
        aggregate_id=first_animal,
        event_type=ANIMAL_REGISTERED,
        payload=a_payload(first_animal),  # type: ignore[arg-type]
        occurred_at=OCCURRED_AT,
    )

    assert (one.aggregate_version, two.aggregate_version, three.aggregate_version) == (1, 1, 2)


def test_rejects_event_type_not_declared_by_the_vertical(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """Evita que o log do Core receba tipo improvisado, indecifrável depois."""
    animal_id = TypedId.new("animal")

    with pytest.raises(ValueError, match="não é um evento declarado"):
        recorder.record(
            context=context,
            aggregate_id=animal_id,
            event_type="livestock.inventado",
            payload=a_payload(animal_id),  # type: ignore[arg-type]
            occurred_at=OCCURRED_AT,
        )


def test_causation_links_a_correction_to_what_it_corrects(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    lot_id = TypedId.new("livestock_lot")
    original = recorder.record(
        context=context,
        aggregate_id=lot_id,
        event_type=LOT_CREATED,
        payload=a_payload(TypedId.new("animal")),  # type: ignore[arg-type]
        occurred_at=OCCURRED_AT,
    )

    follow_up = recorder.record(
        context=context,
        aggregate_id=lot_id,
        event_type=LOT_CREATED,
        payload=a_payload(TypedId.new("animal")),  # type: ignore[arg-type]
        occurred_at=OCCURRED_AT,
        causation_id=original.event_id,
    )

    assert follow_up.causation_id == original.event_id


def test_context_refuses_actor_from_another_organization() -> None:
    organization_id = OrganizationId.new()
    foreign = UniversalReference(
        target_id=TypedId.new("actor"),
        organization_id=OrganizationId.new(),
        contract_version=1,
    )

    with pytest.raises(ValueError, match="actor_reference pertence a outra Organization"):
        LivestockOperationContext(
            organization_id=organization_id,
            actor_reference=foreign,
            source_reference=UniversalReference(
                target_id=TypedId.new("system"),
                organization_id=organization_id,
                contract_version=1,
            ),
            correlation_id=TypedId.new("correlation"),
        )


def test_context_refuses_correlation_with_wrong_logical_type() -> None:
    organization_id = OrganizationId.new()
    reference = UniversalReference(
        target_id=TypedId.new("actor"),
        organization_id=organization_id,
        contract_version=1,
    )

    with pytest.raises(ValueError, match="'correlation'"):
        LivestockOperationContext(
            organization_id=organization_id,
            actor_reference=reference,
            source_reference=reference,
            correlation_id=TypedId.new("animal"),
        )


def test_same_correlation_ties_operations_of_one_flow(
    recorder: LivestockEventRecorder, organization_id: OrganizationId
) -> None:
    correlation_id = TypedId.new("correlation")
    shared = LivestockOperationContext.create(
        organization_id=organization_id,
        actor_id=TypedId.new("actor"),
        source_id=TypedId.new("system"),
        correlation_id=correlation_id,
    )
    first_animal = TypedId.new("animal")
    second_animal = TypedId.new("animal")

    one = recorder.record(
        context=shared,
        aggregate_id=first_animal,
        event_type=ANIMAL_REGISTERED,
        payload=a_payload(first_animal),  # type: ignore[arg-type]
        occurred_at=OCCURRED_AT,
    )
    two = recorder.record(
        context=shared,
        aggregate_id=second_animal,
        event_type=ANIMAL_REGISTERED,
        payload=a_payload(second_animal),  # type: ignore[arg-type]
        occurred_at=OCCURRED_AT,
    )

    assert one.correlation_id == two.correlation_id == correlation_id
