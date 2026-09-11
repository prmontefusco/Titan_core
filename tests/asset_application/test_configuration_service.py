"""Testes do `ConfigurationService` — Titan Asset (A4)."""

from datetime import UTC, datetime

import pytest

from packages.asset_application.configuration_service import (
    ConfigurationBaselineRepositoryPort,
    ConfigurationService,
)
from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.configuration import ConfigurationBaseline, Effectivity
from packages.asset_domain.events import (
    CONFIGURATION_BASELINE_PUBLISHED,
    CONFIGURATION_BASELINE_SUPERSEDED,
)
from packages.shared_kernel import TypedId
from tests.asset_support import FakeEventLog

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class InMemoryConfigurationBaselineRepository(ConfigurationBaselineRepositoryPort):
    def __init__(self) -> None:
        self.baselines: dict[str, ConfigurationBaseline] = {}

    def save(self, baseline: ConfigurationBaseline) -> None:
        self.baselines[baseline.baseline_id.value.hex] = baseline

    def get_by_id(self, baseline_id: TypedId) -> ConfigurationBaseline | None:
        return self.baselines.get(baseline_id.value.hex)

    def list_by_model(
        self, model_ref: TypedId, variant_ref: TypedId | None
    ) -> tuple[ConfigurationBaseline, ...]:
        return tuple(
            baseline
            for baseline in self.baselines.values()
            if baseline.model_ref == model_ref and baseline.variant_ref == variant_ref
        )


def test_publish_first_baseline(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = ConfigurationService(
        repository=InMemoryConfigurationBaselineRepository(), recorder=recorder
    )
    model_ref = TypedId.new("vehicle_model")

    baseline = service.publish_baseline(
        context,
        model_ref=model_ref,
        revision_number=1,
        effectivity=Effectivity(valid_from=datetime(2026, 1, 1, tzinfo=UTC)),
        occurred_at=OCCURRED_AT,
    )

    assert baseline.revision.number == 1
    assert baseline.revision.supersedes_ref is None
    event_log.only(CONFIGURATION_BASELINE_PUBLISHED)
    assert service.get_baseline(baseline.baseline_id) == baseline


def test_publish_superseding_baseline_requires_reason(
    recorder: AssetEventRecorder, context: AssetOperationContext
) -> None:
    service = ConfigurationService(
        repository=InMemoryConfigurationBaselineRepository(), recorder=recorder
    )
    model_ref = TypedId.new("vehicle_model")
    first = service.publish_baseline(
        context,
        model_ref=model_ref,
        revision_number=1,
        effectivity=Effectivity(valid_from=datetime(2026, 1, 1, tzinfo=UTC)),
        occurred_at=OCCURRED_AT,
    )

    with pytest.raises(ValueError, match="reason é obrigatório"):
        service.publish_baseline(
            context,
            model_ref=model_ref,
            revision_number=2,
            effectivity=Effectivity(valid_from=datetime(2026, 6, 1, tzinfo=UTC)),
            supersedes_ref=first.baseline_id,
            occurred_at=OCCURRED_AT,
        )


def test_publish_superseding_baseline_emits_both_events(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = ConfigurationService(
        repository=InMemoryConfigurationBaselineRepository(), recorder=recorder
    )
    model_ref = TypedId.new("vehicle_model")
    first = service.publish_baseline(
        context,
        model_ref=model_ref,
        revision_number=1,
        effectivity=Effectivity(valid_from=datetime(2026, 1, 1, tzinfo=UTC)),
        occurred_at=OCCURRED_AT,
    )

    second = service.publish_baseline(
        context,
        model_ref=model_ref,
        revision_number=2,
        effectivity=Effectivity(valid_from=datetime(2026, 6, 1, tzinfo=UTC)),
        supersedes_ref=first.baseline_id,
        reason="Correção de posição incorreta na baseline 1.",
        occurred_at=OCCURRED_AT,
    )

    assert second.revision.supersedes_ref == first.baseline_id
    published_events = event_log.of_type(CONFIGURATION_BASELINE_PUBLISHED)
    assert len(published_events) == 2
    superseded_event = event_log.only(CONFIGURATION_BASELINE_SUPERSEDED)
    assert superseded_event.aggregate_reference.target_id == first.baseline_id
