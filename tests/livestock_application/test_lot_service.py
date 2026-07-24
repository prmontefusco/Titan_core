"""Testes unitários para LotService (Passo 8.4 - Titan Livestock)."""

from datetime import datetime

import pytest

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.lot_service import (
    LivestockLotRepositoryPort,
    LotMembershipRepositoryPort,
    LotService,
)
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.animal import Animal, AnimalSex, IdentifierType
from packages.livestock_domain.events import (
    ANIMAL_ADDED_TO_LOT,
    ANIMAL_REMOVED_FROM_LOT,
    LOT_CREATED,
)
from packages.livestock_domain.lot import (
    LivestockLot,
    LotMembership,
    LotType,
)
from packages.livestock_domain.property import RuralProperty
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog


class InMemoryLotRepository(LivestockLotRepositoryPort):
    def __init__(self) -> None:
        self.lots: dict[str, LivestockLot] = {}

    def save(self, lot: LivestockLot) -> None:
        self.lots[lot.lot_id.value.hex] = lot

    def update(self, lot: LivestockLot) -> None:
        self.lots[lot.lot_id.value.hex] = lot

    def get_by_id(self, lot_id: TypedId) -> LivestockLot | None:
        return self.lots.get(lot_id.value.hex)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> LivestockLot | None:
        for item in self.lots.values():
            if item.organization_id == organization_id and item.code == code:
                return item
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[LivestockLot]:
        return [item for item in self.lots.values() if item.organization_id == organization_id]


class InMemoryMembershipRepository(LotMembershipRepositoryPort):
    def __init__(self) -> None:
        self.memberships: dict[str, LotMembership] = {}

    def save(self, membership: LotMembership) -> None:
        self.memberships[membership.membership_id.value.hex] = membership

    def update(self, membership: LotMembership) -> None:
        self.memberships[membership.membership_id.value.hex] = membership

    def get_active_memberships_for_animal(self, animal_id: TypedId) -> list[LotMembership]:
        return [
            m
            for m in self.memberships.values()
            if m.animal_id == animal_id and m.valid_until is None
        ]

    def get_memberships_for_lot(
        self, lot_id: TypedId, at_time: datetime | None = None
    ) -> list[LotMembership]:
        result = []
        for m in self.memberships.values():
            if m.lot_id == lot_id:
                if at_time is None:
                    if m.valid_until is None:
                        result.append(m)
                else:
                    if m.valid_from <= at_time and (
                        m.valid_until is None or m.valid_until > at_time
                    ):
                        result.append(m)
        return result


class InMemoryPropertyRepo(RuralPropertyRepositoryPort):
    def __init__(self) -> None:
        self.props: dict[str, RuralProperty] = {}

    def save(self, property: RuralProperty) -> None:
        self.props[property.property_id.value.hex] = property

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None:
        return self.props.get(property_id.value.hex)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        return list(self.props.values())


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
        return list(self.animals.values())


def test_operational_lot_exclusivity_rule(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    org_id = context.organization_id
    prop_id = TypedId.new("rural_property")
    animal_id = TypedId.new("animal")

    prop_repo = InMemoryPropertyRepo()
    prop_repo.save(
        RuralProperty(
            property_id=prop_id,
            organization_id=org_id,
            code="P-01",
            name="Fazenda 1",
            municipality="SP",
            state_code="SP",
        )
    )

    anim_repo = InMemoryAnimalRepo()
    anim_repo.save(
        Animal(
            animal_id=animal_id,
            organization_id=org_id,
            birth_property_id=prop_id,
            sex=AnimalSex.MALE,
        )
    )

    lot_repo = InMemoryLotRepository()
    mem_repo = InMemoryMembershipRepository()

    service = LotService(
        lot_repository=lot_repo,
        membership_repository=mem_repo,
        animal_repository=anim_repo,
        property_repository=prop_repo,
        recorder=recorder,
    )

    # 1. Cria 2 lotes operacionais de manejo
    lot_op1 = service.create_lot(
        context=context,
        property_id=prop_id,
        code="PASTO-1",
        name="Lote Pasto 1",
        lot_type=LotType.OPERATIONAL,
    )
    lot_op2 = service.create_lot(
        context=context,
        property_id=prop_id,
        code="PASTO-2",
        name="Lote Pasto 2",
        lot_type=LotType.OPERATIONAL,
    )

    # 2. Cria 1 lote sanitário de vacinação
    lot_san = service.create_lot(
        context=context,
        property_id=prop_id,
        code="VACCINE-AFTOSA",
        name="Lote Aftosa Maio",
        lot_type=LotType.SANITARY,
    )

    # Adiciona animal no Lote Operacional 1 (Sucesso)
    service.add_animal_to_lot(context, lot_op1.lot_id, animal_id)

    # Tenta adicionar no Lote Operacional 2 (Deve falhar por exclusividade de manejo)
    with pytest.raises(ValueError, match="já pertence ao lote operacional ativo"):
        service.add_animal_to_lot(context, lot_op2.lot_id, animal_id)

    # Adiciona no Lote Sanitário (Deve ter sucesso pois permite sobreposição)
    m_san = service.add_animal_to_lot(context, lot_san.lot_id, animal_id)
    assert m_san.lot_id == lot_san.lot_id

    # A inclusão recusada não deixou evento; cada lote tem o fluxo dele.
    assert len(event_log.of_type(LOT_CREATED)) == 3
    assert len(event_log.of_type(ANIMAL_ADDED_TO_LOT)) == 2
    assert event_log.versions_of(event_log.of_type(LOT_CREATED)[0].aggregate_reference) == (1, 2)


def test_removal_closes_the_membership_and_extends_the_lot_stream(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """Remover não apaga a entrada: fecha a vigência e acrescenta um fato."""
    org_id = context.organization_id
    prop_id = TypedId.new("rural_property")
    animal_id = TypedId.new("animal")

    prop_repo = InMemoryPropertyRepo()
    prop_repo.save(
        RuralProperty(
            property_id=prop_id,
            organization_id=org_id,
            code="P-01",
            name="Fazenda 1",
            municipality="SP",
            state_code="SP",
        )
    )
    anim_repo = InMemoryAnimalRepo()
    anim_repo.save(
        Animal(
            animal_id=animal_id,
            organization_id=org_id,
            birth_property_id=prop_id,
            sex=AnimalSex.MALE,
        )
    )
    service = LotService(
        lot_repository=InMemoryLotRepository(),
        membership_repository=InMemoryMembershipRepository(),
        animal_repository=anim_repo,
        property_repository=prop_repo,
        recorder=recorder,
    )

    lot = service.create_lot(
        context=context,
        property_id=prop_id,
        code="PASTO-1",
        name="Lote Pasto 1",
        lot_type=LotType.OPERATIONAL,
    )
    service.add_animal_to_lot(context, lot.lot_id, animal_id)
    closed = service.remove_animal_from_lot(context, lot.lot_id, animal_id)

    assert closed.valid_until is not None
    assert event_log.types() == [LOT_CREATED, ANIMAL_ADDED_TO_LOT, ANIMAL_REMOVED_FROM_LOT]
    assert [event.aggregate_version for event in event_log.events] == [1, 2, 3]


def test_refuses_lot_of_another_organization(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    org_id = context.organization_id
    prop_id = TypedId.new("rural_property")
    prop_repo = InMemoryPropertyRepo()
    prop_repo.save(
        RuralProperty(
            property_id=prop_id,
            organization_id=org_id,
            code="P-01",
            name="Fazenda 1",
            municipality="SP",
            state_code="SP",
        )
    )
    service = LotService(
        lot_repository=InMemoryLotRepository(),
        membership_repository=InMemoryMembershipRepository(),
        animal_repository=InMemoryAnimalRepo(),
        property_repository=prop_repo,
        recorder=recorder,
    )
    lot = service.create_lot(
        context=context,
        property_id=prop_id,
        code="PASTO-1",
        name="Lote Pasto 1",
        lot_type=LotType.OPERATIONAL,
    )
    intruder = LivestockOperationContext.create(
        organization_id=OrganizationId.new(),
        actor_id=TypedId.new("actor"),
        source_id=TypedId.new("system"),
    )

    with pytest.raises(KeyError, match="não encontrado"):
        service.add_animal_to_lot(intruder, lot.lot_id, TypedId.new("animal"))

    assert event_log.types() == [LOT_CREATED]
