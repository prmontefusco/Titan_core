"""Elegibilidade farmacológica (Passo 9.5 - Titan Livestock).

Uma regra BLOQUEANTE que reprova um animal em período de carência. Ela não
recalcula nada: consome o fato `livestock.withdrawal` produzido pelo
`LivestockFactProvider` (que usa o cálculo versionado do Passo 9.4) e o avalia
pela maquinária do Core (Policy → Rule → Evaluation → Decision), preservando
motivo, evidência (o snapshot dos fatos), versão da regra e sujeito afetado.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

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
ELIGIBILITY_RULE_ADOPTION_SCOPE = "livestock.animal"
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


class EvaluationRepositoryPort(Protocol):
    def save(self, evaluation: Evaluation) -> None: ...


class DecisionRepositoryPort(Protocol):
    def save(self, decision: Decision) -> None: ...


@dataclass(frozen=True, slots=True)
class GovernedRuleReference:
    """Referencia a versao de regra governada adotada para uma avaliacao."""

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
    """Avalia a elegibilidade farmacológica de um animal.

    Compõe o fornecedor de fatos da vertical com a política e a regra
    farmacológicas e delega a decisão ao Core, sem reimplementar avaliação.

    A avaliação e a decisão são gravadas nas tabelas do Core. Sem isso o bloqueio
    e a reavaliação existiriam só durante a chamada, e a linha do tempo do Passo
    10.1 não teria como mostrar por que um animal foi barrado — que é o fato
    central do Marco 9. A vertical não cria armazenamento próprio para isso: a
    fonte da verdade continua sendo o Core.
    """

    fact_provider: FactProviderPort
    policy: Policy
    rule: Rule
    evaluation_repository: EvaluationRepositoryPort
    decision_repository: DecisionRepositoryPort
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
        # A ordem importa: a decisão referencia a avaliação, então gravar a
        # decisão primeiro deixaria uma referência pendurada se a segunda escrita
        # falhasse.
        self.evaluation_repository.save(evaluation)
        self.decision_repository.save(decision)
        return evaluation, decision
