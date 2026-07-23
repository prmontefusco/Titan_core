"""Testes unitários de domínio para AnimalMovement e PropertyStay (Passo 8.3 - Titan Livestock)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from packages.livestock_domain.movement import (
    AnimalMovement,
    PropertyStay,
    StayStatus,
)
from packages.shared_kernel import OrganizationId, TypedId


def test_animal_movement_creation_success() -> None:
    org_id = OrganizationId(uuid4())
    p_orig = TypedId.new("rural_property")
    p_dest = TypedId.new("rural_property")
    animal1 = TypedId.new("animal")
    animal2 = TypedId.new("animal")
    m_time = datetime.now(UTC) - timedelta(hours=2)

    movement = AnimalMovement(
        movement_id=TypedId.new("animal_movement"),
        organization_id=org_id,
        origin_property_id=p_orig,
        destination_property_id=p_dest,
        movement_time=m_time,
        animal_ids=(animal1, animal2),
        reason="Transferência de pasto",
    )

    assert movement.origin_property_id == p_orig
    assert movement.destination_property_id == p_dest
    assert len(movement.animal_ids) == 2


def test_animal_movement_rejects_naive_time() -> None:
    """O domínio rejeita datetime sem timezone; não o trata silenciosamente como UTC."""
    org_id = OrganizationId(uuid4())

    with pytest.raises(ValueError, match="timezone"):
        AnimalMovement(
            movement_id=TypedId.new("animal_movement"),
            organization_id=org_id,
            origin_property_id=TypedId.new("rural_property"),
            destination_property_id=TypedId.new("rural_property"),
            movement_time=datetime(2026, 7, 20, 12, 0),  # noqa: DTZ001 — naive de propósito
            animal_ids=(TypedId.new("animal"),),
        )


def test_animal_movement_same_origin_and_destination_fails() -> None:
    org_id = OrganizationId(uuid4())
    prop_id = TypedId.new("rural_property")
    animal_id = TypedId.new("animal")

    with pytest.raises(ValueError, match="não podem ser iguais"):
        AnimalMovement(
            movement_id=TypedId.new("animal_movement"),
            organization_id=org_id,
            origin_property_id=prop_id,
            destination_property_id=prop_id,
            movement_time=datetime.now(UTC),
            animal_ids=(animal_id,),
        )


def test_property_stay_creation_and_closed_invariants() -> None:
    org_id = OrganizationId(uuid4())
    animal_id = TypedId.new("animal")
    prop_id = TypedId.new("rural_property")
    t_start = datetime.now(UTC) - timedelta(days=10)
    t_end = datetime.now(UTC) - timedelta(days=2)

    stay = PropertyStay(
        stay_id=TypedId.new("property_stay"),
        organization_id=org_id,
        animal_id=animal_id,
        property_id=prop_id,
        start_time=t_start,
        end_time=t_end,
        status=StayStatus.CLOSED,
    )

    assert stay.status == StayStatus.CLOSED
    assert stay.end_time == t_end

    # Testar end_time <= start_time
    with pytest.raises(ValueError, match="estritamente posterior"):
        PropertyStay(
            stay_id=TypedId.new("property_stay"),
            organization_id=org_id,
            animal_id=animal_id,
            property_id=prop_id,
            start_time=t_end,
            end_time=t_start,
            status=StayStatus.CLOSED,
        )
