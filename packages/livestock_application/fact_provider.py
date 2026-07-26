"""Implementação de FactProviderPort para a vertical Titan Livestock (Passo 8.0 - 9.5)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from packages.core_application.fact_service import FactProviderPort
from packages.core_domain.facts import Fact, FactSnapshot
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.lot_service import LotMembershipRepositoryPort
from packages.livestock_application.movement_service import PropertyStayRepositoryPort
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.withdrawal_service import WithdrawalCalculator
from packages.livestock_domain.imported_fact import FactOrigin, ImportedLivestockFact
from packages.livestock_domain.withdrawal import WITHDRAWAL_RULE_VERSION, compute_withdrawal_ends
from packages.shared_kernel import OrganizationId, TypedId

# Fato de carência consumido pela regra de elegibilidade farmacológica (Passo 9.5).
WITHDRAWAL_FACT_TYPE = "livestock.withdrawal"
# Fato de elegibilidade do lote, consumido pela regra de bloqueio de lote (Passo 9.6).
LOT_ELIGIBILITY_FACT_TYPE = "livestock.lot_eligibility"
IMPORTED_TREATMENT_FACT_TYPE = "livestock.treatment_applied"


class ImportedFactReaderPort(Protocol):
    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[ImportedLivestockFact]: ...


@dataclass(frozen=True, slots=True)
class LivestockFactProvider(FactProviderPort):
    property_repository: RuralPropertyRepositoryPort
    animal_repository: AnimalRepositoryPort
    stay_repository: PropertyStayRepositoryPort | None = None
    withdrawal_calculator: WithdrawalCalculator | None = None
    membership_repository: LotMembershipRepositoryPort | None = None
    imported_fact_repository: ImportedFactReaderPort | None = None

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
                    # Nulo quando o parto não teve propriedade determinável: o
                    # fato entra na avaliação com a lacuna declarada, e não com
                    # uma fazenda inventada (ADR-0040).
                    "birth_property_id": (
                        None
                        if animal.birth_property_id is None
                        else animal.birth_property_id.value.hex
                    ),
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
                    # As contribuições viajam no fato, com o prazo congelado em cada
                    # uma. Sem elas o fato afirmaria a carência sem mostrar a conta,
                    # e um dossiê não teria como percorrer fato -> aplicação ->
                    # evidência. Com elas, quem tem o fato refaz o cálculo.
                    contribuicoes = [
                        {
                            "application_id": contribution.application_id.value.hex,
                            "medication_batch_id": contribution.medication_batch_id.value.hex,
                            "applied_at": contribution.applied_at.isoformat(),
                            "withdrawal_period_days": contribution.withdrawal_period_days,
                            "withdrawal_ends_at": contribution.withdrawal_ends_at.isoformat(),
                            "origin": "LOCAL_OBSERVATION",
                        }
                        for contribution in status.contributions
                    ]
                    all_contributions = [
                        *contribuicoes,
                        *self._imported_withdrawal_contributions(organization_id, target_id),
                    ]
                    eligible_from = _latest_withdrawal_end(all_contributions)
                    blocking = [
                        _blocking_contribution_id(contribution)
                        for contribution in all_contributions
                        if datetime.fromisoformat(str(contribution["withdrawal_ends_at"])) > at_time
                    ]
                    fact_list.append(
                        Fact.create(
                            fact_type=WITHDRAWAL_FACT_TYPE,
                            payload={
                                "in_withdrawal": (
                                    eligible_from is not None and at_time < eligible_from
                                ),
                                "eligible_from": (
                                    None if eligible_from is None else eligible_from.isoformat()
                                ),
                                "rule_version": status.rule_version,
                                "blocking_batches": blocking,
                                "contributions": all_contributions,
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

    def _imported_withdrawal_contributions(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[dict[str, Any]]:
        if self.imported_fact_repository is None:
            return []
        contributions: list[dict[str, Any]] = []
        for fact in self.imported_fact_repository.list_by_animal(organization_id, animal_id):
            if fact.fact_type != IMPORTED_TREATMENT_FACT_TYPE:
                continue
            withdrawal_days = fact.payload.get("withdrawal_period_days")
            if not isinstance(withdrawal_days, int) or withdrawal_days < 0:
                continue
            withdrawal_ends_at = compute_withdrawal_ends(fact.occurred_at, withdrawal_days)
            contributions.append(
                {
                    "imported_fact_id": fact.imported_fact_id.value.hex,
                    "source_artifact_id": fact.source_artifact_id.value.hex,
                    "applied_at": fact.occurred_at.isoformat(),
                    "withdrawal_period_days": withdrawal_days,
                    "withdrawal_ends_at": withdrawal_ends_at.isoformat(),
                    "origin": fact.origin.value,
                    "asserted_by": fact.asserted_by,
                    "confidence_tier": fact.confidence_tier.value,
                }
            )
        return contributions


def _latest_withdrawal_end(contributions: list[dict[str, Any]]) -> datetime | None:
    return max(
        (datetime.fromisoformat(str(item["withdrawal_ends_at"])) for item in contributions),
        default=None,
    )


def _blocking_contribution_id(contribution: dict[str, Any]) -> str:
    if contribution.get("origin") == FactOrigin.IMPORTED_ASSERTION.value:
        return str(contribution["imported_fact_id"])
    return str(contribution["medication_batch_id"])
