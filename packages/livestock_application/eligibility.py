"""Elegibilidade farmacologica (Passo 9.5 - Titan Livestock)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_application.decision_governance_service import (
    DecisionGovernanceRepositoryPort,
    DecisionGovernanceService,
)
from packages.core_application.decision_service import DecisionService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.fact_service import FactProviderPort
from packages.core_domain.decision import Decision
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.decision_governance import (
    DecisionAuthorityProfile,
    DecisionEmissionRefusalCode,
    DecisionEmissionRefused,
    DecisionProposal,
)
from packages.core_domain.evaluation import Evaluation
from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.livestock_application.fact_provider import (
    LOT_ELIGIBILITY_FACT_TYPE,
    WITHDRAWAL_FACT_TYPE,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

ELIGIBILITY_POLICY_CODE = "pol-elegibilidade-farmacologica"
ELIGIBILITY_RULE_CODE = "rule-carencia-farmacologica"
LOT_ELIGIBILITY_RULE_CODE = "rule-carencia-lote"
ELIGIBILITY_PURPOSE = "ELEGIBILIDADE_FARMACOLOGICA"
ELIGIBILITY_RULE_ADOPTION_SCOPE = "livestock.animal"
_CORRECTIVE_ACTION = (
    "Animal em carencia: aguardar o fim do prazo (ver eligible_from) antes de "
    "destinar ou movimentar; conferir os lotes bloqueadores."
)
_LOT_CORRECTIVE_ACTION = (
    "Lote com animal em carencia: remover o(s) animal(is) bloqueador(es) do lote "
    "(ver blocking_animals) ou aguardar o fim da carencia, e reavaliar."
)


def automated_decision_authority(
    organization_id: OrganizationId,
    *,
    purpose: str,
    role_name: str = "LIVESTOCK_AUTOMATED_DECISION_ENGINE",
) -> DecisionAuthorityProfile:
    return DecisionAuthorityProfile(
        authority_id=TypedId.new("authority_profile"),
        organization_id=organization_id,
        principal_reference=UniversalReference(
            target_id=TypedId.new("service_identity"),
            organization_id=organization_id,
            contract_version=1,
        ),
        role_name=role_name,
        purpose=purpose,
        emission_method=DecisionEmissionMethod.AUTOMATED,
        approvals_required=0,
    )


def build_eligibility_policy(
    organization_id: OrganizationId, published_at: datetime | None = None
) -> Policy:
    draft = Policy(
        policy_id=TypedId.new("policy"),
        organization_id=organization_id,
        code=ELIGIBILITY_POLICY_CODE,
        name="Elegibilidade farmacologica",
        description="Reprova animal em periodo de carencia de medicamento.",
        version=1,
        status=PolicyStatus.DRAFT,
    )
    return draft.publish(published_at)


def build_eligibility_rule(policy_id: TypedId, organization_id: OrganizationId) -> Rule:
    return Rule(
        rule_id=TypedId.new("rule"),
        policy_id=policy_id,
        organization_id=organization_id,
        code=ELIGIBILITY_RULE_CODE,
        name="Carencia farmacologica",
        description="Bloqueia animal dentro do periodo de carencia de medicamento.",
        severity=SeverityLevel.BLOCKING,
        normative_source="titan-livestock-withdrawal-v1",
        conditions=(
            RuleCondition(
                fact_type=WITHDRAWAL_FACT_TYPE,
                payload_key="in_withdrawal",
                operator=ComparisonOperator.EQUALS,
                expected_value=False,
                description="Animal nao pode estar em periodo de carencia.",
            ),
        ),
        corrective_action=_CORRECTIVE_ACTION,
    )


def build_lot_eligibility_rule(policy_id: TypedId, organization_id: OrganizationId) -> Rule:
    return Rule(
        rule_id=TypedId.new("rule"),
        policy_id=policy_id,
        organization_id=organization_id,
        code=LOT_ELIGIBILITY_RULE_CODE,
        name="Carencia farmacologica no lote",
        description="Bloqueia lote que contem animal em periodo de carencia.",
        severity=SeverityLevel.BLOCKING,
        normative_source="titan-livestock-withdrawal-v1",
        conditions=(
            RuleCondition(
                fact_type=LOT_ELIGIBILITY_FACT_TYPE,
                payload_key="has_animal_in_withdrawal",
                operator=ComparisonOperator.EQUALS,
                expected_value=False,
                description="Nenhum animal do lote pode estar em carencia.",
            ),
        ),
        corrective_action=_LOT_CORRECTIVE_ACTION,
    )


class EvaluationRepositoryPort(Protocol):
    def save(self, evaluation: Evaluation) -> None: ...


class DecisionRepositoryPort(Protocol):
    def save(self, decision: Decision) -> None: ...


class DecisionAuthorityProfileRepositoryPort(Protocol):
    def save(self, profile: DecisionAuthorityProfile) -> None: ...


@dataclass(frozen=True, slots=True)
class HumanReviewRequired(Exception):
    evaluation: Evaluation
    proposal: DecisionProposal


@dataclass(frozen=True, slots=True)
class GovernedRuleReference:
    adoption_id: TypedId
    rule_identity_id: TypedId
    rule_version_id: TypedId
    purpose: str
    scope: str

    def __post_init__(self) -> None:
        if self.adoption_id.entity_type != "rule_adoption":
            raise ValueError("adoption_id deve ser do tipo 'rule_adoption'.")
        if self.rule_identity_id.entity_type != "rule_identity":
            raise ValueError("rule_identity_id deve ser do tipo 'rule_identity'.")
        if self.rule_version_id.entity_type != "rule":
            raise ValueError("rule_version_id deve ser do tipo 'rule'.")
        if not self.purpose.strip():
            raise ValueError("purpose da regra governada nao pode ser vazio.")
        if not self.scope.strip():
            raise ValueError("scope da regra governada nao pode ser vazio.")

    def to_dict(self) -> dict[str, str]:
        return {
            "adoption_id": str(self.adoption_id.value),
            "rule_identity_id": str(self.rule_identity_id.value),
            "rule_version_id": str(self.rule_version_id.value),
            "purpose": self.purpose,
            "scope": self.scope,
        }


@dataclass(frozen=True, slots=True)
class PharmacologicalEligibilityService:
    fact_provider: FactProviderPort
    policy: Policy
    rule: Rule
    evaluation_repository: EvaluationRepositoryPort
    decision_repository: DecisionRepositoryPort
    authority_profile_repository: DecisionAuthorityProfileRepositoryPort | None = None
    governance_repository: DecisionGovernanceRepositoryPort | None = None
    lot_rule: Rule | None = None

    def evaluate_animal(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        at_time: datetime,
    ) -> tuple[Evaluation, Decision]:
        return self._evaluate(organization_id, animal_id, self.rule, at_time)

    def evaluate_lot(
        self,
        organization_id: OrganizationId,
        lot_id: TypedId,
        at_time: datetime,
    ) -> tuple[Evaluation, Decision]:
        if self.lot_rule is None:
            raise RuntimeError("O servico nao foi configurado com a regra de lote (lot_rule).")
        return self._evaluate(organization_id, lot_id, self.lot_rule, at_time)

    def _evaluate(
        self,
        organization_id: OrganizationId,
        subject_id: TypedId,
        rule: Rule,
        at_time: datetime,
    ) -> tuple[Evaluation, Decision]:
        snapshot = self.fact_provider.get_snapshot(organization_id, subject_id, at_time)
        evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
            policy=self.policy,
            rules=(rule,),
            snapshot=snapshot,
            purpose=ELIGIBILITY_PURPOSE,
        )
        authority = automated_decision_authority(
            organization_id,
            purpose=evaluation.purpose,
            role_name="LIVESTOCK_PHARMACOLOGICAL_ELIGIBILITY_ENGINE",
        )
        self.evaluation_repository.save(evaluation)
        if self.authority_profile_repository is not None:
            self.authority_profile_repository.save(authority)
        try:
            decision = DecisionService().decide(evaluation, authority)
        except DecisionEmissionRefused as exc:
            if (
                exc.code is DecisionEmissionRefusalCode.REVIEW_REQUIRED
                and self.governance_repository is not None
            ):
                proposal = DecisionGovernanceService(
                    repository=self.governance_repository
                ).create_proposal(evaluation=evaluation)
                raise HumanReviewRequired(evaluation=evaluation, proposal=proposal) from exc
            raise
        self.decision_repository.save(decision)
        return evaluation, decision
