"""Matriz de elegibilidade comercial por mercado (ADR-0044)."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from packages.core_domain.decision import DecisionReason, DecisionResult
from packages.core_domain.rule_governance import RuleAdoption
from packages.livestock_application.eligibility import (
    ELIGIBILITY_RULE_ADOPTION_SCOPE,
    ELIGIBILITY_RULE_CODE,
    GovernedRuleReference,
)
from packages.shared_kernel import OrganizationId

EXPORT_MARKETS: tuple[str, ...] = (
    "exportacao-uniao-europeia",
    "exportacao-china",
    "exportacao-estados-unidos",
)
TRACEABILITY_RULE_CODE = "rule-rastreabilidade-minima"
SUPPORTED_BASE_DECISION_RULE_CODES = frozenset({ELIGIBILITY_RULE_CODE})


class MarketEligibilityStatus(Enum):
    ELEGIVEL = "ELEGIVEL"
    NAO_ELEGIVEL = "NAO_ELEGIVEL"
    CONDICIONADO = "CONDICIONADO"
    INDETERMINADO = "INDETERMINADO"
    AUSENTE = "AUSENTE"


class MarketEligibilityGapCode(Enum):
    REGRA_GOVERNADA_AUSENTE = "REGRA_GOVERNADA_AUSENTE"
    AVALIADOR_DE_REQUISITO_AUSENTE = "AVALIADOR_DE_REQUISITO_AUSENTE"


@dataclass(frozen=True, slots=True)
class MarketRequirement:
    rule_code: str
    scope: str

    def __post_init__(self) -> None:
        if not self.rule_code.strip():
            raise ValueError("rule_code do requisito de mercado nao pode ser vazio.")
        if not self.scope.strip():
            raise ValueError("scope do requisito de mercado nao pode ser vazio.")


@dataclass(frozen=True, slots=True)
class MarketProfile:
    market: str
    requirements: tuple[MarketRequirement, ...]

    def __post_init__(self) -> None:
        if not self.market.strip():
            raise ValueError("market do perfil nao pode ser vazio.")
        if not self.requirements:
            raise ValueError("perfil de mercado exige ao menos um requisito.")


DEFAULT_MARKET_PROFILES: tuple[MarketProfile, ...] = (
    MarketProfile(
        market="exportacao-uniao-europeia",
        requirements=(
            MarketRequirement(
                rule_code=ELIGIBILITY_RULE_CODE,
                scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
            ),
            MarketRequirement(
                rule_code=TRACEABILITY_RULE_CODE,
                scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
            ),
        ),
    ),
    MarketProfile(
        market="exportacao-china",
        requirements=(
            MarketRequirement(
                rule_code=ELIGIBILITY_RULE_CODE,
                scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
            ),
        ),
    ),
    MarketProfile(
        market="exportacao-estados-unidos",
        requirements=(
            MarketRequirement(
                rule_code=ELIGIBILITY_RULE_CODE,
                scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
            ),
        ),
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
class MarketRequirementResult:
    rule_code: str
    scope: str
    status: MarketEligibilityStatus
    reasons: tuple[MarketEligibilityReason, ...]
    gaps: tuple[MarketEligibilityGap, ...]
    governed_rule: GovernedRuleReference | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_code": self.rule_code,
            "scope": self.scope,
            "status": self.status.value,
            "governed_rule": None if self.governed_rule is None else self.governed_rule.to_dict(),
            "reasons": [reason.to_dict() for reason in self.reasons],
            "gaps": [gap.to_dict() for gap in self.gaps],
        }


@dataclass(frozen=True, slots=True)
class MarketEligibilityEntry:
    market: str
    status: MarketEligibilityStatus
    reasons: tuple[MarketEligibilityReason, ...]
    gaps: tuple[MarketEligibilityGap, ...] = ()
    governed_rule: GovernedRuleReference | None = None
    requirements: tuple[MarketRequirementResult, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "market": self.market,
            "status": self.status.value,
            "governed_rule": None if self.governed_rule is None else self.governed_rule.to_dict(),
            "reasons": [reason.to_dict() for reason in self.reasons],
            "gaps": [gap.to_dict() for gap in self.gaps],
            "requirements": [requirement.to_dict() for requirement in self.requirements],
        }


@dataclass(frozen=True, slots=True)
class MarketEligibilityMatrix:
    entries: tuple[MarketEligibilityEntry, ...]

    def to_dict(self) -> list[dict[str, object]]:
        return [entry.to_dict() for entry in self.entries]


@dataclass(frozen=True, slots=True)
class MarketEligibilityService:
    adoption_reader: MarketRuleAdoptionReaderPort
    profiles: Sequence[MarketProfile] = DEFAULT_MARKET_PROFILES

    def evaluate(
        self,
        organization_id: OrganizationId,
        base_result: DecisionResult,
        base_reasons: Sequence[DecisionReason],
    ) -> MarketEligibilityMatrix:
        entries = tuple(
            self._entry_for_profile(organization_id, profile, base_result, base_reasons)
            for profile in self.profiles
        )
        return MarketEligibilityMatrix(entries=entries)

    def _entry_for_profile(
        self,
        organization_id: OrganizationId,
        profile: MarketProfile,
        base_result: DecisionResult,
        base_reasons: Sequence[DecisionReason],
    ) -> MarketEligibilityEntry:
        requirements = tuple(
            self._requirement_result(
                organization_id,
                profile.market,
                requirement,
                base_result,
                base_reasons,
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
            governed_rule=first_governed_rule,
            reasons=reasons,
            gaps=gaps,
            requirements=requirements,
        )

    def _requirement_result(
        self,
        organization_id: OrganizationId,
        market: str,
        requirement: MarketRequirement,
        base_result: DecisionResult,
        base_reasons: Sequence[DecisionReason],
    ) -> MarketRequirementResult:
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
        if requirement.rule_code not in SUPPORTED_BASE_DECISION_RULE_CODES:
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
                reasons=(),
            )

        return MarketRequirementResult(
            rule_code=requirement.rule_code,
            scope=requirement.scope,
            status=_status_from_decision(base_result),
            gaps=(),
            governed_rule=governed_rule,
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
