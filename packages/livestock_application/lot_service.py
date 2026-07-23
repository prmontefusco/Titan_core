"""Serviço de aplicação LotService (Passo 8.4 - Titan Livestock)."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.lot import (
    LivestockLot,
    LotMembership,
    LotStatus,
    LotType,
)
from packages.shared_kernel import OrganizationId, TypedId


class LivestockLotRepositoryPort(Protocol):
    def save(self, lot: LivestockLot) -> None: ...

    def update(self, lot: LivestockLot) -> None: ...

    def get_by_id(self, lot_id: TypedId) -> LivestockLot | None: ...

    def get_by_code(self, organization_id: OrganizationId, code: str) -> LivestockLot | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[LivestockLot]: ...


class LotMembershipRepositoryPort(Protocol):
    def save(self, membership: LotMembership) -> None: ...

    def update(self, membership: LotMembership) -> None: ...

    def get_active_memberships_for_animal(self, animal_id: TypedId) -> list[LotMembership]: ...

    def get_memberships_for_lot(
        self, lot_id: TypedId, at_time: datetime | None = None
    ) -> list[LotMembership]: ...


@dataclass(frozen=True, slots=True)
class LotService:
    lot_repository: LivestockLotRepositoryPort
    membership_repository: LotMembershipRepositoryPort
    animal_repository: AnimalRepositoryPort
    property_repository: RuralPropertyRepositoryPort

    def create_lot(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
        code: str,
        name: str,
        lot_type: LotType = LotType.OPERATIONAL,
    ) -> LivestockLot:
        prop = self.property_repository.get_by_id(property_id)
        if prop is None or prop.organization_id != organization_id:
            raise KeyError(
                f"Propriedade '{property_id.value}' não encontrada ou "
                "pertencente a outra organização."
            )

        existing = self.lot_repository.get_by_code(organization_id, code)
        if existing is not None:
            raise ValueError(
                f"Já existe um lote com o código '{code}' cadastrado para a organização "
                f"{organization_id.value}."
            )

        lot = LivestockLot(
            lot_id=TypedId.new("livestock_lot"),
            organization_id=organization_id,
            property_id=property_id,
            code=code,
            name=name,
            lot_type=lot_type,
            status=LotStatus.ACTIVE,
            created_at=datetime.now(UTC),
        )

        self.lot_repository.save(lot)
        return lot

    def add_animal_to_lot(
        self,
        lot_id: TypedId,
        animal_id: TypedId,
        reason: str | None = None,
    ) -> LotMembership:
        lot = self.lot_repository.get_by_id(lot_id)
        if lot is None:
            raise KeyError(f"Lote '{lot_id.value}' não encontrado.")

        animal = self.animal_repository.get_by_id(animal_id)
        if animal is None or animal.organization_id != lot.organization_id:
            raise KeyError(
                f"Animal '{animal_id.value}' não encontrado ou pertencente a outra organização."
            )

        # Regra de Exclusividade: Lotes Operacionais não permitem sobreposição de lote ativo
        if lot.lot_type == LotType.OPERATIONAL:
            active_memberships = self.membership_repository.get_active_memberships_for_animal(
                animal_id
            )
            for m in active_memberships:
                parent_lot = self.lot_repository.get_by_id(m.lot_id)
                if parent_lot is not None and parent_lot.lot_type == LotType.OPERATIONAL:
                    raise ValueError(
                        f"Animal '{animal_id.value}' já pertence ao lote operacional ativo "
                        f"'{parent_lot.code}'."
                    )

        now_utc = datetime.now(UTC)
        membership = LotMembership(
            membership_id=TypedId.new("lot_membership"),
            lot_id=lot_id,
            animal_id=animal_id,
            valid_from=now_utc,
            valid_until=None,
            reason=reason,
        )

        self.membership_repository.save(membership)
        return membership

    def remove_animal_from_lot(
        self,
        lot_id: TypedId,
        animal_id: TypedId,
    ) -> LotMembership:
        lot = self.lot_repository.get_by_id(lot_id)
        if lot is None:
            raise KeyError(f"Lote '{lot_id.value}' não encontrado.")

        active_memberships = self.membership_repository.get_active_memberships_for_animal(animal_id)
        target_membership = None
        for m in active_memberships:
            if m.lot_id == lot_id:
                target_membership = m
                break

        if target_membership is None:
            raise KeyError(
                f"Animal '{animal_id.value}' não possui associação ativa no lote '{lot_id.value}'."
            )

        now_utc = datetime.now(UTC)
        closed_membership = replace(target_membership, valid_until=now_utc)
        self.membership_repository.update(closed_membership)
        return closed_membership

    def get_lot_composition(
        self, lot_id: TypedId, at_time: datetime | None = None
    ) -> list[LotMembership]:
        return self.membership_repository.get_memberships_for_lot(lot_id, at_time=at_time)
