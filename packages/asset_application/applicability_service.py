"""Caso de uso do agregado `Applicability` — Titan Asset (A4).

I-APP-1 (`evidence_ref` obrigatório) e I-APP-2 (retirada é correção, nunca
delete) já são garantidos pelo próprio `Applicability.__post_init__`/`withdraw`
— este serviço só monta o agregado e grava o evento correspondente, mesmo
padrão de `part_service.py`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.asset_application.event_recorder import (
    AGGREGATE_CONTRACT_VERSION,
    AssetEventRecorder,
    AssetOperationContext,
)
from packages.asset_domain.applicability import Applicability, ApplicabilityTarget
from packages.asset_domain.events import (
    APPLICABILITY_ASSERTED,
    APPLICABILITY_WITHDRAWN,
    applicability_asserted_payload,
    applicability_withdrawn_payload,
)
from packages.core_application import OptimisticConcurrencyConflict
from packages.shared_kernel import TypedId, UniversalReference


class ApplicabilityNaoEncontrada(KeyError):
    """`applicability_id` não corresponde a nenhuma `Applicability` desta Organization."""


class AssercaoOriginalNaoEncontrada(RuntimeError):
    """O fluxo da Applicability não contém seu evento original de asserção."""


class ApplicabilityRepositoryPort(Protocol):
    def save(self, applicability: Applicability) -> None: ...

    def update(self, applicability: Applicability) -> None: ...

    def get_by_id(self, applicability_id: TypedId) -> Applicability | None: ...


class RecordedApplicabilityEvent(Protocol):
    @property
    def event_id(self) -> TypedId: ...

    @property
    def event_type(self) -> str: ...


class ApplicabilityEventReader(Protocol):
    def list_for_aggregate(
        self, aggregate_reference: UniversalReference
    ) -> Sequence[RecordedApplicabilityEvent]: ...


@dataclass(frozen=True, slots=True)
class ApplicabilityService:
    repository: ApplicabilityRepositoryPort
    recorder: AssetEventRecorder
    event_reader: ApplicabilityEventReader

    def _require(self, applicability_id: TypedId) -> Applicability:
        applicability = self.repository.get_by_id(applicability_id)
        if applicability is None:
            raise ApplicabilityNaoEncontrada(
                f"Applicability '{applicability_id.value}' não encontrada."
            )
        return applicability

    def assert_applicability(
        self,
        context: AssetOperationContext,
        *,
        part_ref: TypedId,
        part_revision_ref: TypedId,
        target: ApplicabilityTarget,
        evidence_ref: TypedId,
        asserted_at: datetime,
        asserted_by: TypedId,
    ) -> Applicability:
        applicability = Applicability(
            applicability_id=TypedId.new("applicability"),
            organization_id=context.organization_id,
            part_ref=part_ref,
            part_revision_ref=part_revision_ref,
            target=target,
            evidence_ref=evidence_ref,
            asserted_at=asserted_at,
            asserted_by=asserted_by,
        )
        self.repository.save(applicability)
        self.recorder.record(
            context=context,
            aggregate_id=applicability.applicability_id,
            event_type=APPLICABILITY_ASSERTED,
            payload=applicability_asserted_payload(
                applicability_id=applicability.applicability_id,
                part_ref=part_ref,
                part_revision_ref=part_revision_ref,
                model_ref=target.model_ref,
                variant_ref=target.variant_ref,
                evidence_ref=evidence_ref,
                asserted_at=asserted_at,
            ),
            occurred_at=asserted_at,
        )
        return applicability

    def withdraw_applicability(
        self,
        context: AssetOperationContext,
        applicability_id: TypedId,
        *,
        reason: str,
        withdrawn_at: datetime,
        expected_version: int | None = None,
    ) -> Applicability:
        applicability = self._require(applicability_id)
        if expected_version is not None and applicability.version != expected_version:
            raise OptimisticConcurrencyConflict()
        aggregate_reference = UniversalReference(
            target_id=applicability_id,
            organization_id=context.organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        assertion_event = next(
            (
                event
                for event in self.event_reader.list_for_aggregate(aggregate_reference)
                if event.event_type == APPLICABILITY_ASSERTED
            ),
            None,
        )
        if assertion_event is None:
            raise AssercaoOriginalNaoEncontrada(
                f"Evento original de Applicability '{applicability_id.value}' não encontrado."
            )
        updated = applicability.withdraw(reason=reason, withdrawn_at=withdrawn_at)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.applicability_id,
            event_type=APPLICABILITY_WITHDRAWN,
            payload=applicability_withdrawn_payload(
                applicability_id=updated.applicability_id,
                reason=reason,
            ),
            occurred_at=withdrawn_at,
            causation_id=assertion_event.event_id,
        )
        return updated

    def get_applicability(self, applicability_id: TypedId) -> Applicability | None:
        return self.repository.get_by_id(applicability_id)
