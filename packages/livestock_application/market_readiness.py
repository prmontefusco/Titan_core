"""Projeção pura de readiness para candidatos de mercado (NEXT-06/Corte 1)."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from packages.core_domain.decision import Decision, DecisionResult
from packages.core_domain.evaluation import Evaluation
from packages.livestock_application.lot_service import (
    LivestockLotRepositoryPort,
    LotMembershipRepositoryPort,
)
from packages.livestock_application.requirement_authority import RecognitionBoundary
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc

MARKET_ELIGIBILITY_RESULT_BOUNDARY = "MARKET_ELIGIBILITY_ASSESSMENT_NOT_EXPORT_AUTHORIZATION"
SELECTION_STRATEGY_STABLE_SUBJECT_ID = "STABLE_SUBJECT_ID"
SELECTION_STRATEGY_VERSION = 1
_RECOGNITION_BOUNDARY_PREFIX = "RECOGNITION_BOUNDARY:"


class MarketReadinessStatus(StrEnum):
    """Utilidade operacional de uma conclusão individual, nunca DecisionResult."""

    READY = "READY"
    NOT_READY = "NOT_READY"
    CONDITIONED = "CONDITIONED"
    INDETERMINATE = "INDETERMINATE"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    NOT_EVALUATED = "NOT_EVALUATED"


class MarketReadinessDecisionReaderPort(Protocol):
    def list_by_subject(
        self,
        organization_id: OrganizationId,
        subject_id: TypedId,
    ) -> list[Decision]: ...


class MarketReadinessEvaluationReaderPort(Protocol):
    def get_by_id(self, evaluation_id: TypedId) -> Evaluation | None: ...


@dataclass(frozen=True, slots=True)
class MarketReadinessContext:
    """Pergunta normativa homogênea que delimita uma projeção de readiness."""

    organization_id: OrganizationId
    purpose: str
    policy_id: TypedId
    policy_version: int
    reference_time: datetime
    knowledge_cutoff: datetime
    recognition_boundary: RecognitionBoundary = RecognitionBoundary.INTERNAL_ONLY
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY

    def __post_init__(self) -> None:
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ter entity_type 'policy'.")
        if not isinstance(self.policy_version, int) or self.policy_version < 1:
            raise ValueError("policy_version deve ser inteiro >= 1.")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ValueError("purpose deve ser texto não vazio.")
        require_utc(self.reference_time, field_name="reference_time")
        require_utc(self.knowledge_cutoff, field_name="knowledge_cutoff")
        if self.knowledge_cutoff < self.reference_time:
            raise ValueError("knowledge_cutoff não pode ser anterior a reference_time.")
        if self.recognition_boundary is not RecognitionBoundary.INTERNAL_ONLY:
            raise ValueError("O Corte 1 suporta somente a boundary INTERNAL_ONLY.")
        if self.result_boundary != MARKET_ELIGIBILITY_RESULT_BOUNDARY:
            raise ValueError(
                "result_boundary do Corte 1 deve preservar o limite de Market Eligibility."
            )


@dataclass(frozen=True, slots=True)
class MarketReadinessInput:
    """Material já emitido para um Animal, sem executar nova avaliação."""

    subject_id: TypedId
    decision: Decision | None = None
    evaluation: Evaluation | None = None

    def __post_init__(self) -> None:
        if self.subject_id.entity_type != "animal":
            raise ValueError("O Corte 1 aceita somente subject_id do tipo 'animal'.")
        if (self.decision is None) != (self.evaluation is None):
            raise ValueError("decision e evaluation devem ser informadas juntas ou ambas ausentes.")
        if self.decision is not None and self.evaluation is not None:
            if (
                self.decision.subject_id != self.subject_id
                or self.evaluation.subject_id != self.subject_id
            ):
                raise ValueError(
                    "Decision, Evaluation e subject_id devem identificar o mesmo Animal."
                )
            if self.decision.evaluation_id != self.evaluation.evaluation_id:
                raise ValueError("Decision deve referenciar a Evaluation informada.")
            if self.decision.evaluation_hash != self.evaluation.evaluation_hash:
                raise ValueError("Decision deve preservar o hash da Evaluation informada.")


@dataclass(frozen=True, slots=True)
class MarketReadinessEntry:
    subject_id: TypedId
    status: MarketReadinessStatus
    decision_id: TypedId | None
    evaluation_id: TypedId | None
    reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY

    @property
    def is_candidate(self) -> bool:
        """READY é utilizável somente para seleção neste contexto Titan."""
        return self.status is MarketReadinessStatus.READY


@dataclass(frozen=True, slots=True)
class MarketReadinessGapSummary:
    code: str
    count: int
    example_subject_ids: tuple[TypedId, ...]


@dataclass(frozen=True, slots=True)
class MarketReadinessReport:
    context: MarketReadinessContext
    entries: tuple[MarketReadinessEntry, ...]
    counts: dict[MarketReadinessStatus, int]
    gap_summary: tuple[MarketReadinessGapSummary, ...]
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY


@dataclass(frozen=True, slots=True)
class MarketCandidateSelection:
    context: MarketReadinessContext
    requested_count: int
    available_count: int
    shortage: int
    selected_entries: tuple[MarketReadinessEntry, ...]
    selection_strategy: str = SELECTION_STRATEGY_STABLE_SUBJECT_ID
    selection_strategy_version: int = SELECTION_STRATEGY_VERSION
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY


@dataclass(frozen=True, slots=True)
class MarketReadinessService:
    """Deriva utilidade contextual; nunca reconsidera a semântica da Decision."""

    def build_report(
        self,
        *,
        context: MarketReadinessContext,
        inputs: tuple[MarketReadinessInput, ...],
    ) -> MarketReadinessReport:
        subject_ids = [item.subject_id for item in inputs]
        if len(set(subject_ids)) != len(subject_ids):
            raise ValueError("A população de readiness não pode conter Animal repetido.")

        entries = tuple(
            sorted(
                (self._entry_for(context=context, item=item) for item in inputs),
                key=lambda item: str(item.subject_id.value),
            )
        )
        counts = Counter(entry.status for entry in entries)
        return MarketReadinessReport(
            context=context,
            entries=entries,
            counts={status: counts[status] for status in MarketReadinessStatus},
            gap_summary=_gap_summary(entries),
        )

    def select_candidates(
        self,
        *,
        report: MarketReadinessReport,
        requested_count: int,
    ) -> MarketCandidateSelection:
        if not isinstance(requested_count, int) or requested_count < 1:
            raise ValueError("requested_count deve ser inteiro >= 1.")
        eligible = tuple(entry for entry in report.entries if entry.is_candidate)
        selected = eligible[:requested_count]
        return MarketCandidateSelection(
            context=report.context,
            requested_count=requested_count,
            available_count=len(eligible),
            shortage=max(0, requested_count - len(selected)),
            selected_entries=selected,
        )

    def _entry_for(
        self,
        *,
        context: MarketReadinessContext,
        item: MarketReadinessInput,
    ) -> MarketReadinessEntry:
        if item.decision is None or item.evaluation is None:
            return _entry(item.subject_id, MarketReadinessStatus.NOT_EVALUATED, ("NOT_EVALUATED",))

        decision = item.decision
        evaluation = item.evaluation
        if (
            decision.organization_id != context.organization_id
            or evaluation.organization_id != context.organization_id
        ):
            raise ValueError("Decision e Evaluation devem pertencer à Organization do contexto.")

        if not _matches_identity_context(context=context, decision=decision, evaluation=evaluation):
            return _entry(
                item.subject_id,
                MarketReadinessStatus.REASSESSMENT_REQUIRED,
                ("CONTEXT_MISMATCH_REASSESSMENT_REQUIRED",),
            )

        limitations = evaluation.normative_limitations
        if limitations:
            return _entry(
                item.subject_id,
                MarketReadinessStatus.INDETERMINATE,
                ("NORMATIVE_BASIS_SNAPSHOT_UNAVAILABLE",),
                limitations,
                decision,
                evaluation,
            )

        normative = evaluation.normative_basis_snapshot
        assert normative is not None
        if (
            normative.reference_time != context.reference_time
            or normative.knowledge_cutoff != context.knowledge_cutoff
        ):
            return _entry(
                item.subject_id,
                MarketReadinessStatus.REASSESSMENT_REQUIRED,
                ("CONTEXT_MISMATCH_REASSESSMENT_REQUIRED",),
                decision=decision,
                evaluation=evaluation,
            )

        if _recognition_boundary(evaluation) is not context.recognition_boundary:
            return _entry(
                item.subject_id,
                MarketReadinessStatus.INDETERMINATE,
                ("RECOGNITION_BOUNDARY_UNAVAILABLE",),
                decision=decision,
                evaluation=evaluation,
            )

        status = {
            DecisionResult.APROVADA: MarketReadinessStatus.READY,
            DecisionResult.REJEITADA: MarketReadinessStatus.NOT_READY,
            DecisionResult.APROVADA_COM_RESTRICOES: MarketReadinessStatus.CONDITIONED,
            DecisionResult.INDETERMINADA: MarketReadinessStatus.INDETERMINATE,
        }[decision.result]
        return _entry(
            item.subject_id,
            status,
            tuple(reason.code.value for reason in decision.reasons),
            decision=decision,
            evaluation=evaluation,
        )


def _matches_identity_context(
    *,
    context: MarketReadinessContext,
    decision: Decision,
    evaluation: Evaluation,
) -> bool:
    return (
        decision.subject_id == evaluation.subject_id
        and decision.purpose == context.purpose
        and evaluation.purpose == context.purpose
        and decision.policy_id == context.policy_id
        and evaluation.policy_id == context.policy_id
        and decision.policy_version == context.policy_version
        and evaluation.policy_version == context.policy_version
    )


def _recognition_boundary(evaluation: Evaluation) -> RecognitionBoundary | None:
    normative = evaluation.normative_basis_snapshot
    if normative is None:
        return None
    values = [
        limitation.removeprefix(_RECOGNITION_BOUNDARY_PREFIX)
        for limitation in normative.limitations
        if limitation.startswith(_RECOGNITION_BOUNDARY_PREFIX)
    ]
    if len(values) != 1:
        return None
    try:
        return RecognitionBoundary(values[0])
    except ValueError:
        return None


def _entry(
    subject_id: TypedId,
    status: MarketReadinessStatus,
    reason_codes: tuple[str, ...],
    limitations: tuple[str, ...] = (),
    decision: Decision | None = None,
    evaluation: Evaluation | None = None,
) -> MarketReadinessEntry:
    return MarketReadinessEntry(
        subject_id=subject_id,
        status=status,
        decision_id=None if decision is None else decision.decision_id,
        evaluation_id=None if evaluation is None else evaluation.evaluation_id,
        reason_codes=reason_codes,
        limitations=limitations,
    )


def _gap_summary(
    entries: tuple[MarketReadinessEntry, ...],
) -> tuple[MarketReadinessGapSummary, ...]:
    subjects_by_code: defaultdict[str, list[TypedId]] = defaultdict(list)
    for entry in entries:
        if entry.status is MarketReadinessStatus.READY:
            continue
        for code in (*entry.reason_codes, *entry.limitations):
            subjects_by_code[code].append(entry.subject_id)
    return tuple(
        MarketReadinessGapSummary(
            code=code,
            count=len(subjects),
            example_subject_ids=tuple(sorted(subjects, key=lambda item: str(item.value))[:3]),
        )
        for code, subjects in sorted(subjects_by_code.items())
    )


@dataclass(frozen=True, slots=True)
class MarketReadinessPopulationReader:
    """Lê população e conclusões existentes; não avalia, não grava e não reserva."""

    decision_repository: MarketReadinessDecisionReaderPort
    evaluation_repository: MarketReadinessEvaluationReaderPort
    readiness_service: MarketReadinessService
    lot_repository: LivestockLotRepositoryPort | None = None
    membership_repository: LotMembershipRepositoryPort | None = None

    def build_for_animals(
        self,
        *,
        context: MarketReadinessContext,
        animal_ids: tuple[TypedId, ...],
    ) -> MarketReadinessReport:
        return self.readiness_service.build_report(
            context=context,
            inputs=tuple(
                self._input_for(context=context, animal_id=animal_id) for animal_id in animal_ids
            ),
        )

    def build_for_lot(
        self,
        *,
        context: MarketReadinessContext,
        lot_id: TypedId,
    ) -> MarketReadinessReport:
        if self.lot_repository is None or self.membership_repository is None:
            raise ValueError("Leitura por lote exige os repositórios de lote e membership.")
        lot = self.lot_repository.get_by_id(lot_id)
        if lot is None or lot.organization_id != context.organization_id:
            raise KeyError("Lote não encontrado na Organization do contexto.")
        memberships = self.membership_repository.get_memberships_for_lot(
            lot_id,
            at_time=context.reference_time,
        )
        return self.build_for_animals(
            context=context,
            animal_ids=tuple(membership.animal_id for membership in memberships),
        )

    def _input_for(
        self,
        *,
        context: MarketReadinessContext,
        animal_id: TypedId,
    ) -> MarketReadinessInput:
        if animal_id.entity_type != "animal":
            raise ValueError("A população do Corte 2 aceita somente Animals.")
        candidates: list[tuple[Decision, Evaluation]] = []
        decisions = self.decision_repository.list_by_subject(context.organization_id, animal_id)
        for decision in decisions:
            evaluation = self.evaluation_repository.get_by_id(decision.evaluation_id)
            if evaluation is None:
                continue
            if _matches_exact_context(context=context, decision=decision, evaluation=evaluation):
                candidates.append((decision, evaluation))
        if len(candidates) > 1:
            raise ValueError(
                "Mais de uma Decision corresponde exatamente ao contexto de readiness."
            )
        if candidates:
            decision, evaluation = candidates[0]
            return MarketReadinessInput(animal_id, decision, evaluation)

        if not decisions:
            return MarketReadinessInput(animal_id)
        decision = decisions[0]
        evaluation = self.evaluation_repository.get_by_id(decision.evaluation_id)
        if evaluation is None:
            return MarketReadinessInput(animal_id)
        return MarketReadinessInput(animal_id, decision, evaluation)


def _matches_exact_context(
    *,
    context: MarketReadinessContext,
    decision: Decision,
    evaluation: Evaluation,
) -> bool:
    normative = evaluation.normative_basis_snapshot
    return (
        _matches_identity_context(context=context, decision=decision, evaluation=evaluation)
        and normative is not None
        and normative.reference_time == context.reference_time
        and normative.knowledge_cutoff == context.knowledge_cutoff
        and _recognition_boundary(evaluation) is context.recognition_boundary
    )
