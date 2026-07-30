"""Matriz de elegibilidade comercial por mercado (ADR-0044)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from packages.core_application.decision_service import DecisionService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.fact_service import FactProviderPort
from packages.core_domain.decision import Decision, DecisionReason, DecisionResult
from packages.core_domain.decision_governance import DecisionAuthorityProfile
from packages.core_domain.evaluation import Evaluation
from packages.core_domain.policy import Policy
from packages.core_domain.rule import Rule
from packages.core_domain.rule_governance import RuleAdoption
from packages.livestock_application.eligibility import (
    ELIGIBILITY_RULE_ADOPTION_SCOPE,
    ELIGIBILITY_RULE_CODE,
    GovernedRuleReference,
    automated_decision_authority,
)
from packages.shared_kernel import OrganizationId, TypedId

TRACEABILITY_RULE_CODE = "rule-rastreabilidade-minima"
ESTABLISHMENT_RULE_CODE = "rule-habilitacao-estabelecimento"
ENVIRONMENTAL_EMBARGO_RULE_CODE = "rule-embargo-ambiental-ibama"
# Regra governada de exigibilidade sanitária (Item 4 da fila do backend).
# Qual campanha um mercado exige vive na RuleCondition da versão adotada
# (fact_type=sanitary_requirement_fact_type("<campanha>")), não aqui — o
# mesmo padrão já usado por ESTABLISHMENT_RULE_CODE com qualificação de
# estabelecimento. Nenhum MarketProfile referencia este código ainda:
# amarrar um mercado a uma campanha real é decisão normativa, não deste
# mecanismo.
SANITARY_RULE_CODE = "rule-exigibilidade-sanitaria"
SUPPORTED_BASE_DECISION_RULE_CODES = frozenset({ELIGIBILITY_RULE_CODE})


class MarketEligibilityPurpose(Enum):
    EXPORTACAO_UNIAO_EUROPEIA = "exportacao-uniao-europeia"
    EXPORTACAO_CHINA = "exportacao-china"
    EXPORTACAO_ESTADOS_UNIDOS = "exportacao-estados-unidos"

    @property
    def code(self) -> str:
        return self.value


EXPORT_MARKETS: tuple[MarketEligibilityPurpose, ...] = tuple(MarketEligibilityPurpose)


class MarketEligibilityStatus(Enum):
    ELEGIVEL = "ELEGIVEL"
    NAO_ELEGIVEL = "NAO_ELEGIVEL"
    CONDICIONADO = "CONDICIONADO"
    INDETERMINADO = "INDETERMINADO"
    AUSENTE = "AUSENTE"


class MarketProjectionStatus(Enum):
    ATUAL = "ATUAL"
    REAVALIACAO_NECESSARIA = "REAVALIACAO_NECESSARIA"


class MarketEligibilityGapCode(Enum):
    REGRA_GOVERNADA_AUSENTE = "REGRA_GOVERNADA_AUSENTE"
    AVALIADOR_DE_REQUISITO_AUSENTE = "AVALIADOR_DE_REQUISITO_AUSENTE"
    CARENCIA_POR_MERCADO_AUSENTE = "CARENCIA_POR_MERCADO_AUSENTE"
    DEPENDENCIA_DE_SUJEITO_NAO_ESCOLHIDO = "DEPENDENCIA_DE_SUJEITO_NAO_ESCOLHIDO"


@dataclass(frozen=True, slots=True)
class MarketRequirement:
    rule_code: str
    scope: str
    dependent_subject_key: str | None = None
    dependent_subject_label: str | None = None

    def __post_init__(self) -> None:
        if not self.rule_code.strip():
            raise ValueError("rule_code do requisito de mercado nao pode ser vazio.")
        if not self.scope.strip():
            raise ValueError("scope do requisito de mercado nao pode ser vazio.")
        if self.dependent_subject_key is not None and not self.dependent_subject_key.strip():
            raise ValueError("dependent_subject_key nao pode ser vazio.")
        if self.dependent_subject_label is not None and not self.dependent_subject_label.strip():
            raise ValueError("dependent_subject_label nao pode ser vazio.")
        if (self.dependent_subject_key is None) != (self.dependent_subject_label is None):
            raise ValueError(
                "dependent_subject_key e dependent_subject_label devem ser informados juntos."
            )


@dataclass(frozen=True, slots=True)
class MarketProfile:
    market: MarketEligibilityPurpose
    requirements: tuple[MarketRequirement, ...]
    declared_withdrawal_period_days: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.market, MarketEligibilityPurpose):
            raise TypeError("market do perfil deve ser MarketEligibilityPurpose.")
        if not self.requirements:
            raise ValueError("perfil de mercado exige ao menos um requisito.")
        if (
            self.declared_withdrawal_period_days is not None
            and self.declared_withdrawal_period_days < 0
        ):
            raise ValueError("declared_withdrawal_period_days nao pode ser negativo.")


DEFAULT_MARKET_PROFILES: tuple[MarketProfile, ...] = (
    MarketProfile(
        market=MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA,
        requirements=(
            MarketRequirement(
                rule_code=ELIGIBILITY_RULE_CODE,
                scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
            ),
            MarketRequirement(
                rule_code=TRACEABILITY_RULE_CODE,
                scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
            ),
            MarketRequirement(
                rule_code=ENVIRONMENTAL_EMBARGO_RULE_CODE,
                scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
            ),
        ),
        declared_withdrawal_period_days=None,
    ),
    MarketProfile(
        market=MarketEligibilityPurpose.EXPORTACAO_CHINA,
        requirements=(
            MarketRequirement(
                rule_code=ELIGIBILITY_RULE_CODE,
                scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
            ),
            MarketRequirement(
                rule_code=ESTABLISHMENT_RULE_CODE,
                scope="livestock.slaughterhouse",
                dependent_subject_key="slaughterhouse",
                dependent_subject_label="estabelecimento",
            ),
        ),
        declared_withdrawal_period_days=30,
    ),
    MarketProfile(
        market=MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS,
        requirements=(
            MarketRequirement(
                rule_code=ELIGIBILITY_RULE_CODE,
                scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
            ),
        ),
        declared_withdrawal_period_days=30,
    ),
)


class MarketRuleAdoptionReaderPort(Protocol):
    def get_active_by_code_purpose_and_scope(
        self,
        organization_id: OrganizationId,
        code: str,
        purpose: str,
        scope: str,
    ) -> RuleAdoption | None: ...


class MarketRuleVersionReaderPort(Protocol):
    def get_by_id(self, rule_id: TypedId) -> Rule | None: ...


class MarketPolicyReaderPort(Protocol):
    def get_by_id(self, policy_id: TypedId) -> Policy | None: ...

    def get_active_at(
        self, organization_id: OrganizationId, code: str, at_time: datetime
    ) -> Policy | None: ...


class MarketEvaluationRepositoryPort(Protocol):
    def save(self, evaluation: Evaluation) -> None: ...


class MarketDecisionRepositoryPort(Protocol):
    def save(self, decision: Decision) -> None: ...


class MarketDecisionAuthorityProfileRepositoryPort(Protocol):
    def save(self, profile: DecisionAuthorityProfile) -> None: ...


@dataclass(frozen=True, slots=True)
class MarketDependencySummary:
    subject_key: str
    subject_label: str
    selected_subject_id: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "subject_key": self.subject_key,
            "subject_label": self.subject_label,
            "selected_subject_id": self.selected_subject_id,
        }


@dataclass(frozen=True, slots=True)
class MarketEligibilityReason:
    code: str
    message: str
    rule_code: str
    rule_id: str | None
    rule_version: int | None

    @classmethod
    def from_decision_reason(cls, reason: DecisionReason) -> "MarketEligibilityReason":
        return cls(
            code=reason.code.value,
            message=reason.message,
            rule_code=reason.rule_code,
            rule_id=None if reason.rule_id is None else str(reason.rule_id.value),
            rule_version=reason.rule_version,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "rule_code": self.rule_code,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
        }


@dataclass(frozen=True, slots=True)
class MarketEligibilityGap:
    code: MarketEligibilityGapCode
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code.value,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class MarketRuleAdoptionSummary:
    adoption_id: str
    purpose: str
    scope: str
    adopted_at: str
    reason: str

    @classmethod
    def from_rule_adoption(cls, adoption: RuleAdoption) -> "MarketRuleAdoptionSummary":
        return cls(
            adoption_id=str(adoption.adoption_id.value),
            purpose=adoption.purpose,
            scope=adoption.scope,
            adopted_at=adoption.adopted_at.isoformat(),
            reason=adoption.reason,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "adoption_id": self.adoption_id,
            "purpose": self.purpose,
            "scope": self.scope,
            "adopted_at": self.adopted_at,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class MarketRuleVersionSummary:
    rule_id: str
    code: str
    name: str
    version: int
    severity: str
    normative_source: str
    justification: str
    corrective_action: str

    @classmethod
    def from_rule(cls, rule: Rule) -> "MarketRuleVersionSummary":
        return cls(
            rule_id=str(rule.rule_id.value),
            code=rule.code,
            name=rule.name,
            version=rule.version,
            severity=rule.severity.value,
            normative_source=rule.normative_source,
            justification=rule.justification,
            corrective_action=rule.corrective_action,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "code": self.code,
            "name": self.name,
            "version": self.version,
            "severity": self.severity,
            "normative_source": self.normative_source,
            "justification": self.justification,
            "corrective_action": self.corrective_action,
        }


@dataclass(frozen=True, slots=True)
class MarketExecutionSummary:
    evaluation_id: str
    decision_id: str

    @classmethod
    def from_ids(cls, evaluation_id: TypedId, decision_id: TypedId) -> "MarketExecutionSummary":
        return cls(
            evaluation_id=str(evaluation_id.value),
            decision_id=str(decision_id.value),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "evaluation_id": self.evaluation_id,
            "decision_id": self.decision_id,
        }


@dataclass(frozen=True, slots=True)
class MarketPolicySummary:
    policy_id: str
    code: str
    version: int
    status: str
    valid_from: str | None
    valid_to: str | None

    @classmethod
    def from_policy(cls, policy: Policy) -> "MarketPolicySummary":
        return cls(
            policy_id=str(policy.policy_id.value),
            code=policy.code,
            version=policy.version,
            status=policy.status.value,
            valid_from=None if policy.valid_from is None else policy.valid_from.isoformat(),
            valid_to=None if policy.valid_to is None else policy.valid_to.isoformat(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "code": self.code,
            "version": self.version,
            "status": self.status,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
        }


@dataclass(frozen=True, slots=True)
class MarketRequirementResult:
    rule_code: str
    scope: str
    status: MarketEligibilityStatus
    reasons: tuple[MarketEligibilityReason, ...]
    gaps: tuple[MarketEligibilityGap, ...]
    governed_rule: GovernedRuleReference | None = None
    adoption: MarketRuleAdoptionSummary | None = None
    rule_version: MarketRuleVersionSummary | None = None
    execution: MarketExecutionSummary | None = None
    projection_status: MarketProjectionStatus = MarketProjectionStatus.ATUAL
    used_policy: MarketPolicySummary | None = None
    current_policy: MarketPolicySummary | None = None
    dependency: MarketDependencySummary | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_code": self.rule_code,
            "scope": self.scope,
            "status": self.status.value,
            "projection_status": self.projection_status.value,
            "governed_rule": None if self.governed_rule is None else self.governed_rule.to_dict(),
            "adoption": None if self.adoption is None else self.adoption.to_dict(),
            "rule_version": None if self.rule_version is None else self.rule_version.to_dict(),
            "execution": None if self.execution is None else self.execution.to_dict(),
            "used_policy": None if self.used_policy is None else self.used_policy.to_dict(),
            "current_policy": (
                None if self.current_policy is None else self.current_policy.to_dict()
            ),
            "dependency": None if self.dependency is None else self.dependency.to_dict(),
            "reasons": [reason.to_dict() for reason in self.reasons],
            "gaps": [gap.to_dict() for gap in self.gaps],
        }


@dataclass(frozen=True, slots=True)
class MarketEligibilityEntry:
    market: MarketEligibilityPurpose
    status: MarketEligibilityStatus
    reasons: tuple[MarketEligibilityReason, ...]
    gaps: tuple[MarketEligibilityGap, ...] = ()
    governed_rule: GovernedRuleReference | None = None
    adoption: MarketRuleAdoptionSummary | None = None
    rule_version: MarketRuleVersionSummary | None = None
    execution: MarketExecutionSummary | None = None
    projection_status: MarketProjectionStatus = MarketProjectionStatus.ATUAL
    used_policy: MarketPolicySummary | None = None
    current_policy: MarketPolicySummary | None = None
    dependency: MarketDependencySummary | None = None
    requirements: tuple[MarketRequirementResult, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "market": self.market.code,
            "status": self.status.value,
            "projection_status": self.projection_status.value,
            "governed_rule": None if self.governed_rule is None else self.governed_rule.to_dict(),
            "adoption": None if self.adoption is None else self.adoption.to_dict(),
            "rule_version": None if self.rule_version is None else self.rule_version.to_dict(),
            "execution": None if self.execution is None else self.execution.to_dict(),
            "used_policy": None if self.used_policy is None else self.used_policy.to_dict(),
            "current_policy": (
                None if self.current_policy is None else self.current_policy.to_dict()
            ),
            "dependency": None if self.dependency is None else self.dependency.to_dict(),
            "reasons": [reason.to_dict() for reason in self.reasons],
            "gaps": [gap.to_dict() for gap in self.gaps],
            "requirements": [requirement.to_dict() for requirement in self.requirements],
        }


@dataclass(frozen=True, slots=True)
class MarketEligibilityMatrix:
    entries: tuple[MarketEligibilityEntry, ...]

    def to_dict(self) -> list[dict[str, object]]:
        return [entry.to_dict() for entry in self.entries]

    def first_executed_requirement(self) -> MarketRequirementResult | None:
        for entry in self.entries:
            for requirement in entry.requirements:
                if requirement.execution is not None:
                    return requirement
        return None


@dataclass(frozen=True, slots=True)
class MarketEligibilityService:
    adoption_reader: MarketRuleAdoptionReaderPort
    rule_reader: MarketRuleVersionReaderPort
    policy_reader: MarketPolicyReaderPort | None = None
    fact_provider: FactProviderPort | None = None
    evaluation_repository: MarketEvaluationRepositoryPort | None = None
    decision_repository: MarketDecisionRepositoryPort | None = None
    authority_profile_repository: MarketDecisionAuthorityProfileRepositoryPort | None = None
    profiles: Sequence[MarketProfile] = DEFAULT_MARKET_PROFILES

    def evaluate(
        self,
        organization_id: OrganizationId,
        base_result: DecisionResult | None = None,
        base_reasons: Sequence[DecisionReason] = (),
        *,
        subject_id: TypedId | None = None,
        at_time: datetime | None = None,
        selected_subjects: dict[str, TypedId] | None = None,
    ) -> MarketEligibilityMatrix:
        use_independent_evaluation = (
            subject_id is not None
            and at_time is not None
            and self.fact_provider is not None
            and self.policy_reader is not None
            and self.evaluation_repository is not None
            and self.decision_repository is not None
        )
        if not use_independent_evaluation and base_result is None:
            raise ValueError(
                "A matriz exige base_result/base_reasons ou dependencias para avaliacao "
                "independente por mercado."
            )
        entries = tuple(
            self._entry_for_profile(
                organization_id,
                profile,
                base_result,
                base_reasons,
                subject_id=subject_id,
                at_time=at_time,
                use_independent_evaluation=use_independent_evaluation,
                selected_subjects=selected_subjects or {},
            )
            for profile in self.profiles
        )
        return MarketEligibilityMatrix(entries=entries)

    def _entry_for_profile(
        self,
        organization_id: OrganizationId,
        profile: MarketProfile,
        base_result: DecisionResult | None,
        base_reasons: Sequence[DecisionReason],
        *,
        subject_id: TypedId | None,
        at_time: datetime | None,
        use_independent_evaluation: bool,
        selected_subjects: dict[str, TypedId],
    ) -> MarketEligibilityEntry:
        requirements = tuple(
            self._requirement_result(
                organization_id,
                profile.market.code,
                requirement,
                profile.declared_withdrawal_period_days,
                base_result,
                base_reasons,
                subject_id=subject_id,
                at_time=at_time,
                use_independent_evaluation=use_independent_evaluation,
                selected_subjects=selected_subjects,
            )
            for requirement in profile.requirements
        )
        status = _aggregate_requirement_status(requirements)
        reasons = tuple(reason for requirement in requirements for reason in requirement.reasons)
        gaps = tuple(gap for requirement in requirements for gap in requirement.gaps)
        first_governed_rule = next(
            (
                requirement.governed_rule
                for requirement in requirements
                if requirement.governed_rule is not None
            ),
            None,
        )
        return MarketEligibilityEntry(
            market=profile.market,
            status=status,
            projection_status=_aggregate_projection_status(requirements),
            governed_rule=first_governed_rule,
            adoption=next(
                (
                    requirement.adoption
                    for requirement in requirements
                    if requirement.adoption is not None
                ),
                None,
            ),
            rule_version=next(
                (
                    requirement.rule_version
                    for requirement in requirements
                    if requirement.rule_version is not None
                ),
                None,
            ),
            execution=next(
                (
                    requirement.execution
                    for requirement in requirements
                    if requirement.execution is not None
                ),
                None,
            ),
            used_policy=next(
                (
                    requirement.used_policy
                    for requirement in requirements
                    if requirement.used_policy is not None
                ),
                None,
            ),
            current_policy=next(
                (
                    requirement.current_policy
                    for requirement in requirements
                    if requirement.current_policy is not None
                ),
                None,
            ),
            dependency=next(
                (
                    requirement.dependency
                    for requirement in requirements
                    if requirement.dependency is not None
                ),
                None,
            ),
            reasons=reasons,
            gaps=gaps,
            requirements=requirements,
        )

    def _requirement_result(
        self,
        organization_id: OrganizationId,
        market: str,
        requirement: MarketRequirement,
        declared_withdrawal_period_days: int | None,
        base_result: DecisionResult | None,
        base_reasons: Sequence[DecisionReason],
        *,
        subject_id: TypedId | None,
        at_time: datetime | None,
        use_independent_evaluation: bool,
        selected_subjects: dict[str, TypedId],
    ) -> MarketRequirementResult:
        dependency: MarketDependencySummary | None = None
        evaluation_subject_id = subject_id
        if requirement.dependent_subject_key is not None:
            selected_subject = selected_subjects.get(requirement.dependent_subject_key)
            if selected_subject is None:
                dependency = MarketDependencySummary(
                    subject_key=requirement.dependent_subject_key,
                    subject_label=requirement.dependent_subject_label or "sujeito dependente",
                    selected_subject_id=None,
                )
                return MarketRequirementResult(
                    rule_code=requirement.rule_code,
                    scope=requirement.scope,
                    status=MarketEligibilityStatus.CONDICIONADO,
                    reasons=(),
                    dependency=dependency,
                    gaps=(
                        MarketEligibilityGap(
                            code=MarketEligibilityGapCode.DEPENDENCIA_DE_SUJEITO_NAO_ESCOLHIDO,
                            message=(
                                "O que depende do animal esta satisfeito, mas este mercado "
                                "ainda depende de um "
                                f"{dependency.subject_label} escolhido."
                            ),
                        ),
                    ),
                )
            dependency = MarketDependencySummary(
                subject_key=requirement.dependent_subject_key,
                subject_label=requirement.dependent_subject_label or "sujeito dependente",
                selected_subject_id=str(selected_subject.value),
            )
            evaluation_subject_id = selected_subject
        adoption = self.adoption_reader.get_active_by_code_purpose_and_scope(
            organization_id,
            requirement.rule_code,
            market,
            requirement.scope,
        )
        if adoption is None:
            return MarketRequirementResult(
                rule_code=requirement.rule_code,
                scope=requirement.scope,
                status=MarketEligibilityStatus.AUSENTE,
                reasons=(),
                dependency=dependency,
                gaps=(
                    MarketEligibilityGap(
                        code=MarketEligibilityGapCode.REGRA_GOVERNADA_AUSENTE,
                        message="Nenhuma regra governada adotada para este mercado.",
                    ),
                ),
            )

        governed_rule = GovernedRuleReference(
            adoption_id=adoption.adoption_id,
            rule_identity_id=adoption.rule_identity_id,
            rule_version_id=adoption.rule_version_id,
            purpose=adoption.purpose,
            scope=adoption.scope,
        )
        rule = self.rule_reader.get_by_id(adoption.rule_version_id)
        adoption_summary = MarketRuleAdoptionSummary.from_rule_adoption(adoption)
        rule_version = None if rule is None else MarketRuleVersionSummary.from_rule(rule)
        if (
            requirement.rule_code == ELIGIBILITY_RULE_CODE
            and declared_withdrawal_period_days is None
        ):
            return MarketRequirementResult(
                rule_code=requirement.rule_code,
                scope=requirement.scope,
                status=MarketEligibilityStatus.INDETERMINADO,
                gaps=(
                    MarketEligibilityGap(
                        code=MarketEligibilityGapCode.CARENCIA_POR_MERCADO_AUSENTE,
                        message=(
                            "Este mercado nao declarou o prazo de carencia usado na "
                            "avaliacao; o resultado nao pode ser promovido a elegivel."
                        ),
                    ),
                ),
                governed_rule=governed_rule,
                adoption=adoption_summary,
                rule_version=rule_version,
                reasons=(),
                dependency=dependency,
            )
        if (
            requirement.rule_code not in SUPPORTED_BASE_DECISION_RULE_CODES
            and not use_independent_evaluation
        ):
            return MarketRequirementResult(
                rule_code=requirement.rule_code,
                scope=requirement.scope,
                status=MarketEligibilityStatus.INDETERMINADO,
                gaps=(
                    MarketEligibilityGap(
                        code=MarketEligibilityGapCode.AVALIADOR_DE_REQUISITO_AUSENTE,
                        message=(
                            "Regra governada adotada, mas ainda sem avaliador para este "
                            "requisito de mercado."
                        ),
                    ),
                ),
                governed_rule=governed_rule,
                adoption=adoption_summary,
                rule_version=rule_version,
                reasons=(),
                dependency=dependency,
            )

        if use_independent_evaluation:
            assert evaluation_subject_id is not None
            assert at_time is not None
            assert self.fact_provider is not None
            snapshot = self.fact_provider.get_snapshot(
                organization_id,
                evaluation_subject_id,
                at_time,
            )
            if rule is None:
                return MarketRequirementResult(
                    rule_code=requirement.rule_code,
                    scope=requirement.scope,
                    status=MarketEligibilityStatus.INDETERMINADO,
                    gaps=(
                        MarketEligibilityGap(
                            code=MarketEligibilityGapCode.AVALIADOR_DE_REQUISITO_AUSENTE,
                            message=(
                                "Regra governada adotada, mas a versao publicada nao foi "
                                "encontrada para avaliacao."
                            ),
                        ),
                    ),
                    governed_rule=governed_rule,
                    adoption=adoption_summary,
                    rule_version=None,
                    reasons=(),
                    dependency=dependency,
                )
            assert self.policy_reader is not None
            assert self.evaluation_repository is not None
            assert self.decision_repository is not None
            policy = self.policy_reader.get_by_id(rule.policy_id)
            if policy is None:
                return MarketRequirementResult(
                    rule_code=requirement.rule_code,
                    scope=requirement.scope,
                    status=MarketEligibilityStatus.INDETERMINADO,
                    gaps=(
                        MarketEligibilityGap(
                            code=MarketEligibilityGapCode.AVALIADOR_DE_REQUISITO_AUSENTE,
                            message=(
                                "Regra governada adotada, mas a policy publicada nao foi "
                                "encontrada para avaliacao."
                            ),
                        ),
                    ),
                    governed_rule=governed_rule,
                    adoption=adoption_summary,
                    rule_version=rule_version,
                    reasons=(),
                    dependency=dependency,
                )
            current_policy = self.policy_reader.get_active_at(
                organization_id,
                policy.code,
                snapshot.as_of,
            )
            projection_status = _projection_status_from_policies(policy, current_policy)
            evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
                policy=policy,
                rules=(rule,),
                snapshot=snapshot,
                purpose=market,
            )
            authority = automated_decision_authority(
                organization_id,
                purpose=evaluation.purpose,
                role_name="LIVESTOCK_MARKET_ELIGIBILITY_ENGINE",
            )
            decision = DecisionService().decide(evaluation, authority)
            self.evaluation_repository.save(evaluation)
            if self.authority_profile_repository is not None:
                self.authority_profile_repository.save(authority)
            self.decision_repository.save(decision)
            return MarketRequirementResult(
                rule_code=requirement.rule_code,
                scope=requirement.scope,
                status=_status_from_decision(decision.result),
                gaps=(),
                governed_rule=governed_rule,
                adoption=adoption_summary,
                rule_version=rule_version,
                execution=MarketExecutionSummary.from_ids(
                    evaluation.evaluation_id,
                    decision.decision_id,
                ),
                projection_status=projection_status,
                used_policy=MarketPolicySummary.from_policy(policy),
                current_policy=(
                    None
                    if current_policy is None
                    else MarketPolicySummary.from_policy(current_policy)
                ),
                dependency=dependency,
                reasons=tuple(
                    MarketEligibilityReason.from_decision_reason(reason)
                    for reason in decision.reasons
                ),
            )

        assert base_result is not None
        return MarketRequirementResult(
            rule_code=requirement.rule_code,
            scope=requirement.scope,
            status=_status_from_decision(base_result),
            gaps=(),
            governed_rule=governed_rule,
            adoption=adoption_summary,
            rule_version=rule_version,
            projection_status=MarketProjectionStatus.ATUAL,
            dependency=dependency,
            reasons=tuple(
                MarketEligibilityReason.from_decision_reason(reason) for reason in base_reasons
            ),
        )


def _status_from_decision(result: DecisionResult) -> MarketEligibilityStatus:
    if result is DecisionResult.APROVADA:
        return MarketEligibilityStatus.ELEGIVEL
    if result is DecisionResult.REJEITADA:
        return MarketEligibilityStatus.NAO_ELEGIVEL
    if result is DecisionResult.APROVADA_COM_RESTRICOES:
        return MarketEligibilityStatus.CONDICIONADO
    return MarketEligibilityStatus.INDETERMINADO


def _aggregate_requirement_status(
    requirements: Sequence[MarketRequirementResult],
) -> MarketEligibilityStatus:
    statuses = {requirement.status for requirement in requirements}
    for candidate in (
        MarketEligibilityStatus.NAO_ELEGIVEL,
        MarketEligibilityStatus.AUSENTE,
        MarketEligibilityStatus.INDETERMINADO,
        MarketEligibilityStatus.CONDICIONADO,
    ):
        if candidate in statuses:
            return candidate
    return MarketEligibilityStatus.ELEGIVEL


def _aggregate_projection_status(
    requirements: Sequence[MarketRequirementResult],
) -> MarketProjectionStatus:
    if any(
        requirement.projection_status is MarketProjectionStatus.REAVALIACAO_NECESSARIA
        for requirement in requirements
    ):
        return MarketProjectionStatus.REAVALIACAO_NECESSARIA
    return MarketProjectionStatus.ATUAL


def _projection_status_from_policies(
    used_policy: Policy,
    current_policy: Policy | None,
) -> MarketProjectionStatus:
    if current_policy is None:
        return MarketProjectionStatus.ATUAL
    if current_policy.policy_id != used_policy.policy_id:
        return MarketProjectionStatus.REAVALIACAO_NECESSARIA
    return MarketProjectionStatus.ATUAL
