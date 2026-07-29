"""Implementação de FactProviderPort para a vertical Titan Livestock (Passo 8.0 - 9.5)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from packages.core_application.fact_service import FactProviderPort
from packages.core_domain.facts import Fact, FactSnapshot
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.establishment_qualification_service import (
    EstablishmentQualificationRepositoryPort,
    establishment_qualification_fact_type,
)
from packages.livestock_application.external_counterparty_service import (
    ExternalCounterpartyRepositoryPort,
)
from packages.livestock_application.lot_service import LotMembershipRepositoryPort
from packages.livestock_application.movement_service import PropertyStayRepositoryPort
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.sanitary_campaign_service import (
    SanitaryCampaignRepositoryPort,
)
from packages.livestock_application.sanitary_requirement_service import (
    SanitaryRequirementService,
)
from packages.livestock_application.treatment_service import TreatmentApplicationRepositoryPort
from packages.livestock_application.withdrawal_service import WithdrawalCalculator
from packages.livestock_domain.establishment_qualification_assertion import (
    AssertionStatus,
    EstablishmentQualificationAssertion,
)
from packages.livestock_domain.imported_fact import FactOrigin, ImportedLivestockFact
from packages.livestock_domain.withdrawal import WITHDRAWAL_RULE_VERSION, compute_withdrawal_ends
from packages.shared_kernel import OrganizationId, TypedId

# Fato de carência consumido pela regra de elegibilidade farmacológica (Passo 9.5).
WITHDRAWAL_FACT_TYPE = "livestock.withdrawal"
# Fato de elegibilidade do lote, consumido pela regra de bloqueio de lote (Passo 9.6).
LOT_ELIGIBILITY_FACT_TYPE = "livestock.lot_eligibility"
IMPORTED_TREATMENT_FACT_TYPE = "livestock.treatment_applied"
EXTERNAL_COUNTERPARTY_FACT_TYPE = "livestock.external_counterparty"
# Sem limite de paginação real na leitura para fatos: uma campanha sanitária
# que exista e não seja lida aqui produziria uma matriz que finge que aquela
# campanha nunca foi exigida — pior que uma consulta um pouco mais cara.
_SANITARY_CAMPAIGNS_MAX = 1000


def sanitary_requirement_fact_type(campaign_code: str) -> str:
    """Nome do fato para a exigibilidade de uma campanha sanitária específica.

    Uma regra governada por mercado (Item 4 da fila) referencia este fato na
    sua `RuleCondition`, exatamente como `ESTABLISHMENT_RULE_CODE` já referencia
    `establishment_qualification_fact_type`. Qual campanha cada mercado exige é
    decisão de quem governa a regra, não deste fato.
    """
    sufixo = campaign_code.strip().lower().replace(".", "_")
    return f"livestock.sanitary_requirement.{sufixo}"


class ImportedFactReaderPort(Protocol):
    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[ImportedLivestockFact]: ...


class EstablishmentQualificationAssertionReaderPort(Protocol):
    def list_by_establishment(
        self, organization_id: OrganizationId, establishment_id: TypedId
    ) -> list[EstablishmentQualificationAssertion]: ...


@dataclass(frozen=True, slots=True)
class LivestockFactProvider(FactProviderPort):
    property_repository: RuralPropertyRepositoryPort
    animal_repository: AnimalRepositoryPort
    external_counterparty_repository: ExternalCounterpartyRepositoryPort | None = None
    establishment_qualification_repository: EstablishmentQualificationRepositoryPort | None = None
    establishment_qualification_assertion_repository: (
        EstablishmentQualificationAssertionReaderPort | None
    ) = None
    stay_repository: PropertyStayRepositoryPort | None = None
    withdrawal_calculator: WithdrawalCalculator | None = None
    membership_repository: LotMembershipRepositoryPort | None = None
    imported_fact_repository: ImportedFactReaderPort | None = None
    sanitary_campaign_repository: SanitaryCampaignRepositoryPort | None = None
    treatment_application_repository: TreatmentApplicationRepositoryPort | None = None

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

                if (
                    self.sanitary_campaign_repository is not None
                    and self.treatment_application_repository is not None
                ):
                    requirement_service = SanitaryRequirementService(
                        animal_repository=self.animal_repository,
                        campaign_repository=self.sanitary_campaign_repository,
                        application_repository=self.treatment_application_repository,
                    )
                    campanhas = self.sanitary_campaign_repository.list_by_organization(
                        organization_id, limit=_SANITARY_CAMPAIGNS_MAX
                    )
                    for campanha in campanhas:
                        avaliacao = requirement_service.assess_required_campaign(
                            organization_id, target_id, campanha.code
                        )
                        fact_list.append(
                            Fact.create(
                                fact_type=sanitary_requirement_fact_type(campanha.code),
                                payload={
                                    "status": avaliacao.status.value,
                                    "campaign_id": (
                                        None
                                        if avaliacao.campaign_id is None
                                        else avaliacao.campaign_id.value.hex
                                    ),
                                    "application_id": (
                                        None
                                        if avaliacao.application_id is None
                                        else avaliacao.application_id.value.hex
                                    ),
                                },
                                observed_at=at_time,
                            )
                        )

        elif target_id.entity_type == "external_counterparty":
            if self.external_counterparty_repository is not None:
                counterparty = self.external_counterparty_repository.get_by_id(target_id)
                if counterparty is not None and counterparty.organization_id == organization_id:
                    identifier_types = tuple(
                        identifier.split(":", 1)[0].strip().upper()
                        for identifier in counterparty.identifiers
                        if ":" in identifier
                    )
                    fact_list.append(
                        Fact.create(
                            fact_type=EXTERNAL_COUNTERPARTY_FACT_TYPE,
                            payload={
                                "name": counterparty.name,
                                "counterparty_type": counterparty.counterparty_type.value,
                                "identifiers": list(counterparty.identifiers),
                                "identifier_types": list(identifier_types),
                                "has_sif_identifier": "SIF" in identifier_types,
                            },
                            observed_at=at_time,
                        )
                    )
                    if self.establishment_qualification_assertion_repository is not None:
                        latest_assertion_by_type: dict[
                            str, EstablishmentQualificationAssertion
                        ] = {}
                        assertion_repository = self.establishment_qualification_assertion_repository
                        assertions = assertion_repository.list_by_establishment(
                            organization_id, target_id
                        )
                        for assertion in assertions:
                            if not assertion.known_as_of(at_time):
                                continue
                            previous_assertion = latest_assertion_by_type.get(
                                assertion.qualification_type
                            )
                            if (
                                previous_assertion is None
                                or assertion.observed_at >= previous_assertion.observed_at
                            ):
                                latest_assertion_by_type[assertion.qualification_type] = assertion
                        for assertion in latest_assertion_by_type.values():
                            fact_list.append(
                                Fact.create(
                                    fact_type=establishment_qualification_fact_type(
                                        assertion.qualification_type
                                    ),
                                    payload={
                                        "qualification_status": (
                                            "HABILITADO"
                                            if assertion.asserted_status
                                            is AssertionStatus.QUALIFIED
                                            else "NAO_HABILITADO"
                                        ),
                                        "asserted_status": assertion.asserted_status.value,
                                        "source_artifact_id": str(
                                            assertion.source_artifact_id.value
                                        ),
                                        "confidence_tier": assertion.confidence_tier.value,
                                    },
                                    observed_at=assertion.observed_at,
                                )
                            )
                    elif self.establishment_qualification_repository is not None:
                        latest_by_market: dict[str, Any] = {}
                        qualifications = (
                            self.establishment_qualification_repository.list_by_counterparty(
                                organization_id,
                                target_id,
                            )
                        )
                        for qualification in qualifications:
                            if qualification.assessed_at > at_time:
                                continue
                            previous = latest_by_market.get(qualification.market_purpose)
                            if (
                                previous is None
                                or qualification.assessed_at >= previous.assessed_at
                            ):
                                latest_by_market[qualification.market_purpose] = qualification
                        for qualification in latest_by_market.values():
                            fact_list.append(
                                Fact.create(
                                    fact_type=establishment_qualification_fact_type(
                                        qualification.market_purpose
                                    ),
                                    payload={
                                        "qualification_status": qualification.status.value,
                                        "source_name": qualification.source_name,
                                        "source_version": qualification.source_version,
                                    },
                                    observed_at=qualification.assessed_at,
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
