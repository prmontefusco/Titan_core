"""Assessment puro de impacto de mudança de Policy (NEXT-07/Corte 1)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from packages.core_domain.decision import Decision
from packages.core_domain.evaluation import Evaluation
from packages.livestock_application.market_readiness import (
    MARKET_ELIGIBILITY_RESULT_BOUNDARY,
    _recognition_boundary,
)
from packages.livestock_application.requirement_authority import RecognitionBoundary
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class MarketChangeImpactStatus(StrEnum):
    AFFECTED = "AFFECTED"
    UNRELATED = "UNRELATED"
    LIMITED = "LIMITED"


@dataclass(frozen=True, slots=True)
class MarketChangeImpactContext:
    organization_id: OrganizationId
    purpose: str
    previous_policy_id: TypedId
    previous_policy_version: int
    replacement_policy_id: TypedId
    replacement_policy_version: int
    reference_time: datetime
    knowledge_cutoff: datetime
    recognition_boundary: RecognitionBoundary = RecognitionBoundary.INTERNAL_ONLY

    def __post_init__(self) -> None:
        for policy_id in (self.previous_policy_id, self.replacement_policy_id):
            if policy_id.entity_type != "policy":
                raise ValueError("Policies do impacto devem ter entity_type 'policy'.")
        if self.previous_policy_id == self.replacement_policy_id:
            raise ValueError("A Policy de substituição deve ser diferente da anterior.")
        if min(self.previous_policy_version, self.replacement_policy_version) < 1:
            raise ValueError("Versões de Policy devem ser >= 1.")
        if not self.purpose.strip():
            raise ValueError("purpose deve ser texto não vazio.")
        require_utc(self.reference_time, field_name="reference_time")
        require_utc(self.knowledge_cutoff, field_name="knowledge_cutoff")
        if self.knowledge_cutoff < self.reference_time:
            raise ValueError("knowledge_cutoff não pode ser anterior a reference_time.")
        if self.recognition_boundary is not RecognitionBoundary.INTERNAL_ONLY:
            raise ValueError("O Corte 1 suporta somente INTERNAL_ONLY.")


@dataclass(frozen=True, slots=True)
class MarketChangeImpactInput:
    decision: Decision
    evaluation: Evaluation

    def __post_init__(self) -> None:
        if self.decision.evaluation_id != self.evaluation.evaluation_id:
            raise ValueError("Decision deve referenciar a Evaluation informada.")
        if self.decision.evaluation_hash != self.evaluation.evaluation_hash:
            raise ValueError("Decision deve preservar o hash da Evaluation informada.")


@dataclass(frozen=True, slots=True)
class MarketChangeImpactEntry:
    subject_id: TypedId
    decision_id: TypedId
    evaluation_id: TypedId
    status: MarketChangeImpactStatus
    limitation: str | None = None


@dataclass(frozen=True, slots=True)
class MarketChangeImpactAssessment:
    context: MarketChangeImpactContext
    entries: tuple[MarketChangeImpactEntry, ...]
    reassessment_required_count: int
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY


@dataclass(frozen=True, slots=True)
class MarketChangeImpactService:
    """Identifica impacto potencial; nunca executa Policy ou altera histórico."""

    def assess(
        self,
        *,
        context: MarketChangeImpactContext,
        inputs: tuple[MarketChangeImpactInput, ...],
    ) -> MarketChangeImpactAssessment:
        entries = tuple(
            sorted(
                (self._entry(context=context, item=item) for item in inputs),
                key=lambda entry: (str(entry.subject_id.value), str(entry.decision_id.value)),
            )
        )
        return MarketChangeImpactAssessment(
            context=context,
            entries=entries,
            reassessment_required_count=sum(
                entry.status is MarketChangeImpactStatus.AFFECTED for entry in entries
            ),
        )

    def _entry(
        self,
        *,
        context: MarketChangeImpactContext,
        item: MarketChangeImpactInput,
    ) -> MarketChangeImpactEntry:
        decision, evaluation = item.decision, item.evaluation
        status = MarketChangeImpactStatus.UNRELATED
        limitation: str | None = None
        if (
            decision.organization_id == context.organization_id
            and evaluation.organization_id == context.organization_id
            and decision.purpose == context.purpose
            and evaluation.purpose == context.purpose
            and decision.policy_id == context.previous_policy_id
            and evaluation.policy_id == context.previous_policy_id
            and decision.policy_version == context.previous_policy_version
            and evaluation.policy_version == context.previous_policy_version
        ):
            normative = evaluation.normative_basis_snapshot
            if normative is None:
                status, limitation = (
                    MarketChangeImpactStatus.LIMITED,
                    "NORMATIVE_BASIS_SNAPSHOT_LEGACY_ABSENT",
                )
            elif (
                normative.reference_time != context.reference_time
                or normative.knowledge_cutoff != context.knowledge_cutoff
            ):
                status, limitation = MarketChangeImpactStatus.LIMITED, "TEMPORAL_CONTEXT_MISMATCH"
            elif _recognition_boundary(evaluation) is not context.recognition_boundary:
                status, limitation = (
                    MarketChangeImpactStatus.LIMITED,
                    "RECOGNITION_BOUNDARY_UNAVAILABLE",
                )
            else:
                status = MarketChangeImpactStatus.AFFECTED
        return MarketChangeImpactEntry(
            subject_id=decision.subject_id,
            decision_id=decision.decision_id,
            evaluation_id=evaluation.evaluation_id,
            status=status,
            limitation=limitation,
        )


class MarketChangeDecisionReaderPort(Protocol):
    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[Decision]: ...


class MarketChangeEvaluationReaderPort(Protocol):
    def get_by_id(self, evaluation_id: TypedId) -> Evaluation | None: ...


@dataclass(frozen=True, slots=True)
class MarketChangeImpactReader:
    """Lê pares históricos escolhidos pelo servidor; não cria plano nem reavalia."""

    decision_reader: MarketChangeDecisionReaderPort
    evaluation_reader: MarketChangeEvaluationReaderPort
    impact_service: MarketChangeImpactService

    def assess_for_animals(
        self,
        *,
        context: MarketChangeImpactContext,
        animal_ids: tuple[TypedId, ...],
    ) -> MarketChangeImpactAssessment:
        inputs: list[MarketChangeImpactInput] = []
        for animal_id in animal_ids:
            if animal_id.entity_type != "animal":
                raise ValueError("A consulta de impacto aceita somente Animals.")
            for decision in self.decision_reader.list_by_subject(
                context.organization_id, animal_id
            ):
                evaluation = self.evaluation_reader.get_by_id(decision.evaluation_id)
                if evaluation is not None:
                    inputs.append(MarketChangeImpactInput(decision, evaluation))
        return self.impact_service.assess(context=context, inputs=tuple(inputs))
