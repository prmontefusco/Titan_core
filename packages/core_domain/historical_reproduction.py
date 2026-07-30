"""Modelo de domínio imutável para reprodução histórica de Evaluation (ADR-0052).

`ReproductionReport` corresponde ao conceito `HistoricalReproduction` já
formalizado em `DOMAIN.md`: "Reexecução de snapshot, Policy, Rules,
NormativeBasisSnapshot e versão do motor originais para verificar
reprodutibilidade técnica. Produz relatório imutável. Divergência é registrada
e investigada; Evaluation e Decision originais não são substituídas."
"""

from dataclasses import dataclass
from datetime import datetime

from packages.core_domain.evaluation import EvaluationOutcome
from packages.shared_kernel import OrganizationId, TypedId


@dataclass(frozen=True, slots=True)
class ReproductionReport:
    """Relatório imutável de uma tentativa de reprodução histórica.

    Nunca substitui a Evaluation original nem produz nova Evaluation: é uma
    conclusão sobre reprodutibilidade técnica, não uma nova avaliação normativa.
    """

    report_id: TypedId
    organization_id: OrganizationId
    evaluation_id: TypedId
    reproduced_at: datetime
    context_hash_matches: bool
    evaluation_hash_matches: bool
    outcome_matches: bool
    original_outcome: EvaluationOutcome
    reproduced_outcome: EvaluationOutcome
    divergences: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.report_id.entity_type != "reproduction_report":
            raise ValueError("report_id deve ser do tipo 'reproduction_report'.")
        if self.evaluation_id.entity_type != "evaluation":
            raise ValueError("evaluation_id deve ser do tipo 'evaluation'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.reproduced_at, datetime):
            raise TypeError("reproduced_at deve ser um datetime.")
        if not isinstance(self.original_outcome, EvaluationOutcome):
            raise TypeError("original_outcome deve ser um EvaluationOutcome válido.")
        if not isinstance(self.reproduced_outcome, EvaluationOutcome):
            raise TypeError("reproduced_outcome deve ser um EvaluationOutcome válido.")
        if not isinstance(self.divergences, tuple):
            raise TypeError("divergences deve ser uma tupla.")
        if not isinstance(self.limitations, tuple):
            raise TypeError("limitations deve ser uma tupla.")
        # Consistência interna: "casa" só quando as três dimensões concordam, nunca
        # por conveniência de quem monta o relatório fora deste construtor.
        expected_matches = (
            self.context_hash_matches and self.evaluation_hash_matches and self.outcome_matches
        )
        if expected_matches and self.divergences:
            raise ValueError("Relatório sem divergência não pode carregar divergências.")
        if not expected_matches and not self.divergences:
            raise ValueError("Relatório com alguma divergência exige ao menos uma descrição.")

    @property
    def matches(self) -> bool:
        return self.context_hash_matches and self.evaluation_hash_matches and self.outcome_matches
