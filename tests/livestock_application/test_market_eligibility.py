"""Testes da matriz de elegibilidade por mercado (ADR-0044)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast

from packages.core_domain.decision import (
    Decision,
    DecisionReason,
    DecisionReasonCode,
    DecisionResult,
)
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.decision_governance import (
    ContestationRecord,
    DecisionOverride,
    DecisionProposal,
    DecisionReview,
)
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.normative import (
    NormativeBasisSnapshot,
    NormativeReferenceSnapshot,
    NormativeSourceClassification,
)
from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.core_domain.rule_governance import RuleAdoption, RuleAdoptionStatus
from packages.livestock_application.eligibility import (
    ELIGIBILITY_RULE_ADOPTION_SCOPE,
    ELIGIBILITY_RULE_CODE,
    HumanReviewRequired,
)
from packages.livestock_application.establishment_qualification_service import (
    establishment_qualification_fact_type,
)
from packages.livestock_application.fact_provider import (
    ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE,
    TERRITORIAL_FUNAI_FACT_TYPE,
    TERRITORIAL_PRODES_FACT_TYPE,
)
from packages.livestock_application.market_eligibility import (
    DEFAULT_MARKET_PROFILES,
    ENVIRONMENTAL_EMBARGO_RULE_CODE,
    ESTABLISHMENT_RULE_CODE,
    TERRITORIAL_FUNAI_RULE_CODE,
    TERRITORIAL_PRODES_RULE_CODE,
    TRACEABILITY_RULE_CODE,
    MarketEligibilityGapCode,
    MarketEligibilityPurpose,
    MarketEligibilityService,
    MarketEligibilityStatus,
    MarketProfile,
    MarketRequirement,
    MarketWithdrawalBasis,
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
            status=RuleAdoptionStatus.ACTIVE,
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


@dataclass
class InMemoryRules:
    items: dict[TypedId, Rule] = field(default_factory=dict)

    def add_from_adoption(
        self,
        adoption: RuleAdoption,
        *,
        code: str,
        version: int = 1,
        justification: str = "Destino comercial exige carencia cumprida.",
        corrective_action: str = "Aguardar fim da carencia.",
    ) -> Rule:
        rule = Rule(
            rule_id=adoption.rule_version_id,
            policy_id=TypedId.new("policy"),
            organization_id=adoption.organization_id,
            code=code,
            name="Carencia farmacologica",
            description="Regra ficticia de mercado.",
            version=version,
            severity=SeverityLevel.BLOCKING,
            normative_source="politica interna ficticia",
            conditions=(
                RuleCondition(
                    fact_type="livestock.withdrawal",
                    payload_key="in_withdrawal",
                    operator=ComparisonOperator.EQUALS,
                    expected_value=False,
                    description="Animal nao pode estar em carencia.",
                ),
            ),
            justification=justification,
            corrective_action=corrective_action,
        )
        self.items[rule.rule_id] = rule
        return rule

    def get_by_id(self, rule_id: object) -> Rule | None:
        if not isinstance(rule_id, TypedId):
            return None
        return self.items.get(rule_id)


@dataclass
class InMemoryPolicies:
    items: dict[TypedId, Policy] = field(default_factory=dict)
    by_code: dict[tuple[OrganizationId, str], Policy] = field(default_factory=dict)

    def add_from_rule(self, rule: Rule) -> Policy:
        policy = Policy(
            policy_id=rule.policy_id,
            organization_id=rule.organization_id,
            code=f"policy-{rule.code}-{rule.rule_id.value.hex}",
            name="Policy ficticia de mercado",
            description="Policy ficticia para regra governada.",
            version=1,
            status=PolicyStatus.PUBLISHED,
            published_at=datetime.now(UTC) - timedelta(days=1),
        )
        self.items[policy.policy_id] = policy
        self.by_code[(policy.organization_id, policy.code)] = policy
        return policy

    def get_by_id(self, policy_id: TypedId) -> Policy | None:
        return self.items.get(policy_id)

    def get_active_at(
        self, organization_id: OrganizationId, code: str, at_time: datetime
    ) -> Policy | None:
        _ = at_time
        return self.by_code.get((organization_id, code))

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Policy]:
        return [item for item in self.items.values() if item.organization_id == organization_id][
            offset : offset + limit
        ]


@dataclass
class InMemoryFactProvider:
    def get_snapshot(
        self, organization_id: OrganizationId, target_id: TypedId, at_time: datetime
    ) -> FactSnapshot:
        if target_id.entity_type == "external_counterparty":
            return FactSnapshot.create(
                organization_id=organization_id,
                target_id=target_id,
                as_of=at_time,
                facts=(
                    Fact.create(
                        fact_type=establishment_qualification_fact_type("exportacao-china"),
                        payload={
                            "qualification_status": "HABILITADO",
                        },
                        observed_at=at_time,
                    ),
                ),
            )
        return FactSnapshot.create(
            organization_id=organization_id,
            target_id=target_id,
            as_of=at_time,
            facts=(
                Fact.create(
                    fact_type="livestock.treatment_applied",
                    payload={"source": "teste"},
                    observed_at=at_time,
                ),
                Fact.create(
                    fact_type="livestock.withdrawal",
                    payload={"in_withdrawal": False},
                    observed_at=at_time,
                ),
                Fact.create(
                    fact_type=ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE,
                    payload={"status": "SEM_RESTRICAO", "restriction_count": 0},
                    observed_at=at_time,
                ),
            ),
        )


@dataclass
class InMemoryEvaluations:
    saved: list[object] = field(default_factory=list)

    def save(self, evaluation: object) -> None:
        self.saved.append(evaluation)


@dataclass
class InMemoryDecisions:
    saved: list[object] = field(default_factory=list)

    def save(self, decision: object) -> None:
        self.saved.append(decision)


@dataclass
class InMemoryNormativeSnapshotProvider:
    def select(
        self,
        *,
        policy: Policy,
        rules: tuple[Rule, ...],
        purpose: str,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> NormativeBasisSnapshot:
        return NormativeBasisSnapshot(
            schema_version=1,
            normative_basis_id=TypedId.new("normative_basis"),
            normative_basis_code="MARKET_TEST_CONTROLLED_BASIS",
            normative_basis_version=1,
            policy_id=policy.policy_id,
            policy_code=policy.code,
            policy_version=policy.version,
            rule_versions=tuple((rule.code, rule.version) for rule in rules),
            purpose=purpose,
            jurisdiction="INTERNAL_TEST",
            intended_use="INTERNAL_TEST_ONLY",
            reference_time=reference_time,
            knowledge_cutoff=knowledge_cutoff,
            approved_by="SYSTEM:TEST",
            approval_authority="INTERNAL_TEST_ONLY",
            approved_at=policy.published_at or reference_time,
            references=(
                NormativeReferenceSnapshot(
                    instrument_code="MARKET-TEST-CONTROLLED",
                    instrument_version="1",
                    provision="test",
                    content_digest="a" * 64,
                    digest_algorithm="sha256",
                    source_classification=NormativeSourceClassification.INTERNAL_TEST,
                ),
            ),
            limitations=("RECOGNITION_BOUNDARY:INTERNAL_ONLY",),
        )


@dataclass
class InMemoryDecisionGovernanceRepo:
    proposals: list[DecisionProposal] = field(default_factory=list)

    def save_proposal(self, proposal: DecisionProposal) -> None:
        self.proposals.append(proposal)

    def get_proposal(self, proposal_id: TypedId) -> DecisionProposal | None:
        return next(
            (proposal for proposal in self.proposals if proposal.proposal_id == proposal_id),
            None,
        )

    def save_review(self, review: DecisionReview) -> None:
        raise AssertionError("nao deveria registrar review neste teste")

    def get_review(self, review_id: TypedId) -> DecisionReview | None:
        return None

    def list_reviews_by_proposal(self, proposal_id: TypedId) -> list[DecisionReview]:
        return []

    def save_override(self, override: DecisionOverride) -> None:
        raise AssertionError("nao deveria registrar override neste teste")

    def get_override(self, override_id: TypedId) -> DecisionOverride | None:
        return None

    def save_contestation(self, contestation: ContestationRecord) -> None:
        raise AssertionError("nao deveria registrar contestacao neste teste")

    def get_contestation(self, contestation_id: TypedId) -> ContestationRecord | None:
        return None


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
        rule_reader=InMemoryRules(),
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA,
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


def test_adopted_market_without_declared_withdrawal_is_indeterminate() -> None:
    org_id = OrganizationId.new()
    adoptions = InMemoryAdoptions()
    adoption = adoptions.add(
        org_id,
        "rule-carencia-farmacologica",
        "exportacao-uniao-europeia",
    )
    rules = InMemoryRules()
    rules.add_from_adoption(adoption, code="rule-carencia-farmacologica")

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=None,
            ),
        ),
    ).evaluate(org_id, DecisionResult.APROVADA, [_reason("Regra atendida.")])

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.INDETERMINADO
    assert entry.requirements[0].status is MarketEligibilityStatus.INDETERMINADO
    assert entry.requirements[0].gaps[0].code is (
        MarketEligibilityGapCode.CARENCIA_POR_MERCADO_AUSENTE
    )
    assert entry.requirements[0].adoption is not None
    assert entry.requirements[0].rule_version is not None
    assert entry.reasons == ()


def test_adopted_market_maps_rejected_decision_to_not_eligible() -> None:
    org_id = OrganizationId.new()
    adoptions = InMemoryAdoptions()
    adoption = adoptions.add(
        org_id,
        "rule-carencia-farmacologica",
        "exportacao-uniao-europeia",
    )
    rules = InMemoryRules()
    rules.add_from_adoption(adoption, code="rule-carencia-farmacologica")

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
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
    assert entry.adoption is not None
    assert entry.adoption.reason == "Regra adotada para o mercado."
    assert entry.rule_version is not None
    assert entry.rule_version.code == "rule-carencia-farmacologica"
    assert entry.rule_version.corrective_action == "Aguardar fim da carencia."
    assert entry.requirements[0].governed_rule is not None


def test_adopted_markets_can_differ_side_by_side() -> None:
    org_id = OrganizationId.new()
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    china = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-china")
    eua = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-estados-unidos")
    rules.add_from_adoption(china, code="rule-carencia-farmacologica")
    rules.add_from_adoption(eua, code="rule-carencia-farmacologica")

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=None,
            ),
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_CHINA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
            ),
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
            ),
        ),
    ).evaluate(org_id, DecisionResult.APROVADA, [_reason("Regra atendida.")])

    statuses = {entry.market.code: entry.status for entry in matrix.entries}
    assert statuses == {
        "exportacao-uniao-europeia": MarketEligibilityStatus.AUSENTE,
        "exportacao-china": MarketEligibilityStatus.ELEGIVEL,
        "exportacao-estados-unidos": MarketEligibilityStatus.ELEGIVEL,
    }


def test_market_specific_withdrawal_basis_does_not_silently_reuse_local_medication_period() -> None:
    org_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    policies = InMemoryPolicies()
    evaluations = InMemoryEvaluations()
    decisions = InMemoryDecisions()
    china = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-china")
    china_rule = rules.add_from_adoption(china, code="rule-carencia-farmacologica")
    policies.add_from_rule(china_rule)

    class LocalWithdrawalAlreadyEndedFactProvider(InMemoryFactProvider):
        def get_snapshot(
            self, organization_id: OrganizationId, target_id: TypedId, at_time: datetime
        ) -> FactSnapshot:
            return FactSnapshot.create(
                organization_id=organization_id,
                target_id=target_id,
                as_of=at_time,
                facts=(
                    Fact.create(
                        fact_type="livestock.withdrawal",
                        payload={
                            "in_withdrawal": False,
                            "eligible_from": (at_time.replace(microsecond=0)).isoformat(),
                            "contributions": [
                                {
                                    "medication_batch_id": TypedId.new(
                                        "medication_batch"
                                    ).value.hex,
                                    "applied_at": (at_time - timedelta(days=25)).isoformat(),
                                    "withdrawal_period_days": 20,
                                    "withdrawal_ends_at": (at_time - timedelta(days=5)).isoformat(),
                                    "origin": "LOCAL_OBSERVATION",
                                }
                            ],
                        },
                        observed_at=at_time,
                    ),
                ),
            )

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        policy_reader=policies,
        fact_provider=LocalWithdrawalAlreadyEndedFactProvider(),
        evaluation_repository=evaluations,
        decision_repository=decisions,
        normative_snapshot_provider=InMemoryNormativeSnapshotProvider(),
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_CHINA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                withdrawal_basis=MarketWithdrawalBasis(
                    source_kind="VERTICAL_CONFIGURATION",
                    declared_period_days=30,
                    rationale="Mercado exige prazo governado superior ao prazo tecnico local.",
                ),
            ),
        ),
    ).evaluate(
        org_id,
        subject_id=animal_id,
        at_time=datetime.now(UTC).replace(microsecond=0),
    )

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.NAO_ELEGIVEL
    assert entry.requirements[0].withdrawal_basis is not None
    assert entry.requirements[0].withdrawal_basis.declared_period_days == 30
    assert decisions.saved
    decision = cast(Decision, decisions.saved[-1])
    assert decision.result is DecisionResult.REJEITADA


def test_supported_markets_generate_independent_executions_side_by_side() -> None:
    org_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    policies = InMemoryPolicies()
    evaluations = InMemoryEvaluations()
    decisions = InMemoryDecisions()
    china = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-china")
    eua = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-estados-unidos")
    china_rule = rules.add_from_adoption(china, code="rule-carencia-farmacologica")
    eua_rule = rules.add_from_adoption(eua, code="rule-carencia-farmacologica")
    policies.add_from_rule(china_rule)
    policies.add_from_rule(eua_rule)

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        policy_reader=policies,
        fact_provider=InMemoryFactProvider(),
        evaluation_repository=evaluations,
        decision_repository=decisions,
        normative_snapshot_provider=InMemoryNormativeSnapshotProvider(),
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_CHINA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
            ),
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
            ),
        ),
    ).evaluate(
        org_id,
        subject_id=animal_id,
        at_time=datetime.now(UTC),
    )

    assert len(evaluations.saved) == 2
    assert len(decisions.saved) == 2
    assert all(
        cast(Decision, decision).emission_method is DecisionEmissionMethod.AUTOMATED
        for decision in decisions.saved
    )
    executions = [entry.requirements[0].execution for entry in matrix.entries]
    assert executions[0] is not None
    assert executions[1] is not None
    assert executions[0].evaluation_id != executions[1].evaluation_id
    assert executions[0].decision_id != executions[1].decision_id
    assert all(entry.status is MarketEligibilityStatus.ELEGIVEL for entry in matrix.entries)


def test_market_without_temporal_normative_snapshot_is_indeterminate_without_persistence() -> None:
    org_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    policies = InMemoryPolicies()
    evaluations = InMemoryEvaluations()
    decisions = InMemoryDecisions()
    adoption = adoptions.add(org_id, ELIGIBILITY_RULE_CODE, "exportacao-china")
    rule = rules.add_from_adoption(adoption, code=ELIGIBILITY_RULE_CODE)
    policies.add_from_rule(rule)

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        policy_reader=policies,
        fact_provider=InMemoryFactProvider(),
        evaluation_repository=evaluations,
        decision_repository=decisions,
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_CHINA,
                requirements=(
                    MarketRequirement(
                        rule_code=ELIGIBILITY_RULE_CODE,
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
            ),
        ),
    ).evaluate(org_id, subject_id=animal_id, at_time=datetime.now(UTC))

    requirement = matrix.entries[0].requirements[0]
    assert requirement.status is MarketEligibilityStatus.INDETERMINADO
    assert requirement.gaps[0].code is MarketEligibilityGapCode.BASE_NORMATIVA_TEMPORAL_AUSENTE
    assert requirement.execution is None
    assert evaluations.saved == []
    assert decisions.saved == []


def test_market_dependency_without_selected_subject_is_conditioned() -> None:
    org_id = OrganizationId.new()
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    carencia = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-china")
    estabelecimento = RuleAdoption(
        adoption_id=TypedId.new("rule_adoption"),
        organization_id=org_id,
        rule_identity_id=TypedId.new("rule_identity"),
        rule_version_id=TypedId.new("rule"),
        purpose="exportacao-china",
        scope="livestock.slaughterhouse",
        adopted_by=UniversalReference(
            target_id=TypedId.new("actor"),
            organization_id=org_id,
            contract_version=1,
        ),
        adopted_at=datetime.now(UTC),
        reason="Regra adotada para o estabelecimento exigido pela China.",
        status=RuleAdoptionStatus.ACTIVE,
    )
    adoptions.items[
        (
            org_id,
            ESTABLISHMENT_RULE_CODE,
            "exportacao-china",
            "livestock.slaughterhouse",
        )
    ] = estabelecimento
    rules.add_from_adoption(carencia, code="rule-carencia-farmacologica")
    rules.add_from_adoption(
        estabelecimento,
        code=ESTABLISHMENT_RULE_CODE,
        justification="Frigorifico precisa estar habilitado.",
        corrective_action="Selecionar e comprovar o estabelecimento habilitado.",
    )

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        profiles=(DEFAULT_MARKET_PROFILES[1],),
    ).evaluate(org_id, DecisionResult.APROVADA, [_reason("Regra atendida.")])

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.INDETERMINADO
    assert entry.dependency is not None
    assert entry.dependency.subject_key == "slaughterhouse"
    assert entry.dependency.subject_label == "estabelecimento"
    assert entry.dependency.selected_subject_id is None
    assert entry.requirements[0].status is MarketEligibilityStatus.INDETERMINADO
    assert entry.requirements[0].gaps[0].code is (
        MarketEligibilityGapCode.CARENCIA_POR_MERCADO_AUSENTE
    )
    assert entry.requirements[1].rule_code == ESTABLISHMENT_RULE_CODE
    assert entry.requirements[1].status is MarketEligibilityStatus.CONDICIONADO
    assert entry.requirements[1].dependency is not None
    assert entry.requirements[1].gaps[0].code is (
        MarketEligibilityGapCode.DEPENDENCIA_DE_SUJEITO_NAO_ESCOLHIDO
    )


def test_market_dependency_selected_subject_is_evaluated_on_establishment() -> None:
    org_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    slaughterhouse_id = TypedId.new("external_counterparty")
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    policies = InMemoryPolicies()
    evaluations = InMemoryEvaluations()
    decisions = InMemoryDecisions()
    carencia = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-china")
    estabelecimento = RuleAdoption(
        adoption_id=TypedId.new("rule_adoption"),
        organization_id=org_id,
        rule_identity_id=TypedId.new("rule_identity"),
        rule_version_id=TypedId.new("rule"),
        purpose="exportacao-china",
        scope="livestock.slaughterhouse",
        adopted_by=UniversalReference(
            target_id=TypedId.new("actor"),
            organization_id=org_id,
            contract_version=1,
        ),
        adopted_at=datetime.now(UTC),
        reason="Regra adotada para o estabelecimento exigido pela China.",
        status=RuleAdoptionStatus.ACTIVE,
    )
    adoptions.items[
        (
            org_id,
            ESTABLISHMENT_RULE_CODE,
            "exportacao-china",
            "livestock.slaughterhouse",
        )
    ] = estabelecimento
    carencia_rule = rules.add_from_adoption(carencia, code="rule-carencia-farmacologica")
    estabelecimento_rule = Rule(
        rule_id=estabelecimento.rule_version_id,
        policy_id=TypedId.new("policy"),
        organization_id=org_id,
        code=ESTABLISHMENT_RULE_CODE,
        name="Habilitacao do estabelecimento",
        description="Exige frigorifico do tipo correto e com identificador SIF.",
        version=1,
        severity=SeverityLevel.BLOCKING,
        normative_source="politica interna ficticia",
        conditions=(
            RuleCondition(
                fact_type=establishment_qualification_fact_type("exportacao-china"),
                payload_key="qualification_status",
                operator=ComparisonOperator.EQUALS,
                expected_value="HABILITADO",
                description="O estabelecimento deve estar habilitado para a China.",
            ),
        ),
        justification="China exige habilitacao do estabelecimento escolhido.",
        corrective_action="Selecionar frigorifico habilitado com SIF.",
    )
    rules.items[estabelecimento_rule.rule_id] = estabelecimento_rule
    policies.add_from_rule(carencia_rule)
    policies.add_from_rule(estabelecimento_rule)

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        policy_reader=policies,
        fact_provider=InMemoryFactProvider(),
        evaluation_repository=evaluations,
        decision_repository=decisions,
        normative_snapshot_provider=InMemoryNormativeSnapshotProvider(),
        profiles=(DEFAULT_MARKET_PROFILES[1],),
    ).evaluate(
        org_id,
        subject_id=animal_id,
        at_time=datetime.now(UTC),
        selected_subjects={"slaughterhouse": slaughterhouse_id},
    )

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.INDETERMINADO
    assert cast(Decision, decisions.saved[-1]).emission_method is DecisionEmissionMethod.AUTOMATED
    assert entry.dependency is not None
    assert entry.dependency.selected_subject_id == str(slaughterhouse_id.value)
    assert [requirement.status for requirement in entry.requirements] == [
        MarketEligibilityStatus.ELEGIVEL,
        MarketEligibilityStatus.ELEGIVEL,
    ]
    assert entry.requirements[1].execution is not None
    assert entry.requirements[1].dependency is not None
    assert entry.requirements[1].dependency.selected_subject_id == str(slaughterhouse_id.value)


def test_market_projection_requires_reevaluation_when_policy_used_is_not_current() -> None:
    org_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    policies = InMemoryPolicies()
    evaluations = InMemoryEvaluations()
    decisions = InMemoryDecisions()
    china = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-china")
    china_rule = rules.add_from_adoption(china, code="rule-carencia-farmacologica")
    used_policy = policies.add_from_rule(china_rule)
    current_policy = Policy(
        policy_id=TypedId.new("policy"),
        organization_id=org_id,
        code=used_policy.code,
        name="Policy ficticia de mercado v2",
        description="Versao mais nova da mesma policy.",
        version=used_policy.version + 1,
        status=PolicyStatus.PUBLISHED,
        published_at=datetime.now(UTC) - timedelta(days=1),
    )
    policies.items[current_policy.policy_id] = current_policy
    policies.by_code[(org_id, current_policy.code)] = current_policy

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        policy_reader=policies,
        fact_provider=InMemoryFactProvider(),
        evaluation_repository=evaluations,
        decision_repository=decisions,
        normative_snapshot_provider=InMemoryNormativeSnapshotProvider(),
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_CHINA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
            ),
        ),
    ).evaluate(
        org_id,
        subject_id=animal_id,
        at_time=datetime.now(UTC),
    )

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.INDETERMINADO
    assert entry.gaps[0].code is MarketEligibilityGapCode.POLITICA_TEMPORAL_INDETERMINADA
    assert entry.used_policy is None
    assert entry.current_policy is None


def test_market_with_multiple_requirements_fails_when_any_requirement_is_absent() -> None:
    org_id = OrganizationId.new()
    adoptions = InMemoryAdoptions()
    adoption = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-uniao-europeia")
    rules = InMemoryRules()
    rules.add_from_adoption(adoption, code="rule-carencia-farmacologica")

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                    MarketRequirement(
                        rule_code=TRACEABILITY_RULE_CODE,
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
            ),
        ),
    ).evaluate(org_id, DecisionResult.APROVADA, [_reason("Regra atendida.")])

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.AUSENTE
    assert [requirement.rule_code for requirement in entry.requirements] == [
        "rule-carencia-farmacologica",
        TRACEABILITY_RULE_CODE,
    ]
    assert entry.requirements[0].status is MarketEligibilityStatus.ELEGIVEL
    assert entry.requirements[1].status is MarketEligibilityStatus.AUSENTE


def test_adopted_requirement_without_evaluator_is_indeterminate() -> None:
    org_id = OrganizationId.new()
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    carencia = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-uniao-europeia")
    traceability_adoption = adoptions.add(
        org_id,
        TRACEABILITY_RULE_CODE,
        "exportacao-uniao-europeia",
    )
    embargo_adoption = adoptions.add(
        org_id,
        ENVIRONMENTAL_EMBARGO_RULE_CODE,
        "exportacao-uniao-europeia",
    )
    rules.add_from_adoption(carencia, code="rule-carencia-farmacologica")
    rules.add_from_adoption(
        traceability_adoption,
        code=TRACEABILITY_RULE_CODE,
        justification="Rastreabilidade minima exigida.",
        corrective_action="Completar a cadeia minima de proveniencia.",
    )
    rules.add_from_adoption(
        embargo_adoption,
        code=ENVIRONMENTAL_EMBARGO_RULE_CODE,
        justification="Ausencia de embargo ambiental conhecida.",
        corrective_action="Resolver o embargo ou registrar nova assertion.",
    )

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        profiles=(DEFAULT_MARKET_PROFILES[0],),
    ).evaluate(org_id, DecisionResult.APROVADA, [_reason("Regra atendida.")])

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.INDETERMINADO
    assert [requirement.status for requirement in entry.requirements] == [
        MarketEligibilityStatus.INDETERMINADO,
        MarketEligibilityStatus.INDETERMINADO,
        MarketEligibilityStatus.INDETERMINADO,
    ]
    assert entry.requirements[0].gaps[0].code is (
        MarketEligibilityGapCode.CARENCIA_POR_MERCADO_AUSENTE
    )
    assert entry.requirements[1].governed_rule is not None
    assert entry.requirements[1].governed_rule.adoption_id == traceability_adoption.adoption_id
    assert entry.requirements[1].adoption is not None
    assert entry.requirements[1].rule_version is not None
    assert entry.requirements[1].rule_version.justification == "Rastreabilidade minima exigida."
    assert entry.requirements[1].reasons == ()
    assert entry.requirements[1].gaps[0].code is (
        MarketEligibilityGapCode.AVALIADOR_DE_REQUISITO_AUSENTE
    )
    assert entry.requirements[2].governed_rule is not None
    assert entry.requirements[2].governed_rule.adoption_id == embargo_adoption.adoption_id
    assert entry.requirements[2].rule_version is not None
    assert entry.requirements[2].rule_version.code == ENVIRONMENTAL_EMBARGO_RULE_CODE
    assert entry.requirements[2].gaps[0].code is (
        MarketEligibilityGapCode.AVALIADOR_DE_REQUISITO_AUSENTE
    )


def test_market_with_adopted_environmental_embargo_rule_can_block_by_governed_fact() -> None:
    org_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    policies = InMemoryPolicies()
    evaluations = InMemoryEvaluations()
    decisions = InMemoryDecisions()

    carencia = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-china")
    embargo = adoptions.add(org_id, ENVIRONMENTAL_EMBARGO_RULE_CODE, "exportacao-china")
    carencia_rule = rules.add_from_adoption(carencia, code="rule-carencia-farmacologica")
    embargo_rule = Rule(
        rule_id=embargo.rule_version_id,
        policy_id=TypedId.new("policy"),
        organization_id=org_id,
        code=ENVIRONMENTAL_EMBARGO_RULE_CODE,
        name="Embargo ambiental do IBAMA",
        description="Bloqueia mercado quando a propriedade vigente tem embargo declarado.",
        version=1,
        severity=SeverityLevel.BLOCKING,
        normative_source="politica interna ficticia",
        conditions=(
            RuleCondition(
                fact_type=ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE,
                payload_key="status",
                operator=ComparisonOperator.EQUALS,
                expected_value="SEM_RESTRICAO",
                description="A propriedade nao pode ter embargo ambiental do IBAMA.",
            ),
        ),
        justification="Mercado exige ausencia de embargo ambiental conhecido.",
        corrective_action="Resolver o embargo ou reavaliar com nova assertion valida.",
    )
    rules.items[embargo_rule.rule_id] = embargo_rule
    policies.add_from_rule(carencia_rule)
    policies.add_from_rule(embargo_rule)

    class EmbargoedFactProvider(InMemoryFactProvider):
        def get_snapshot(
            self, organization_id: OrganizationId, target_id: TypedId, at_time: datetime
        ) -> FactSnapshot:
            snapshot = super().get_snapshot(organization_id, target_id, at_time)
            facts = tuple(
                Fact.create(
                    fact_type=ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE,
                    payload={"status": "COM_RESTRICAO", "restriction_count": 1},
                    observed_at=at_time,
                )
                if fact.fact_type == ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE
                else fact
                for fact in snapshot.facts
            )
            return FactSnapshot.create(
                organization_id=organization_id,
                target_id=target_id,
                as_of=at_time,
                facts=facts,
            )

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        policy_reader=policies,
        fact_provider=EmbargoedFactProvider(),
        evaluation_repository=evaluations,
        decision_repository=decisions,
        normative_snapshot_provider=InMemoryNormativeSnapshotProvider(),
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_CHINA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                    MarketRequirement(
                        rule_code=ENVIRONMENTAL_EMBARGO_RULE_CODE,
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
            ),
        ),
    ).evaluate(
        org_id,
        subject_id=animal_id,
        at_time=datetime.now(UTC),
    )

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.NAO_ELEGIVEL


def test_market_with_adopted_prodes_rule_can_block_by_governed_fact() -> None:
    org_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    policies = InMemoryPolicies()
    evaluations = InMemoryEvaluations()
    decisions = InMemoryDecisions()

    carencia = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-china")
    prodes = adoptions.add(org_id, TERRITORIAL_PRODES_RULE_CODE, "exportacao-china")
    carencia_rule = rules.add_from_adoption(carencia, code="rule-carencia-farmacologica")
    prodes_rule = Rule(
        rule_id=prodes.rule_version_id,
        policy_id=TypedId.new("policy"),
        organization_id=org_id,
        code=TERRITORIAL_PRODES_RULE_CODE,
        name="Desmatamento por PRODES",
        description="Bloqueia mercado quando o PRODES registra ocorrencia na propriedade.",
        version=1,
        severity=SeverityLevel.BLOCKING,
        normative_source="politica interna ficticia",
        conditions=(
            RuleCondition(
                fact_type=TERRITORIAL_PRODES_FACT_TYPE,
                payload_key="has_occurrence",
                operator=ComparisonOperator.EQUALS,
                expected_value=False,
                description="A propriedade nao pode ter ocorrencia conhecida no PRODES.",
            ),
        ),
        justification="Mercado exige ausencia de ocorrencia conhecida no PRODES.",
        corrective_action="Aprofundar diligencia ou redirecionar para mercado compativel.",
    )
    rules.items[prodes_rule.rule_id] = prodes_rule
    policies.add_from_rule(carencia_rule)
    policies.add_from_rule(prodes_rule)

    class ProdesFactProvider(InMemoryFactProvider):
        def get_snapshot(
            self, organization_id: OrganizationId, target_id: TypedId, at_time: datetime
        ) -> FactSnapshot:
            snapshot = super().get_snapshot(organization_id, target_id, at_time)
            facts = (
                *snapshot.facts,
                Fact.create(
                    fact_type=TERRITORIAL_PRODES_FACT_TYPE,
                    payload={
                        "status": "DISPONIVEL",
                        "has_occurrence": True,
                        "total_feature_count": 1,
                        "occurrence_years": [2020],
                    },
                    observed_at=at_time,
                ),
            )
            return FactSnapshot.create(
                organization_id=organization_id,
                target_id=target_id,
                as_of=at_time,
                facts=facts,
            )

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        policy_reader=policies,
        fact_provider=ProdesFactProvider(),
        evaluation_repository=evaluations,
        decision_repository=decisions,
        normative_snapshot_provider=InMemoryNormativeSnapshotProvider(),
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_CHINA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                    MarketRequirement(
                        rule_code=TERRITORIAL_PRODES_RULE_CODE,
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
            ),
        ),
    ).evaluate(
        org_id,
        subject_id=animal_id,
        at_time=datetime.now(UTC),
    )

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.NAO_ELEGIVEL
    assert entry.requirements[1].rule_code == TERRITORIAL_PRODES_RULE_CODE
    assert entry.requirements[1].status is MarketEligibilityStatus.NAO_ELEGIVEL
    assert entry.requirements[1].reasons[0].rule_code == TERRITORIAL_PRODES_RULE_CODE
    assert cast(Decision, decisions.saved[-1]).emission_method is DecisionEmissionMethod.AUTOMATED
    assert [requirement.status for requirement in entry.requirements] == [
        MarketEligibilityStatus.ELEGIVEL,
        MarketEligibilityStatus.NAO_ELEGIVEL,
    ]


def test_market_with_adopted_funai_rule_can_block_by_governed_fact() -> None:
    org_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    policies = InMemoryPolicies()
    evaluations = InMemoryEvaluations()
    decisions = InMemoryDecisions()

    carencia = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-china")
    funai = adoptions.add(org_id, TERRITORIAL_FUNAI_RULE_CODE, "exportacao-china")
    carencia_rule = rules.add_from_adoption(carencia, code="rule-carencia-farmacologica")
    funai_rule = Rule(
        rule_id=funai.rule_version_id,
        policy_id=TypedId.new("policy"),
        organization_id=org_id,
        code=TERRITORIAL_FUNAI_RULE_CODE,
        name="Sobreposicao territorial FUNAI",
        description="Bloqueia mercado quando a propriedade intercepta terra indigena.",
        version=1,
        severity=SeverityLevel.BLOCKING,
        normative_source="politica interna ficticia",
        conditions=(
            RuleCondition(
                fact_type=TERRITORIAL_FUNAI_FACT_TYPE,
                payload_key="has_overlap",
                operator=ComparisonOperator.EQUALS,
                expected_value=False,
                description="A propriedade nao pode sobrepor terra indigena conhecida.",
            ),
        ),
        justification="Mercado exige ausencia de sobreposicao territorial FUNAI conhecida.",
        corrective_action="Aprofundar diligencia territorial ou redirecionar o lote.",
    )
    rules.items[funai_rule.rule_id] = funai_rule
    policies.add_from_rule(carencia_rule)
    policies.add_from_rule(funai_rule)

    class FunaiFactProvider(InMemoryFactProvider):
        def get_snapshot(
            self, organization_id: OrganizationId, target_id: TypedId, at_time: datetime
        ) -> FactSnapshot:
            snapshot = super().get_snapshot(organization_id, target_id, at_time)
            facts = (
                *snapshot.facts,
                Fact.create(
                    fact_type=TERRITORIAL_FUNAI_FACT_TYPE,
                    payload={
                        "status": "COM_RESTRICAO",
                        "has_overlap": True,
                        "feature_count": 1,
                    },
                    observed_at=at_time,
                ),
            )
            return FactSnapshot.create(
                organization_id=organization_id,
                target_id=target_id,
                as_of=at_time,
                facts=facts,
            )

    matrix = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        policy_reader=policies,
        fact_provider=FunaiFactProvider(),
        evaluation_repository=evaluations,
        decision_repository=decisions,
        normative_snapshot_provider=InMemoryNormativeSnapshotProvider(),
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_CHINA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                    MarketRequirement(
                        rule_code=TERRITORIAL_FUNAI_RULE_CODE,
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
            ),
        ),
    ).evaluate(
        org_id,
        subject_id=animal_id,
        at_time=datetime.now(UTC),
    )

    entry = matrix.entries[0]
    assert entry.status is MarketEligibilityStatus.NAO_ELEGIVEL
    assert entry.requirements[1].rule_code == TERRITORIAL_FUNAI_RULE_CODE
    assert entry.requirements[1].status is MarketEligibilityStatus.NAO_ELEGIVEL


def test_market_evaluation_creates_proposal_when_review_is_required() -> None:
    org_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    adoptions = InMemoryAdoptions()
    rules = InMemoryRules()
    policies = InMemoryPolicies()
    evaluations = InMemoryEvaluations()
    decisions = InMemoryDecisions()
    governance = InMemoryDecisionGovernanceRepo()

    adoption = adoptions.add(org_id, "rule-carencia-farmacologica", "exportacao-china")
    rule = rules.add_from_adoption(adoption, code="rule-carencia-farmacologica")
    policies.add_from_rule(rule)

    class ConflictingFactProvider(InMemoryFactProvider):
        def get_snapshot(
            self, organization_id: OrganizationId, target_id: TypedId, at_time: datetime
        ) -> FactSnapshot:
            snapshot = super().get_snapshot(organization_id, target_id, at_time)
            return FactSnapshot.create(
                organization_id=organization_id,
                target_id=target_id,
                as_of=at_time,
                facts=snapshot.facts
                + (
                    Fact.create(
                        fact_type="sanitary.attestation",
                        payload={"result": "approved"},
                        observed_at=at_time,
                    ),
                    Fact.create(
                        fact_type="sanitary.attestation",
                        payload={"result": "rejected"},
                        observed_at=at_time,
                    ),
                ),
            )

    service = MarketEligibilityService(
        adoption_reader=adoptions,
        rule_reader=rules,
        policy_reader=policies,
        fact_provider=ConflictingFactProvider(),
        evaluation_repository=evaluations,
        decision_repository=decisions,
        normative_snapshot_provider=InMemoryNormativeSnapshotProvider(),
        governance_repository=governance,
        profiles=(
            MarketProfile(
                market=MarketEligibilityPurpose.EXPORTACAO_CHINA,
                requirements=(
                    MarketRequirement(
                        rule_code="rule-carencia-farmacologica",
                        scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    ),
                ),
                declared_withdrawal_period_days=30,
            ),
        ),
    )

    try:
        service.evaluate(
            org_id,
            subject_id=animal_id,
            at_time=datetime.now(UTC),
        )
    except HumanReviewRequired as exc:
        assert exc.proposal.evaluation_id == exc.evaluation.evaluation_id
        assert governance.proposals == [exc.proposal]
    else:
        raise AssertionError("era esperado review humana obrigatoria")

    assert len(evaluations.saved) == 1
    assert decisions.saved == []
