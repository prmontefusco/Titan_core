"""Implementação de FactProviderPort para a vertical Titan Livestock (Passo 8.0 - 9.5)."""

from dataclasses import dataclass
from datetime import datetime

from packages.core_application.fact_service import FactProviderPort
from packages.core_domain.facts import Fact, FactSnapshot
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.lot_service import LotMembershipRepositoryPort
from packages.livestock_application.movement_service import PropertyStayRepositoryPort
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.withdrawal_service import WithdrawalCalculator
from packages.livestock_domain.withdrawal import WITHDRAWAL_RULE_VERSION
from packages.shared_kernel import OrganizationId, TypedId

# Fato de carência consumido pela regra de elegibilidade farmacológica (Passo 9.5).
WITHDRAWAL_FACT_TYPE = "livestock.withdrawal"
# Fato de elegibilidade do lote, consumido pela regra de bloqueio de lote (Passo 9.6).
LOT_ELIGIBILITY_FACT_TYPE = "livestock.lot_eligibility"


@dataclass(frozen=True, slots=True)
class LivestockFactProvider(FactProviderPort):
    property_repository: RuralPropertyRepositoryPort
    animal_repository: AnimalRepositoryPort
    stay_repository: PropertyStayRepositoryPort | None = None
    withdrawal_calculator: WithdrawalCalculator | None = None
    membership_repository: LotMembershipRepositoryPort | None = None

    def get_snapshot(
        self,
        organization_id: OrganizationId,
        target_id: TypedId,
        at_time: datetime,
    ) -> FactSnapshot:
        fact_list: list[Fact] = []

        if target_id.entity_type == "rural_property":
            prop = self.property_repository.get_by_id(target_id)
            if prop is not None and prop.organization_id == organization_id:
                fact_list.append(
                    Fact.create(
                        fact_type="livestock.rural_property",
                        payload={
                            "property_code": prop.code,
                            "property_name": prop.name,
                            "municipality": prop.municipality,
                            "state_code": prop.state_code,
                            "registration_number": prop.registration_number,
                            "total_area_hectares": prop.total_area_hectares,
                            "status": prop.status,
                            "version": prop.version,
                        },
                        observed_at=at_time,
                    )
                )

        elif target_id.entity_type == "animal":
            animal = self.animal_repository.get_by_id(target_id)
            if animal is not None and animal.organization_id == organization_id:
                tags_payload = [
                    {
                        "identifier_id": tag.identifier_id.value.hex,
                        "type": tag.identifier_type.value,
                        "value": tag.identifier_value,
                        "state": tag.state.value,
                        "verification_status": tag.verification_status.value,
                    }
                    for tag in animal.identifiers
                ]

                animal_payload: dict[
                    str, str | int | float | bool | None | list[dict[str, str]]
                ] = {
                    "sex": animal.sex.value,
                    "breed": animal.breed,
                    "birth_property_id": animal.birth_property_id.value.hex,
                    "version": animal.version,
                    "identifiers": tags_payload,
                }

                if self.stay_repository is not None:
                    active_stay = self.stay_repository.get_active_stay(target_id)
                    if active_stay is not None:
                        animal_payload["current_property_id"] = active_stay.property_id.value.hex
                        animal_payload["stay_status"] = active_stay.status.value

                fact_list.append(
                    Fact.create(
                        fact_type="livestock.animal",
                        payload=animal_payload,
                        observed_at=at_time,
                    )
                )

                if self.withdrawal_calculator is not None:
                    status = self.withdrawal_calculator.assess_animal(organization_id, target_id)
                    blocking = [
                        contribution.medication_batch_id.value.hex
                        for contribution in status.contributions
                        if contribution.withdrawal_ends_at > at_time
                    ]
                    fact_list.append(
                        Fact.create(
                            fact_type=WITHDRAWAL_FACT_TYPE,
                            payload={
                                "in_withdrawal": status.is_in_withdrawal_at(at_time),
                                "eligible_from": (
                                    status.eligible_from.isoformat()
                                    if status.eligible_from is not None
                                    else None
                                ),
                                "rule_version": status.rule_version,
                                "blocking_batches": blocking,
                            },
                            observed_at=at_time,
                        )
                    )

        elif target_id.entity_type == "livestock_lot":
            if self.membership_repository is not None and self.withdrawal_calculator is not None:
                memberships = self.membership_repository.get_memberships_for_lot(
                    target_id, at_time=at_time
                )
                blocking_animals = [
                    membership.animal_id.value.hex
                    for membership in memberships
                    if self.withdrawal_calculator.assess_animal(
                        organization_id, membership.animal_id
                    ).is_in_withdrawal_at(at_time)
                ]
                fact_list.append(
                    Fact.create(
                        fact_type=LOT_ELIGIBILITY_FACT_TYPE,
                        payload={
                            "has_animal_in_withdrawal": len(blocking_animals) > 0,
                            "blocking_animals": blocking_animals,
                            "member_count": len(memberships),
                            "rule_version": WITHDRAWAL_RULE_VERSION,
                        },
                        observed_at=at_time,
                    )
                )

        # `.create` calcula o hash de integridade do snapshot; o construtor direto o
        # deixaria vazio, e o Passo 9.6 depende de comparar hashes de snapshot.
        return FactSnapshot.create(
            organization_id=organization_id,
            target_id=target_id,
            as_of=at_time,
            facts=tuple(fact_list),
        )
