"""Testes unitários para MovementService (Passo 8.3 - Titan Livestock)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from packages.livestock_application.animal_service import (
    AnimalRepositoryPort,
    AnimalService,
)
from packages.livestock_application.movement_service import (
    MovementRepositoryPort,
    MovementService,
    PropertyStayRepositoryPort,
)
from packages.livestock_application.property_service import (
    RuralPropertyRepositoryPort,
    RuralPropertyService,
)
from packages.livestock_domain.animal import Animal, AnimalSex, IdentifierType
from packages.livestock_domain.movement import (
    AnimalMovement,
    PropertyStay,
    StayStatus,
)
from packages.livestock_domain.property import RuralProperty
from packages.shared_kernel import OrganizationId, TypedId


class InMemoryMovementRepository(MovementRepositoryPort):
    def __init__(self) -> None:
        self.movements: dict[str, AnimalMovement] = {}

    def save(self, movement: AnimalMovement) -> None:
        self.movements[movement.movement_id.value.hex] = movement

    def get_by_id(self, movement_id: TypedId) -> AnimalMovement | None:
        return self.movements.get(movement_id.value.hex)

    def list_by_animal(self, animal_id: TypedId) -> list[AnimalMovement]:
        return [m for m in self.movements.values() if animal_id in m.animal_ids]

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[AnimalMovement]:
        filtered = [m for m in self.movements.values() if m.organization_id == organization_id]
        return filtered[offset : offset + limit]


class InMemoryPropertyStayRepository(PropertyStayRepositoryPort):
    def __init__(self) -> None:
        self.stays: dict[str, PropertyStay] = {}

    def save(self, stay: PropertyStay) -> None:
        self.stays[stay.stay_id.value.hex] = stay

    def update(self, stay: PropertyStay) -> None:
        self.stays[stay.stay_id.value.hex] = stay

    def delete_by_animal(self, animal_id: TypedId) -> None:
        self.stays = {k: s for k, s in self.stays.items() if s.animal_id != animal_id}

    def get_active_stay(self, animal_id: TypedId) -> PropertyStay | None:
        for s in self.stays.values():
            if s.animal_id == animal_id and s.status == StayStatus.ACTIVE:
                return s
        return None

    def get_timeline(self, animal_id: TypedId) -> list[PropertyStay]:
        filtered = [s for s in self.stays.values() if s.animal_id == animal_id]
        filtered.sort(key=lambda s: s.start_time)
        return filtered


class InMemoryPropertyRepo(RuralPropertyRepositoryPort):
    def __init__(self) -> None:
        self.props: dict[str, RuralProperty] = {}

    def save(self, property: RuralProperty) -> None:
        self.props[property.property_id.value.hex] = property

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None:
        return self.props.get(property_id.value.hex)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        for p in self.props.values():
            if p.organization_id == organization_id and p.code == code:
                return p
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        return [p for p in self.props.values() if p.organization_id == organization_id]


class InMemoryAnimalRepo(AnimalRepositoryPort):
    def __init__(self) -> None:
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
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Animal]:
        return [a for a in self.animals.values() if a.organization_id == organization_id]


def test_register_movement_updates_stays_timeline() -> None:
    org_id = OrganizationId(uuid4())
    prop_repo = InMemoryPropertyRepo()
    animal_repo = InMemoryAnimalRepo()
    m_repo = InMemoryMovementRepository()
    stay_repo = InMemoryPropertyStayRepository()

    prop_service = RuralPropertyService(repository=prop_repo)
    animal_service = AnimalService(repository=animal_repo)
    movement_service = MovementService(
        movement_repository=m_repo,
        stay_repository=stay_repo,
        animal_repository=animal_repo,
        property_repository=prop_repo,
    )

    # 1. Cadastra 2 fazendas
    p_orig = prop_service.register_property(
        organization_id=org_id,
        code="ORIGEM-01",
        name="Fazenda Origem",
        municipality="Ribeirão Preto",
        state_code="SP",
    )
    p_dest = prop_service.register_property(
        organization_id=org_id,
        code="DESTINO-02",
        name="Fazenda Destino",
        municipality="Sertãozinho",
        state_code="SP",
    )

    # 2. Cadastra 1 animal
    animal = animal_service.register_animal(
        organization_id=org_id,
        birth_property_id=p_orig.property_id,
        sex=AnimalSex.MALE,
        breed="Nelore",
    )

    # Cria a estada inicial no nascimento
    stay_repo.save(
        PropertyStay(
            stay_id=TypedId.new("property_stay"),
            organization_id=org_id,
            animal_id=animal.animal_id,
            property_id=p_orig.property_id,
            start_time=datetime.now(UTC) - timedelta(days=30),
            end_time=None,
            status=StayStatus.ACTIVE,
        )
    )

    # 3. Movimenta o animal para a fazenda de destino
    m_time = datetime.now(UTC) - timedelta(hours=1)
    movement = movement_service.register_movement(
        organization_id=org_id,
        origin_property_id=p_orig.property_id,
        destination_property_id=p_dest.property_id,
        movement_time=m_time,
        animal_ids=(animal.animal_id,),
        reason="Manejo de engorda",
    )

    assert movement.origin_property_id == p_orig.property_id

    # 4. Verifica se a estada ativa agora é no destino
    active_stay = movement_service.get_active_stay(animal.animal_id)
    assert active_stay is not None
    assert active_stay.property_id == p_dest.property_id
    assert active_stay.status == StayStatus.ACTIVE

    # 5. Verifica a timeline completa (2 estadas: Origem encerrada e Destino ativa)
    timeline = movement_service.get_stay_timeline(animal.animal_id)
    assert len(timeline) == 2
    assert timeline[0].status == StayStatus.CLOSED
    assert timeline[0].property_id == p_orig.property_id
    assert timeline[1].status == StayStatus.ACTIVE
    assert timeline[1].property_id == p_dest.property_id
