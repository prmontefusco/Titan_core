"""Caso de uso do agregado `ConfigurationBaseline` — Titan Asset (A4).

`ConfigurationBaseline` é imutável e publicada uma vez só (`configuration.py`)
— `PublishConfigurationBaseline` e `SupersedeConfigurationRevision`
(`09_COMMAND_MODEL.md`) são a **mesma** operação de domínio (`publish_baseline`
aqui): a diferença é só se `revision.supersedes_ref` é informado. I-CFG-1
(`require_acyclic_revision_chain`) e I-CFG-2 (`require_no_overlapping_effectivity`)
são funções puras cross-agregado — cabe à aplicação buscar o histórico
relevante (`repository.list_by_model`, A4) e chamá-las **antes** de persistir.

Quando `supersedes_ref` é informado, além de `configuration.baseline_published`
(sujeito: a baseline nova) emite `configuration.baseline_superseded` — cujo
sujeito é a baseline **anterior** (`08_DOMAIN_EVENTS.md`: `baseline_id` é a
antiga, `superseded_by_ref` aponta para a nova). `reason` é obrigatório nesse
caso (`09_COMMAND_MODEL.md`: "Valida: `reason`") — é dado de auditoria do
evento, não campo do domínio (`ConfigurationRevision` não guarda motivo).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.configuration import (
    BaselinePosition,
    ConfigurationBaseline,
    ConfigurationRevision,
    ConfigurationView,
    Effectivity,
    require_acyclic_revision_chain,
    require_no_overlapping_effectivity,
)
from packages.asset_domain.events import (
    CONFIGURATION_BASELINE_PUBLISHED,
    CONFIGURATION_BASELINE_SUPERSEDED,
    configuration_baseline_published_payload,
    configuration_baseline_superseded_payload,
)
from packages.shared_kernel import TypedId


class ConfigurationBaselineRepositoryPort(Protocol):
    def save(self, baseline: ConfigurationBaseline) -> None: ...

    def get_by_id(self, baseline_id: TypedId) -> ConfigurationBaseline | None: ...

    def list_by_model(
        self, model_ref: TypedId, variant_ref: TypedId | None
    ) -> Sequence[ConfigurationBaseline]: ...


@dataclass(frozen=True, slots=True)
class ConfigurationService:
    repository: ConfigurationBaselineRepositoryPort
    recorder: AssetEventRecorder

    def publish_baseline(
        self,
        context: AssetOperationContext,
        *,
        model_ref: TypedId,
        revision_number: int,
        effectivity: Effectivity,
        positions: tuple[BaselinePosition, ...] = (),
        variant_ref: TypedId | None = None,
        view: ConfigurationView = ConfigurationView.AS_DESIGNED,
        supersedes_ref: TypedId | None = None,
        reason: str | None = None,
        occurred_at: datetime,
    ) -> ConfigurationBaseline:
        if supersedes_ref is not None and (reason is None or not reason.strip()):
            raise ValueError("reason é obrigatório ao superseder uma baseline (I-CFG-1).")

        candidate = ConfigurationBaseline(
            baseline_id=TypedId.new("configuration_baseline"),
            organization_id=context.organization_id,
            model_ref=model_ref,
            revision=ConfigurationRevision(number=revision_number, supersedes_ref=supersedes_ref),
            effectivity=effectivity,
            positions=positions,
            variant_ref=variant_ref,
            view=view,
        )

        history = self.repository.list_by_model(model_ref, variant_ref)
        require_acyclic_revision_chain(candidate, history)
        require_no_overlapping_effectivity(candidate, history)

        self.repository.save(candidate)
        self.recorder.record(
            context=context,
            aggregate_id=candidate.baseline_id,
            event_type=CONFIGURATION_BASELINE_PUBLISHED,
            payload=configuration_baseline_published_payload(
                baseline_id=candidate.baseline_id,
                model_ref=model_ref,
                variant_ref=variant_ref,
                revision_number=revision_number,
                supersedes_ref=supersedes_ref,
                valid_from=effectivity.valid_from,
            ),
            occurred_at=occurred_at,
        )

        if supersedes_ref is not None:
            assert reason is not None
            self.recorder.record(
                context=context,
                aggregate_id=supersedes_ref,
                event_type=CONFIGURATION_BASELINE_SUPERSEDED,
                payload=configuration_baseline_superseded_payload(
                    baseline_id=supersedes_ref,
                    superseded_by_ref=candidate.baseline_id,
                    reason=reason,
                ),
                occurred_at=occurred_at,
            )

        return candidate

    def get_baseline(self, baseline_id: TypedId) -> ConfigurationBaseline | None:
        return self.repository.get_by_id(baseline_id)
