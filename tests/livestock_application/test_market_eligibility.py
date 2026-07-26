"""Testes da matriz de elegibilidade por mercado (ADR-0044)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.core_domain.decision import DecisionReason, DecisionReasonCode, DecisionResult
from packages.core_domain.rule_governance import RuleAdoption
from packages.livestock_application.eligibility import ELIGIBILITY_RULE_ADOPTION_SCOPE
from packages.livestock_application.market_eligibility import (
    MarketEligibilityGapCode,
    MarketEligibilityService,
    MarketEligibilityStatus,
    MarketProfile,
    MarketRequirement,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@dataclass
class InMemoryAdoptions:
    items: dict[tuple[OrganizationId, str, str, str], RuleAdoption] = field(default_factory=dict)

    def add(self, organization_id: OrganizationId, code: str, purpose: str) -> RuleAdoption:
        adoption = RuleAdoption(
            adoption_id=TypedId.new("rule_adoption"),
            organization_id=organization_id,
            rule_identity_id=TypedId.new("rule_identity"),
            rule_version_id=TypedId.new("rule"),
            purpose=purpose,
            scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
            adopted_by=UniversalReference(
                target_id=TypedId.new("actor"),
                organization_id=organization_id,
                contract_version=1,
            ),
            adopted_at=datetime.now(UTC),
            reason="Regra adotada para o mercado.",
            status="active",
        )
        self.items[(organization_id, code, purpose, ELIGIBILITY_RULE_ADOPTION_SCOPE)] = adoption
        return adoption

    def get_active_by_code_purpose_and_scope(
        self,
        organization_id: OrganizationId,
        code: str,
        purpose: str,
        scope: str,
    ) -> RuleAdoption | None:
        return self.items.get((organization_id, code, purpose, scope))


def _reason(message: str = "Animal em carencia.") -> DecisionReason:
    return DecisionReason(
        code=DecisionReasonCode.REGRA_NAO_ATENDIDA,
        message=message,
        rule_code="rule-carencia-farmacologica",
        rule_id=TypedId.new("rule"),
        rule_version=1,
    )


def test_market_without_adopted_rule_is_absent() -> None:
    org_id = OrganizationId.new()

    matrix = MarketEligibilityService(
        adoption_reader=InMemoryAdoptions(),
        profiles=(
            MarketProfile(
                market="exportacao-uniao-europeia",
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
            ),
        ),
    ).evaluate(org_id, DecisionResult.APROVADA, [_reason("Regra atendida.")])

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.AUSENTE
    assert entry.governed_rule is None
    assert entry.reasons == ()
    assert entry.gaps[0].code is MarketEligibilityGapCode.REGRA_GOVERNADA_AUSENTE
    assert entry.requirements[0].rule_code == "rule-carencia-farmacologica"
    assert entry.requirements[0].status is MarketEligibilityStatus.AUSENTE


def test_adopted_market_maps_rejected_decision_to_not_eligible() -> None:
    org_id = OrganizationId.new()
    adoptions = InMemoryAdoptions()
    adoption = adoptions.add(
        org_id,
        "rule-carencia-farmacologica",
        "exportacao-uniao-europeia",
    )

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        profiles=(
            MarketProfile(
                market="exportacao-uniao-europeia",
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
            ),
        ),
    ).evaluate(org_id, DecisionResult.REJEITADA, [_reason()])

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.NAO_ELEGIVEL
    assert entry.governed_rule is not None
    assert entry.governed_rule.adoption_id == adoption.adoption_id
    assert entry.reasons[0].code == "regra_nao_atendida"
    assert entry.reasons[0].message == "Animal em carencia."
    assert entry.reasons[0].rule_code == "rule-carencia-farmacologica"
    assert entry.gaps == ()
    assert entry.requirements[0].governed_rule is not None


def test_adopted_markets_can_differ_side_by_side() -> None:
    org_id = OrganizationId.new()
    adoptions = InMemoryAdoptions()
    adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-china")
    adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-estados-unidos")

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        profiles=(
            MarketProfile(
                market="exportacao-uniao-europeia",
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
            ),
            MarketProfile(
                market="exportacao-china",
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
            ),
            MarketProfile(
                market="exportacao-estados-unidos",
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
            ),
        ),
    ).evaluate(org_id, DecisionResult.APROVADA, [_reason("Regra atendida.")])

    statuses = {entry.market: entry.status for entry in matrix.entries}
    assert statuses == {
        "exportacao-uniao-europeia": MarketEligibilityStatus.AUSENTE,
        "exportacao-china": MarketEligibilityStatus.ELEGIVEL,
        "exportacao-estados-unidos": MarketEligibilityStatus.ELEGIVEL,
    }


def test_market_with_multiple_requirements_fails_when_any_requirement_is_absent() -> None:
    org_id = OrganizationId.new()
    adoptions = InMemoryAdoptions()
    adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-uniao-europeia")

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        profiles=(
            MarketProfile(
                market="exportacao-uniao-europeia",
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                    MarketRequirement(
                        rule_code="rule-rastreabilidade-minima",
                        scope="livestock.animal",
                    ),
                ),
            ),
        ),
    ).evaluate(org_id, DecisionResult.APROVADA, [_reason("Regra atendida.")])

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.AUSENTE
    assert [requirement.rule_code for requirement in entry.requirements] == [
        "rule-carencia-farmacologica",
        "rule-rastreabilidade-minima",
    ]
    assert entry.requirements[0].status is MarketEligibilityStatus.ELEGIVEL
    assert entry.requirements[1].status is MarketEligibilityStatus.AUSENTE
