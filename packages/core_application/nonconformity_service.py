"""Casos de uso e porta para NonConformity (Passo 7.3)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain.evaluation import Evaluation, RuleResult, RuleResultStatus
from packages.core_domain.evidence import ValidityPeriod
from packages.core_domain.nonconformity import (
    NonConformity,
    NonConformityOrigin,
    NonConformityStatus,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

# Um resultado de regra vira não conformidade quando falha ou fica sem informação
# suficiente. Atendida e não aplicável não geram tratamento.
_ORIGIN_BY_RULE_STATUS: dict[RuleResultStatus, NonConformityOrigin] = {
    RuleResultStatus.NAO_ATENDIDA: NonConformityOrigin.REGRA_NAO_ATENDIDA,
    RuleResultStatus.PENDENTE: NonConformityOrigin.EVIDENCIA_AUSENTE,
    RuleResultStatus.INDETERMINADA: NonConformityOrigin.DIVERGENCIA_ENTRE_FONTES,
}


class NonConformityRepositoryPort(Protocol):
    def save(self, nonconformity: NonConformity) -> None: ...

    def get_by_id(self, nonconformity_id: TypedId) -> NonConformity | None: ...

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[NonConformity]: ...

    def list_open(self, organization_id: OrganizationId) -> list[NonConformity]: ...


@dataclass(frozen=True, slots=True)
class NonConformityService:
    """Abre, acompanha e encerra não conformidades sem apagar histórico."""

    repository: NonConformityRepositoryPort

    def open_from_evaluation(
        self, evaluation: Evaluation, detected_at: datetime | None = None
    ) -> list[NonConformity]:
        """Abre uma não conformidade para cada resultado de regra que exige tratamento.

        Regra atendida e regra não aplicável não geram registro: tratar o que não
        falhou transformaria a lista de pendências em ruído.
        """
        instante = detected_at or evaluation.evaluated_at
        abertas: list[NonConformity] = []

        for resultado in evaluation.rule_results:
            origem = _ORIGIN_BY_RULE_STATUS.get(resultado.status)
            if origem is None:
                continue
            abertas.append(self._open_from_rule_result(evaluation, resultado, origem, instante))
        return abertas

    def _open_from_rule_result(
        self,
        evaluation: Evaluation,
        resultado: RuleResult,
        origem: NonConformityOrigin,
        detected_at: datetime,
    ) -> NonConformity:
        nonconformity = NonConformity.detect(
            organization_id=evaluation.organization_id,
            subject_reference=UniversalReference(
                target_id=evaluation.subject_id,
                organization_id=evaluation.organization_id,
                contract_version=1,
            ),
            origin=origem,
            severity=resultado.severity,
            description=resultado.reason,
            detected_at=detected_at,
            # Aponta para a Evaluation que a originou: é o fio que leva de volta
            # aos fatos, evidências e eventos que a justificam.
            origin_reference=UniversalReference(
                target_id=evaluation.evaluation_id,
                organization_id=evaluation.organization_id,
                contract_version=1,
            ),
            affected_period=ValidityPeriod(valid_from=evaluation.fact_snapshot.as_of),
            corrective_action=resultado.corrective_action,
        )
        self.repository.save(nonconformity)
        return nonconformity

    def classify(
        self,
        nonconformity_id: TypedId,
        occurred_at: datetime,
        corrective_action: str = "",
        note: str = "",
    ) -> NonConformity:
        atual = self._load(nonconformity_id)
        proxima = atual.classify(
            occurred_at=occurred_at, corrective_action=corrective_action, note=note
        )
        self.repository.save(proxima)
        return proxima

    def assign(
        self,
        nonconformity_id: TypedId,
        responsible_reference: UniversalReference,
        due_date: datetime,
        occurred_at: datetime,
        note: str = "",
    ) -> NonConformity:
        atual = self._load(nonconformity_id)
        proxima = atual.assign(
            responsible_reference=responsible_reference,
            due_date=due_date,
            occurred_at=occurred_at,
            note=note,
        )
        self.repository.save(proxima)
        return proxima

    def start_correction(
        self, nonconformity_id: TypedId, occurred_at: datetime, note: str = ""
    ) -> NonConformity:
        proxima = self._load(nonconformity_id).start_correction(occurred_at, note=note)
        self.repository.save(proxima)
        return proxima

    def submit_for_reevaluation(
        self,
        nonconformity_id: TypedId,
        correction_evidence_references: list[UniversalReference],
        occurred_at: datetime,
        note: str = "",
    ) -> NonConformity:
        proxima = self._load(nonconformity_id).submit_for_reevaluation(
            correction_evidence_references, occurred_at, note=note
        )
        self.repository.save(proxima)
        return proxima

    def close_with_reevaluation(
        self,
        nonconformity_id: TypedId,
        reevaluation: Evaluation,
        occurred_at: datetime,
        note: str = "",
    ) -> NonConformity:
        """Encerra somente se a reavaliação confirmar a correção.

        Reavaliação que ainda aponta descumprimento devolve o caso à correção em
        vez de encerrá-lo: encerrar sem confirmação seria declarar resolvido o que
        não foi.
        """
        atual = self._load(nonconformity_id)
        if not reevaluation.is_reproducible():
            raise ValueError("Reavaliação não reproduzível: não pode sustentar encerramento.")

        ainda_falha = reevaluation.results_by_status(RuleResultStatus.NAO_ATENDIDA)
        if ainda_falha:
            proxima = atual.reject_reevaluation(
                occurred_at,
                note=note or "Reavaliação manteve descumprimento; caso devolvido à correção.",
            )
        else:
            proxima = atual.close(
                reevaluation_id=reevaluation.evaluation_id,
                occurred_at=occurred_at,
                note=note or "Reavaliação confirmou a correção.",
            )
        self.repository.save(proxima)
        return proxima

    def list_open(self, organization_id: OrganizationId) -> list[NonConformity]:
        return [
            n
            for n in self.repository.list_open(organization_id)
            if n.status is not NonConformityStatus.ENCERRADA
        ]

    def _load(self, nonconformity_id: TypedId) -> NonConformity:
        atual = self.repository.get_by_id(nonconformity_id)
        if atual is None:
            raise KeyError(f"Não conformidade {nonconformity_id.value} não encontrada.")
        return atual
