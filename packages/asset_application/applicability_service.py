"""Caso de uso do agregado `Applicability` — Titan Asset (A4).

I-APP-1 (`evidence_ref` obrigatório) e I-APP-2 (retirada é correção, nunca
delete) já são garantidos pelo próprio `Applicability.__post_init__`/`withdraw`
— este serviço só monta o agregado e grava o evento correspondente, mesmo
padrão de `part_service.py`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.applicability import Applicability, ApplicabilityTarget
from packages.asset_domain.events import (
    APPLICABILITY_ASSERTED,
    APPLICABILITY_WITHDRAWN,
    applicability_asserted_payload,
    applicability_withdrawn_payload,
)
from packages.shared_kernel import TypedId


class ApplicabilityNaoEncontrada(KeyError):
    """`applicability_id` não corresponde a nenhuma `Applicability` desta Organization."""


class ApplicabilityRepositoryPort(Protocol):
    def save(self, applicability: Applicability) -> None: ...

    def update(self, applicability: Applicability) -> None: ...

    def get_by_id(self, applicability_id: TypedId) -> Applicability | None: ...


@dataclass(frozen=True, slots=True)
class ApplicabilityService:
    repository: ApplicabilityRepositoryPort
    recorder: AssetEventRecorder

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
        correction_ref: TypedId | None = None,
    ) -> Applicability:
        applicability = self._require(applicability_id)
        updated = applicability.withdraw(reason=reason, withdrawn_at=withdrawn_at)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.applicability_id,
            event_type=APPLICABILITY_WITHDRAWN,
            payload=applicability_withdrawn_payload(
                applicability_id=updated.applicability_id,
                reason=reason,
                correction_ref=correction_ref,
            ),
            occurred_at=withdrawn_at,
        )
        return updated

    def get_applicability(self, applicability_id: TypedId) -> Applicability | None:
        return self.repository.get_by_id(applicability_id)
