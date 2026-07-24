"""Elegibilidade farmacológica (Passo 9.5 - Titan Livestock).

Uma regra BLOQUEANTE que reprova um animal em período de carência. Ela não
recalcula nada: consome o fato `livestock.withdrawal` produzido pelo
`LivestockFactProvider` (que usa o cálculo versionado do Passo 9.4) e o avalia
pela maquinária do Core (Policy → Rule → Evaluation → Decision), preservando
motivo, evidência (o snapshot dos fatos), versão da regra e sujeito afetado.
"""

from dataclasses import dataclass
from datetime import datetime

from packages.core_application.decision_service import DecisionService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.fact_service import FactProviderPort
from packages.core_domain.decision import Decision
from packages.core_domain.evaluation import Evaluation
from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.livestock_application.fact_provider import (
    LOT_ELIGIBILITY_FACT_TYPE,
    WITHDRAWAL_FACT_TYPE,
)
from packages.shared_kernel import OrganizationId, TypedId

ELIGIBILITY_POLICY_CODE = "pol-elegibilidade-farmacologica"
ELIGIBILITY_RULE_CODE = "rule-carencia-farmacologica"
LOT_ELIGIBILITY_RULE_CODE = "rule-carencia-lote"
ELIGIBILITY_PURPOSE = "ELEGIBILIDADE_FARMACOLOGICA"
_CORRECTIVE_ACTION = (
    "Animal em carência: aguardar o fim do prazo (ver eligible_from) antes de "
    "destinar ou movimentar; conferir os lotes bloqueadores."
)
_LOT_CORRECTIVE_ACTION = (
    "Lote com animal em carência: remover o(s) animal(is) bloqueador(es) do lote "
    "(ver blocking_animals) ou aguardar o fim da carência, e reavaliar."
)


def build_eligibility_policy(
    organization_id: OrganizationId, published_at: datetime | None = None
) -> Policy:
    """Política publicada que agrupa a regra de carência."""
    draft = Policy(
        policy_id=TypedId.new("policy"),
        organization_id=organization_id,
        code=ELIGIBILITY_POLICY_CODE,
        name="Elegibilidade farmacológica",
        description="Reprova animal em período de carência de medicamento.",
        version=1,
        status=PolicyStatus.DRAFT,
    )
    return draft.publish(published_at)


def build_eligibility_rule(policy_id: TypedId, organization_id: OrganizationId) -> Rule:
    """Regra bloqueante: animal em carência (`in_withdrawal == True`) reprova."""
    return Rule(
        rule_id=TypedId.new("rule"),
        policy_id=policy_id,
        organization_id=organization_id,
        code=ELIGIBILITY_RULE_CODE,
        name="Carência farmacológica",
        description="Bloqueia animal dentro do período de carência de medicamento.",
        severity=SeverityLevel.BLOCKING,
        normative_source="titan-livestock-withdrawal-v1",
        conditions=(
            RuleCondition(
                fact_type=WITHDRAWAL_FACT_TYPE,
                payload_key="in_withdrawal",
                operator=ComparisonOperator.EQUALS,
                expected_value=False,
                description="Animal não pode estar em período de carência.",
            ),
        ),
        corrective_action=_CORRECTIVE_ACTION,
    )


def build_lot_eligibility_rule(policy_id: TypedId, organization_id: OrganizationId) -> Rule:
    """Regra bloqueante de lote: qualquer animal em carência reprova o lote."""
    return Rule(
        rule_id=TypedId.new("rule"),
        policy_id=policy_id,
        organization_id=organization_id,
        code=LOT_ELIGIBILITY_RULE_CODE,
        name="Carência farmacológica no lote",
        description="Bloqueia lote que contém animal em período de carência.",
        severity=SeverityLevel.BLOCKING,
        normative_source="titan-livestock-withdrawal-v1",
        conditions=(
            RuleCondition(
                fact_type=LOT_ELIGIBILITY_FACT_TYPE,
                payload_key="has_animal_in_withdrawal",
                operator=ComparisonOperator.EQUALS,
                expected_value=False,
                description="Nenhum animal do lote pode estar em carência.",
            ),
        ),
        corrective_action=_LOT_CORRECTIVE_ACTION,
    )


@dataclass(frozen=True, slots=True)
class PharmacologicalEligibilityService:
    """Avalia a elegibilidade farmacológica de um animal.

    Compõe o fornecedor de fatos da vertical com a política e a regra
    farmacológicas e delega a decisão ao Core, sem reimplementar avaliação.
    """

    fact_provider: FactProviderPort
    policy: Policy
    rule: Rule
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
            raise RuntimeError("O serviço não foi configurado com a regra de lote (lot_rule).")
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
        decision = DecisionService().decide(evaluation)
        return evaluation, decision
