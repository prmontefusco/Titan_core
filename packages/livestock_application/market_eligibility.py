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


class MarketEligibilityStatus(Enum):
    ELEGIVEL = "ELEGIVEL"
    NAO_ELEGIVEL = "NAO_ELEGIVEL"
    CONDICIONADO = "CONDICIONADO"
    INDETERMINADO = "INDETERMINADO"
    AUSENTE = "AUSENTE"


class MarketEligibilityGapCode(Enum):
    REGRA_GOVERNADA_AUSENTE = "REGRA_GOVERNADA_AUSENTE"


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
class MarketEligibilityEntry:
    market: str
    status: MarketEligibilityStatus
    reasons: tuple[MarketEligibilityReason, ...]
    gaps: tuple[MarketEligibilityGap, ...] = ()
    governed_rule: GovernedRuleReference | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "market": self.market,
            "status": self.status.value,
            "governed_rule": None if self.governed_rule is None else self.governed_rule.to_dict(),
            "reasons": [reason.to_dict() for reason in self.reasons],
            "gaps": [gap.to_dict() for gap in self.gaps],
        }


@dataclass(frozen=True, slots=True)
class MarketEligibilityMatrix:
    entries: tuple[MarketEligibilityEntry, ...]

    def to_dict(self) -> list[dict[str, object]]:
        return [entry.to_dict() for entry in self.entries]


@dataclass(frozen=True, slots=True)
class MarketEligibilityService:
    adoption_reader: MarketRuleAdoptionReaderPort
    markets: Sequence[str] = EXPORT_MARKETS

    def evaluate(
        self,
        organization_id: OrganizationId,
        base_result: DecisionResult,
        base_reasons: Sequence[DecisionReason],
    ) -> MarketEligibilityMatrix:
        entries = tuple(
            self._entry_for_market(organization_id, market, base_result, base_reasons)
            for market in self.markets
        )
        return MarketEligibilityMatrix(entries=entries)

    def _entry_for_market(
        self,
        organization_id: OrganizationId,
        market: str,
        base_result: DecisionResult,
        base_reasons: Sequence[DecisionReason],
    ) -> MarketEligibilityEntry:
        adoption = self.adoption_reader.get_active_by_code_purpose_and_scope(
            organization_id,
            ELIGIBILITY_RULE_CODE,
            market,
            ELIGIBILITY_RULE_ADOPTION_SCOPE,
        )
        if adoption is None:
            return MarketEligibilityEntry(
                market=market,
                status=MarketEligibilityStatus.AUSENTE,
                reasons=(),
                gaps=(
                    MarketEligibilityGap(
                        code=MarketEligibilityGapCode.REGRA_GOVERNADA_AUSENTE,
                        message="Nenhuma regra governada adotada para este mercado.",
                    ),
                ),
            )

        return MarketEligibilityEntry(
            market=market,
            status=_status_from_decision(base_result),
            governed_rule=GovernedRuleReference(
                adoption_id=adoption.adoption_id,
                rule_identity_id=adoption.rule_identity_id,
                rule_version_id=adoption.rule_version_id,
                purpose=adoption.purpose,
                scope=adoption.scope,
            ),
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
