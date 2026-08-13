"""Implementação de FactProviderPort para a vertical Titan Livestock (Passo 8.0 - 9.5)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from packages.core_application.fact_service import FactProviderPort
from packages.core_domain.facts import Fact, FactSnapshot
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.dimensional_coverage import StoredCoverageContribution
from packages.livestock_application.environmental_embargo_assertion_service import (
    PropertyEnvironmentalEmbargoAssertionRepositoryPort,
)
from packages.livestock_application.establishment_qualification_service import (
    EstablishmentQualificationRepositoryPort,
    establishment_qualification_fact_type,
)
from packages.livestock_application.external_counterparty_service import (
    ExternalCounterpartyRepositoryPort,
)
from packages.livestock_application.lot_service import LotMembershipRepositoryPort
from packages.livestock_application.medication_classification_service import (
    MedicationClassificationRepositoryPort,
)
from packages.livestock_application.movement_service import (
    MovementRepositoryPort,
    PropertyStayRepositoryPort,
)
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.sanitary_campaign_service import (
    SanitaryCampaignRepositoryPort,
)
from packages.livestock_application.sanitary_requirement_service import (
    SanitaryRequirementService,
)
from packages.livestock_application.sanitary_test_coverage import (
    MedicationTreatmentRecord,
    SanitaryTestACoverageService,
    TreatmentMaterialSource,
)
from packages.livestock_application.temporal_identifier import (
    TEMPORAL_IDENTIFIER_FACT_TYPE,
    TemporalAnimalIdentifierReader,
)
from packages.livestock_application.territorial_overlap_service import (
    PropertyTerritorialOverlapAssessment,
)
from packages.livestock_application.territorial_timeline_service import (
    PropertyTerritorialTimelineAssessment,
)
from packages.livestock_application.transfer_artifact_service import (
    ReceivedTransferArtifactRepositoryPort,
)
from packages.livestock_application.treatment_service import TreatmentApplicationRepositoryPort
from packages.livestock_application.withdrawal_service import WithdrawalCalculator
from packages.livestock_domain.environmental_embargo_assertion import (
    PropertyEnvironmentalEmbargoAssertion,
)
from packages.livestock_domain.establishment_qualification_assertion import (
    AssertionStatus,
    EstablishmentQualificationAssertion,
)
from packages.livestock_domain.imported_fact import FactOrigin, ImportedLivestockFact
from packages.livestock_domain.transfer_artifact import ReceivedTransferArtifact
from packages.livestock_domain.withdrawal import WITHDRAWAL_RULE_VERSION, compute_withdrawal_ends
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

# Fato de carência consumido pela regra de elegibilidade farmacológica (Passo 9.5).
WITHDRAWAL_FACT_TYPE = "livestock.withdrawal"
HISTORY_COVERAGE_FACT_TYPE = "livestock.history_coverage"
# Fato de elegibilidade do lote, consumido pela regra de bloqueio de lote (Passo 9.6).
LOT_ELIGIBILITY_FACT_TYPE = "livestock.lot_eligibility"
IMPORTED_TREATMENT_FACT_TYPE = "livestock.treatment_applied"
EXTERNAL_COUNTERPARTY_FACT_TYPE = "livestock.external_counterparty"
ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE = "livestock.environmental_embargo.ibama"
TERRITORIAL_PRODES_FACT_TYPE = "livestock.territorial.prodes"
TERRITORIAL_DETER_FACT_TYPE = "livestock.territorial.deter"
TERRITORIAL_FUNAI_FACT_TYPE = "livestock.territorial.funai"
MOVEMENT_DERIVED_PROPERTY_STAY_FACT_TYPE = "livestock.property_stay_from_movement"
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


class CoverageContributionReaderPort(Protocol):
    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[StoredCoverageContribution]: ...


class EstablishmentQualificationAssertionReaderPort(Protocol):
    def list_by_establishment(
        self, organization_id: OrganizationId, establishment_id: TypedId
    ) -> list[EstablishmentQualificationAssertion]: ...


class TerritorialTimelineReaderPort(Protocol):
    def assess_prodes_timeline(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
        *,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> PropertyTerritorialTimelineAssessment: ...

    def assess_deter_timeline(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
        *,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> PropertyTerritorialTimelineAssessment: ...


class TerritorialOverlapReaderPort(Protocol):
    def assess_funai_overlap(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
    ) -> PropertyTerritorialOverlapAssessment: ...


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
    movement_repository: MovementRepositoryPort | None = None
    environmental_embargo_assertion_repository: (
        PropertyEnvironmentalEmbargoAssertionRepositoryPort | None
    ) = None
    territorial_timeline_service: TerritorialTimelineReaderPort | None = None
    territorial_overlap_service: TerritorialOverlapReaderPort | None = None
    withdrawal_calculator: WithdrawalCalculator | None = None
    membership_repository: LotMembershipRepositoryPort | None = None
    imported_fact_repository: ImportedFactReaderPort | None = None
    transfer_artifact_repository: ReceivedTransferArtifactRepositoryPort | None = None
    sanitary_campaign_repository: SanitaryCampaignRepositoryPort | None = None
    treatment_application_repository: TreatmentApplicationRepositoryPort | None = None
    coverage_contribution_repository: CoverageContributionReaderPort | None = None
    medication_classification_repository: MedicationClassificationRepositoryPort | None = None
    temporal_identifier_reader: TemporalAnimalIdentifierReader | None = None

    def get_snapshot_with_temporal_context(
        self,
        organization_id: OrganizationId,
        target_id: TypedId,
        *,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> FactSnapshot:
        """Obtém apenas material cuja seleção histórica é demonstrável.

        Cadastros de Animal e projeções territoriais atuais ainda não possuem leitor
        histórico verificável. A permanência só pode ser derivada de movimentos
        append-only elegíveis; a projeção mutável ``PropertyStay`` nunca é usada.
        O restante não pode integrar uma avaliação temporal como se descrevesse o
        passado; a limitação é parte do snapshot e força a Policy material a
        permanecer inconclusiva.
        """
        facts: list[Fact] = []
        limitations = ["LIVESTOCK_CURRENT_STATE_NOT_HISTORICALLY_RECONSTRUCTABLE"]

        if target_id.entity_type == "animal":
            facts.extend(
                self._imported_sanitary_facts(
                    organization_id,
                    target_id,
                    reference_time=reference_time,
                    knowledge_cutoff=knowledge_cutoff,
                )
            )
            facts.extend(
                self._dimensional_coverage_facts(
                    organization_id,
                    target_id,
                    reference_time=reference_time,
                    knowledge_cutoff=knowledge_cutoff,
                )
            )
            sanitary_fact = self._sanitary_test_a_fact(
                organization_id,
                target_id,
                reference_time=reference_time,
                knowledge_cutoff=knowledge_cutoff,
            )
            if sanitary_fact is not None:
                facts.append(sanitary_fact)
            coverage_fact = self._history_coverage_fact(
                organization_id,
                target_id,
                reference_time,
                knowledge_cutoff=knowledge_cutoff,
            )
            if coverage_fact is not None:
                facts.append(coverage_fact)

            movement_stay_fact, movement_limitation = self._movement_derived_property_stay_fact(
                organization_id,
                target_id,
                reference_time=reference_time,
                knowledge_cutoff=knowledge_cutoff,
            )
            if movement_stay_fact is not None:
                facts.append(movement_stay_fact)
            if movement_limitation is not None:
                limitations.append(movement_limitation)

            identifier_fact, identifier_limitation = self._temporal_identifier_fact(
                organization_id,
                target_id,
                reference_time=reference_time,
                knowledge_cutoff=knowledge_cutoff,
            )
            if identifier_fact is not None:
                facts.append(identifier_fact)
            if identifier_limitation is not None:
                limitations.append(identifier_limitation)

        return FactSnapshot.create(
            organization_id=organization_id,
            target_id=target_id,
            as_of=reference_time,
            facts=tuple(facts),
            reference_time=reference_time,
            knowledge_cutoff=knowledge_cutoff,
            knowledge_limitations=tuple(limitations),
        )

    def _temporal_identifier_fact(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        *,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> tuple[Fact | None, str | None]:
        if self.temporal_identifier_reader is None:
            return None, "LIVESTOCK_IDENTIFIER_HISTORY_SOURCE_UNAVAILABLE"
        selection = self.temporal_identifier_reader.select(
            organization_id,
            animal_id,
            reference_time=reference_time,
            knowledge_cutoff=knowledge_cutoff,
        )
        if selection.limitation is not None:
            return None, selection.limitation.value
        assert selection.observed_at is not None
        assert selection.recorded_at is not None
        return (
            Fact.create(
                fact_type=TEMPORAL_IDENTIFIER_FACT_TYPE,
                payload={
                    "identifiers": [
                        {
                            "identifier_id": item.identifier_id.value.hex,
                            "identifier_type": item.identifier_type.value,
                            "identifier_value": item.identifier_value,
                            "attached_event_id": item.attached_event_id.value.hex,
                            "attached_payload_digest": item.attached_payload_digest,
                        }
                        for item in selection.identifiers
                    ],
                    "supporting_event_ids": [
                        item.value.hex for item in selection.supporting_event_ids
                    ],
                    "supporting_payload_digests": list(selection.supporting_payload_digests),
                    "derivation": "ANIMAL_IDENTIFIER_EVENT_LIFECYCLE_V1",
                },
                observed_at=selection.observed_at,
                recorded_at=selection.recorded_at,
            ),
            None,
        )

    def _movement_derived_property_stay_fact(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        *,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> tuple[Fact | None, str | None]:
        """Deriva permanência de movimentos append-only conhecidos no corte."""
        if self.movement_repository is None:
            return None, "LIVESTOCK_MOVEMENT_HISTORY_SOURCE_UNAVAILABLE"
        movements = [
            movement
            for movement in self.movement_repository.list_by_animal(animal_id)
            if movement.organization_id == organization_id
            and movement.movement_time <= reference_time
            and movement.created_at <= knowledge_cutoff
        ]
        if not movements:
            return None, "LIVESTOCK_MOVEMENT_HISTORY_ABSENT_AT_CONTEXT"

        movements.sort(key=lambda item: (item.movement_time, item.movement_id.value.hex))
        if any(
            current.movement_time == previous.movement_time
            or current.origin_property_id != previous.destination_property_id
            for previous, current in zip(movements[:-1], movements[1:], strict=True)
        ):
            return None, "LIVESTOCK_MOVEMENT_HISTORY_CONFLICT"

        latest = movements[-1]
        return (
            Fact.create(
                fact_type=MOVEMENT_DERIVED_PROPERTY_STAY_FACT_TYPE,
                payload={
                    "property_id": latest.destination_property_id.value.hex,
                    "source_movement_id": latest.movement_id.value.hex,
                    "supporting_movement_ids": [
                        movement.movement_id.value.hex for movement in movements
                    ],
                    "movement_time": latest.movement_time.isoformat(),
                    "derivation": "APPEND_ONLY_MOVEMENT_SEQUENCE_V1",
                },
                observed_at=latest.movement_time,
                # ``created_at`` é o único instante de registro hoje preservado
                # pelo movimento; não o promovemos a known_at.
                recorded_at=latest.created_at,
            ),
            None,
        )

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
                fact_list.extend(self._imported_sanitary_facts(organization_id, target_id))
                coverage_fact = self._history_coverage_fact(organization_id, target_id, at_time)
                if coverage_fact is not None:
                    fact_list.append(coverage_fact)

                property_id = None
                if self.stay_repository is not None:
                    active_stay = self.stay_repository.get_active_stay(target_id)
                    if active_stay is not None:
                        property_id = active_stay.property_id
                if property_id is None:
                    property_id = animal.birth_property_id
                embargo_assertion = self._latest_environmental_embargo_assertion(
                    organization_id,
                    property_id,
                    at_time,
                )
                if embargo_assertion is not None:
                    fact_list.append(
                        Fact.create(
                            fact_type=ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE,
                            payload={
                                "assertion_id": embargo_assertion.assertion_id.value.hex,
                                "property_id": embargo_assertion.property_id.value.hex,
                                "geometry_id": (
                                    None
                                    if embargo_assertion.geometry_id is None
                                    else embargo_assertion.geometry_id.value.hex
                                ),
                                "geometry_version": embargo_assertion.geometry_version,
                                "status": embargo_assertion.status.value,
                                "source_name": embargo_assertion.source_name,
                                "source_layer": embargo_assertion.source_layer,
                                "operation": embargo_assertion.operation,
                                "restriction_count": embargo_assertion.restriction_count,
                                "version_ids": list(embargo_assertion.version_ids),
                                "response_digest": embargo_assertion.response_digest,
                            },
                            observed_at=embargo_assertion.observed_at,
                        )
                    )
                if property_id is not None and self.territorial_timeline_service is not None:
                    for fact_type, assessment in (
                        (
                            TERRITORIAL_PRODES_FACT_TYPE,
                            self.territorial_timeline_service.assess_prodes_timeline(
                                organization_id,
                                property_id,
                            ),
                        ),
                        (
                            TERRITORIAL_DETER_FACT_TYPE,
                            self.territorial_timeline_service.assess_deter_timeline(
                                organization_id,
                                property_id,
                            ),
                        ),
                    ):
                        fact_list.append(
                            Fact.create(
                                fact_type=fact_type,
                                payload=_territorial_timeline_payload(assessment),
                                observed_at=at_time,
                            )
                        )
                if property_id is not None and self.territorial_overlap_service is not None:
                    overlap_assessment = self.territorial_overlap_service.assess_funai_overlap(
                        organization_id,
                        property_id,
                    )
                    fact_list.append(
                        Fact.create(
                            fact_type=TERRITORIAL_FUNAI_FACT_TYPE,
                            payload=_territorial_overlap_payload(overlap_assessment),
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

    def _history_coverage_fact(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        at_time: datetime,
        *,
        knowledge_cutoff: datetime | None = None,
    ) -> Fact | None:
        if self.transfer_artifact_repository is None:
            return None
        artifacts = [
            artifact
            for artifact in self.transfer_artifact_repository.list_by_animal(animal_id)
            if artifact.organization_id == organization_id
            and artifact.transfer_effective_at <= at_time
            and (knowledge_cutoff is None or artifact.created_at <= knowledge_cutoff)
        ]
        if not artifacts:
            return None
        artifact = max(artifacts, key=lambda item: item.transfer_effective_at)
        return Fact.create(
            fact_type=HISTORY_COVERAGE_FACT_TYPE,
            payload=_history_coverage_payload(artifact),
            observed_at=artifact.transfer_effective_at,
            recorded_at=artifact.created_at,
            known_at=artifact.created_at,
        )

    def _dimensional_coverage_facts(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        *,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> list[Fact]:
        """Expõe somente declarações dimensionais já conhecidas no corte.

        Cada contribuição mantém sua identidade e proveniência. A composição em
        cobertura suficiente pertence ao contrato de Policy e será feita pelo
        próximo corte; este leitor não transforma uma declaração isolada em
        cobertura completa.
        """
        if self.coverage_contribution_repository is None:
            return []
        facts: list[Fact] = []
        for item in self.coverage_contribution_repository.list_by_subject(
            organization_id, animal_id
        ):
            if item.known_at is None or item.known_at > knowledge_cutoff:
                continue
            contribution = item.contribution
            if contribution.covered_from > reference_time:
                continue
            facts.append(
                Fact.create(
                    fact_type="livestock.dimensional_coverage_contribution",
                    payload={
                        "contribution_id": item.contribution_id.value.hex,
                        "dimension": contribution.dimension,
                        "covered_from": contribution.covered_from.isoformat(),
                        "covered_until": contribution.covered_until.isoformat(),
                        "validation": contribution.validation.value,
                        "admissibility": contribution.admissibility.value,
                        "accessible": contribution.accessible,
                        "conflicting": contribution.conflicting,
                    },
                    observed_at=contribution.covered_from,
                    recorded_at=item.recorded_at,
                    known_at=item.known_at,
                    source_reference=contribution.source_reference,
                )
            )
        return facts

    def _sanitary_test_a_fact(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        *,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> Fact | None:
        """Compõe o único contrato sanitário controlado do NEXT-01.

        Não existe inferência de ausência de tratamento: se material ou
        classificação não forem suficientes, o fato não terá a chave conclusiva
        e a Rule correspondente retornará INDETERMINADA.
        """
        if (
            self.coverage_contribution_repository is None
            or self.imported_fact_repository is None
            or self.medication_classification_repository is None
        ):
            return None
        contributions = tuple(
            item.contribution
            for item in self.coverage_contribution_repository.list_by_subject(
                organization_id, animal_id
            )
            if item.known_at is not None and item.known_at <= knowledge_cutoff
        )
        treatments: list[MedicationTreatmentRecord] = []
        medication_ids: set[TypedId] = set()
        for imported in self.imported_fact_repository.list_by_animal(organization_id, animal_id):
            if imported.fact_type != IMPORTED_TREATMENT_FACT_TYPE:
                continue
            if imported.imported_at > knowledge_cutoff:
                continue
            raw_medication_id = imported.payload.get("medication_id")
            if not isinstance(raw_medication_id, str):
                continue
            try:
                medication_id = TypedId.parse("medication", raw_medication_id)
            except ValueError:
                continue
            treatments.append(
                MedicationTreatmentRecord(
                    medication_id=medication_id,
                    occurred_at=imported.occurred_at,
                    source=TreatmentMaterialSource.IMPORTED_DOCUMENTED,
                    source_artifact_id=imported.source_artifact_id.value.hex,
                )
            )
            medication_ids.add(medication_id)
        classifications = tuple(
            assertion
            for medication_id in medication_ids
            for assertion in self.medication_classification_repository.list_by_medication(
                organization_id, medication_id
            )
        )
        return SanitaryTestACoverageService().build_fact_from_classified_material(
            reference_time=reference_time,
            contributions=contributions,
            treatments=tuple(treatments),
            classifications=classifications,
            knowledge_cutoff=knowledge_cutoff,
        )

    def _latest_environmental_embargo_assertion(
        self,
        organization_id: OrganizationId,
        property_id: TypedId | None,
        at_time: datetime,
    ) -> PropertyEnvironmentalEmbargoAssertion | None:
        if property_id is None or self.environmental_embargo_assertion_repository is None:
            return None
        assertions = self.environmental_embargo_assertion_repository.list_by_property(
            organization_id,
            property_id,
        )
        known_assertions = [item for item in assertions if item.recorded_at <= at_time]
        if not known_assertions:
            return None
        return max(known_assertions, key=lambda item: item.observed_at)

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

    def _imported_sanitary_facts(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        *,
        reference_time: datetime | None = None,
        knowledge_cutoff: datetime | None = None,
    ) -> list[Fact]:
        if self.imported_fact_repository is None:
            return []
        facts: list[Fact] = []
        for imported_fact in self.imported_fact_repository.list_by_animal(
            organization_id, animal_id
        ):
            if reference_time is not None and imported_fact.occurred_at > reference_time:
                continue
            if knowledge_cutoff is not None and imported_fact.imported_at > knowledge_cutoff:
                continue
            facts.append(
                Fact.create(
                    fact_type=imported_fact.fact_type,
                    payload={
                        **dict(imported_fact.payload),
                        "imported_fact_id": imported_fact.imported_fact_id.value.hex,
                        "source_artifact_id": imported_fact.source_artifact_id.value.hex,
                        "asserted_by": imported_fact.asserted_by,
                        "received_by": imported_fact.received_by.value.hex,
                        "origin": imported_fact.origin.value,
                        "confidence_tier": imported_fact.confidence_tier.value,
                    },
                    observed_at=imported_fact.occurred_at,
                    source_reference=UniversalReference(
                        target_id=imported_fact.source_artifact_id,
                        organization_id=organization_id,
                        contract_version=1,
                    ),
                    recorded_at=imported_fact.imported_at,
                    known_at=imported_fact.imported_at,
                )
            )
        return facts


def _latest_withdrawal_end(contributions: list[dict[str, Any]]) -> datetime | None:
    return max(
        (datetime.fromisoformat(str(item["withdrawal_ends_at"])) for item in contributions),
        default=None,
    )


def _blocking_contribution_id(contribution: dict[str, Any]) -> str:
    if contribution.get("origin") == FactOrigin.IMPORTED_ASSERTION.value:
        return str(contribution["imported_fact_id"])
    return str(contribution["medication_batch_id"])


def _territorial_timeline_payload(
    assessment: PropertyTerritorialTimelineAssessment,
) -> dict[str, Any]:
    years = list(assessment.years)
    total_feature_count = sum(
        feature_count
        for item in years
        if isinstance(feature_count := item.get("feature_count"), int)
    )
    occurrence_years = [
        year
        for item in years
        if isinstance(year := item.get("year"), int) and item["feature_count"]
    ]
    return {
        "property_id": assessment.property_id.value.hex,
        "geometry_id": (
            None if assessment.geometry_id is None else assessment.geometry_id.value.hex
        ),
        "geometry_version": assessment.geometry_version,
        "external_reference": assessment.external_reference,
        "status": assessment.status.value,
        "source": assessment.source,
        "layer": assessment.layer,
        "property_area_hectares": assessment.property_area_hectares,
        "year_from": assessment.year_from,
        "year_to": assessment.year_to,
        "year_count": len(years),
        "total_feature_count": total_feature_count,
        "has_occurrence": total_feature_count > 0,
        "occurrence_years": occurrence_years,
        "years": years,
        "response_digest": assessment.response_digest,
        "gaps": [gap.to_dict() for gap in assessment.gaps],
    }


def _territorial_overlap_payload(
    assessment: PropertyTerritorialOverlapAssessment,
) -> dict[str, Any]:
    return {
        "property_id": assessment.property_id.value.hex,
        "geometry_id": (
            None if assessment.geometry_id is None else assessment.geometry_id.value.hex
        ),
        "geometry_version": assessment.geometry_version,
        "external_reference": assessment.external_reference,
        "status": assessment.status.value,
        "source": assessment.source,
        "layer": assessment.layer,
        "label": assessment.label,
        "feature_count": assessment.feature_count,
        "has_overlap": assessment.feature_count > 0,
        "area_hectares": assessment.area_hectares,
        "source_area_hectares": assessment.source_area_hectares,
        "version_ids": list(assessment.version_ids),
        "response_digest": assessment.response_digest,
        "gaps": [gap.to_dict() for gap in assessment.gaps],
    }


def _history_coverage_payload(artifact: ReceivedTransferArtifact) -> dict[str, Any]:
    coverage = artifact.coverage
    return {
        "source_artifact_id": artifact.artifact_id.value.hex,
        "source_counterparty_id": artifact.source_counterparty_id.value.hex,
        "basis": "received_transfer_artifact",
        "known_from": None if coverage.known_from is None else coverage.known_from.isoformat(),
        "known_until": None if coverage.known_until is None else coverage.known_until.isoformat(),
        "transfer_effective_at": artifact.transfer_effective_at.isoformat(),
        "has_declared_gaps": len(coverage.gaps) > 0,
        "coverage_status": "PARTIAL_DECLARED" if coverage.gaps else "DECLARED",
        "gaps": [
            {
                "code": gap.code.value,
                "starts_at": None if gap.starts_at is None else gap.starts_at.isoformat(),
                "ends_at": None if gap.ends_at is None else gap.ends_at.isoformat(),
                "description": gap.description,
            }
            for gap in coverage.gaps
        ],
    }
