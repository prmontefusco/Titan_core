"""Testes unitários para AnimalService (Passo 8.2 - Titan Livestock)."""

import pytest

from packages.livestock_application.animal_service import (
    AnimalRepositoryPort,
    AnimalService,
)
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_domain.animal import (
    Animal,
    AnimalSex,
    IdentifierState,
    IdentifierType,
)
from packages.livestock_domain.events import (
    ANIMAL_REGISTERED,
    IDENTIFIER_ATTACHED,
    IDENTIFIER_DEACTIVATED,
)
from packages.livestock_domain.exit import AnimalExit
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog


class InMemoryAnimalRepository(AnimalRepositoryPort):
    def __init__(self) -> None:
        self.saidas: dict[str, AnimalExit] = {}
        self.animals: dict[str, Animal] = {}

    def save(self, animal: Animal) -> None:
        self.animals[animal.animal_id.value.hex] = animal

    def update(self, animal: Animal) -> None:
        self.animals[animal.animal_id.value.hex] = animal

    def get_by_id(self, animal_id: TypedId) -> Animal | None:
        return self.animals.get(animal_id.value.hex)

    def find_by_identifier(
        self,
        organization_id: OrganizationId,
        identifier_type: IdentifierType,
        identifier_value: str,
    ) -> Animal | None:
        for animal in self.animals.values():
            if animal.organization_id == organization_id:
                for tag in animal.identifiers:
                    if (
                        tag.identifier_type == identifier_type
                        and tag.identifier_value == identifier_value
                        and tag.state == IdentifierState.ACTIVE
                    ):
                        return animal
        return None

    def get_exit(self, animal_id: TypedId) -> AnimalExit | None:
        return self.saidas.get(animal_id.value.hex)

    def list_by_organization(
        self,
        organization_id: OrganizationId,
        limit: int = 50,
        offset: int = 0,
        identifier: str | None = None,
    ) -> list[Animal]:
        filtered = [a for a in self.animals.values() if a.organization_id == organization_id]
        if identifier is not None and identifier.strip():
            agulha = identifier.strip().lower()
            filtered = [
                a
                for a in filtered
                if any(agulha in tag.identifier_value.lower() for tag in a.identifiers)
            ]
        return filtered[offset : offset + limit]


def test_register_animal_and_find_by_sisbov(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    service = AnimalService(repository=InMemoryAnimalRepository(), recorder=recorder)

    animal = service.register_animal(
        context=context,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.MALE,
        breed="Nelore",
        initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
        initial_identifier_value="BR99881122",
    )

    assert animal.organization_id == context.organization_id
    found = service.find_by_identifier(
        context.organization_id, IdentifierType.OFFICIAL_SISBOV, "BR99881122"
    )
    assert found == animal


def test_list_by_organization_filters_by_identifier_substring(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    repository = InMemoryAnimalRepository()
    service = AnimalService(repository=repository, recorder=recorder)
    alvo = service.register_animal(
        context=context,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.FEMALE,
        initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
        initial_identifier_value="BR99881122",
    )
    outro = service.register_animal(
        context=context,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.MALE,
        initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
        initial_identifier_value="BR11223344",
    )

    parcial = repository.list_by_organization(context.organization_id, identifier="9988")
    assert [a.animal_id for a in parcial] == [alvo.animal_id]

    sem_match = repository.list_by_organization(context.organization_id, identifier="00000000")
    assert sem_match == []

    sem_filtro = repository.list_by_organization(context.organization_id, identifier=None)
    assert {a.animal_id for a in sem_filtro} == {alvo.animal_id, outro.animal_id}

    vazio = repository.list_by_organization(context.organization_id, identifier="   ")
    assert {a.animal_id for a in vazio} == {alvo.animal_id, outro.animal_id}


def test_registering_with_initial_tag_records_both_facts_in_order(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """A marcação é fato próprio: quem lê a linha do tempo não deve deduzi-la."""
    service = AnimalService(repository=InMemoryAnimalRepository(), recorder=recorder)

    animal = service.register_animal(
        context=context,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.MALE,
        initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
        initial_identifier_value="BR99881122",
    )

    assert event_log.types() == [ANIMAL_REGISTERED, IDENTIFIER_ATTACHED]
    versions = [event.aggregate_version for event in event_log.events]
    assert versions == [1, 2]
    assert all(
        event.aggregate_reference.target_id == animal.animal_id for event in event_log.events
    )


def test_registering_without_tag_records_only_the_registration(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service = AnimalService(repository=InMemoryAnimalRepository(), recorder=recorder)

    service.register_animal(
        context=context,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.FEMALE,
    )

    assert event_log.types() == [ANIMAL_REGISTERED]


def test_attach_and_deactivate_extend_the_same_animal_stream(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service = AnimalService(repository=InMemoryAnimalRepository(), recorder=recorder)
    animal = service.register_animal(
        context=context,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.FEMALE,
    )

    updated = service.attach_identifier(
        context=context,
        animal_id=animal.animal_id,
        identifier_type=IdentifierType.OFFICIAL_SISBOV,
        identifier_value="BR55443322",
    )
    tag = updated.identifiers[0]
    service.deactivate_identifier(
        context=context, animal_id=animal.animal_id, identifier_id=tag.identifier_id
    )

    assert event_log.types() == [ANIMAL_REGISTERED, IDENTIFIER_ATTACHED, IDENTIFIER_DEACTIVATED]
    assert [event.aggregate_version for event in event_log.events] == [1, 2, 3]


def test_refuses_to_touch_an_animal_of_another_organization(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """Sem esta guarda, o evento seria gravado no fluxo da Organization errada."""
    service = AnimalService(repository=InMemoryAnimalRepository(), recorder=recorder)
    animal = service.register_animal(
        context=context,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.FEMALE,
    )
    intruder = LivestockOperationContext.create(
        organization_id=OrganizationId.new(),
        actor_id=TypedId.new("actor"),
        source_id=TypedId.new("system"),
    )

    with pytest.raises(KeyError, match="não encontrado"):
        service.attach_identifier(
            context=intruder,
            animal_id=animal.animal_id,
            identifier_type=IdentifierType.OFFICIAL_SISBOV,
            identifier_value="BR11112222",
        )

    assert event_log.types() == [ANIMAL_REGISTERED]


def test_register_animal_duplicate_sisbov_fails(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service = AnimalService(repository=InMemoryAnimalRepository(), recorder=recorder)
    prop_id = TypedId.new("rural_property")

    service.register_animal(
        context=context,
        birth_property_id=prop_id,
        sex=AnimalSex.FEMALE,
        initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
        initial_identifier_value="BR99881122",
    )

    with pytest.raises(ValueError, match="Já existe um animal com o identificador"):
        service.register_animal(
            context=context,
            birth_property_id=prop_id,
            sex=AnimalSex.MALE,
            initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
            initial_identifier_value="BR99881122",
        )

    assert len(event_log.of_type(ANIMAL_REGISTERED)) == 1


def test_initial_tag_never_predates_the_registration_it_belongs_to(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """Ler o relógio duas vezes daria à marcação um instante anterior ao cadastro.

    Uma linha do tempo ordenada por `occurred_at` mostraria o brinco sendo posto
    antes de o animal existir. Em relógio de resolução grosseira o defeito quase
    não aparece; em Linux, com microssegundos, apareceria sempre.
    """
    service = AnimalService(repository=InMemoryAnimalRepository(), recorder=recorder)

    service.register_animal(
        context=context,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.MALE,
        initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
        initial_identifier_value="BR99881122",
    )

    registration, attachment = event_log.events
    assert attachment.timestamps.occurred_at >= registration.timestamps.occurred_at
    # Empatados, quem ordena é a versão do agregado, que não depende do relógio.
    assert registration.aggregate_version < attachment.aggregate_version
