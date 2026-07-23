"""Testes unitários de domínio para Animal e AnimalIdentifier (Passo 8.2 - Titan Livestock)."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from packages.livestock_domain.animal import (
    Animal,
    AnimalIdentifier,
    AnimalSex,
    IdentifierState,
    IdentifierType,
)
from packages.shared_kernel import OrganizationId, TypedId


def test_animal_creation_and_identifier_attachment() -> None:
    org_id = OrganizationId(uuid4())
    animal_id = TypedId.new("animal")
    prop_id = TypedId.new("rural_property")

    tag1 = AnimalIdentifier(
        identifier_id=TypedId.new("animal_identifier"),
        identifier_type=IdentifierType.OFFICIAL_SISBOV,
        identifier_value="BR100982341",
    )

    animal = Animal(
        animal_id=animal_id,
        organization_id=org_id,
        birth_property_id=prop_id,
        sex=AnimalSex.MALE,
        breed="Nelore",
        birth_date=date(2025, 5, 10),
        identifiers=(tag1,),
    )

    assert animal.animal_id == animal_id
    assert animal.sex == AnimalSex.MALE
    assert animal.breed == "Nelore"
    assert len(animal.identifiers) == 1
    assert animal.get_active_identifier(IdentifierType.OFFICIAL_SISBOV) == tag1

    # Anexa novo brinco de manejo EAR_TAG
    tag2 = AnimalIdentifier(
        identifier_id=TypedId.new("animal_identifier"),
        identifier_type=IdentifierType.EAR_TAG,
        identifier_value="BR-102",
    )
    animal_updated = animal.attach_identifier(tag2)
    assert len(animal_updated.identifiers) == 2
    assert animal_updated.get_active_identifier(IdentifierType.EAR_TAG) == tag2

    # A identidade permanente não muda ao atualizar identificadores
    assert animal_updated.animal_id == animal.animal_id


def test_animal_cannot_have_two_active_tags_of_same_type() -> None:
    org_id = OrganizationId(uuid4())
    animal_id = TypedId.new("animal")
    prop_id = TypedId.new("rural_property")

    tag1 = AnimalIdentifier(
        identifier_id=TypedId.new("animal_identifier"),
        identifier_type=IdentifierType.EAR_TAG,
        identifier_value="TAG-01",
    )
    tag2 = AnimalIdentifier(
        identifier_id=TypedId.new("animal_identifier"),
        identifier_type=IdentifierType.EAR_TAG,
        identifier_value="TAG-02",
    )

    with pytest.raises(ValueError, match="já possui um identificador ativo do tipo 'EAR_TAG'"):
        Animal(
            animal_id=animal_id,
            organization_id=org_id,
            birth_property_id=prop_id,
            sex=AnimalSex.FEMALE,
            identifiers=(tag1, tag2),
        )


def test_deactivate_identifier_preserves_history() -> None:
    org_id = OrganizationId(uuid4())
    animal_id = TypedId.new("animal")
    prop_id = TypedId.new("rural_property")

    tag1 = AnimalIdentifier(
        identifier_id=TypedId.new("animal_identifier"),
        identifier_type=IdentifierType.EAR_TAG,
        identifier_value="TAG-ANTIGA",
    )

    animal = Animal(
        animal_id=animal_id,
        organization_id=org_id,
        birth_property_id=prop_id,
        sex=AnimalSex.FEMALE,
        identifiers=(tag1,),
    )

    t_now = datetime.now(UTC)
    animal_deactivated = animal.deactivate_identifier(tag1.identifier_id, deactivated_at=t_now)

    assert animal_deactivated.get_active_identifier(IdentifierType.EAR_TAG) is None
    assert len(animal_deactivated.identifiers) == 1
    assert animal_deactivated.identifiers[0].state == IdentifierState.DEACTIVATED

    # Agora pode anexar uma nova tag EAR_TAG já que a antiga foi desativada
    tag2 = AnimalIdentifier(
        identifier_id=TypedId.new("animal_identifier"),
        identifier_type=IdentifierType.EAR_TAG,
        identifier_value="TAG-NOVA",
    )
    animal_repaired = animal_deactivated.attach_identifier(tag2)
    assert len(animal_repaired.identifiers) == 2
    assert animal_repaired.get_active_identifier(IdentifierType.EAR_TAG) == tag2


def test_animal_id_is_immutable() -> None:
    org_id = OrganizationId(uuid4())
    animal = Animal(
        animal_id=TypedId.new("animal"),
        organization_id=org_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.MALE,
    )

    with pytest.raises(AttributeError):
        setattr(animal, "animal_id", TypedId.new("animal"))  # noqa: B010
