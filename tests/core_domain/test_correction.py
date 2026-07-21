from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from packages.core_domain import ChangeKind, Correction, build_correction
from packages.shared_kernel import TypedId
from tests.core_domain.test_domain_event import reference, valid_event

CORRECTED_AT = datetime(2026, 7, 21, 20, 0, tzinfo=UTC)


def test_correction_references_and_preserves_original_event() -> None:
    original = valid_event()
    original_bytes = original.payload.canonical_bytes

    correction = build_correction(
        correction_event_id=TypedId.new("domain_event"),
        original=original,
        aggregate_version=4,
        change_kind=ChangeKind.CORRECAO_DE_ERRO,
        justification="Valor declarado incorretamente.",
        new_content={"status": "corrigido"},
        corrected_at=CORRECTED_AT,
        actor_reference=reference("actor", original.organization_id),
        source_reference=reference("source", original.organization_id),
        correlation_id=TypedId.new("correlation"),
    )

    assert correction.corrected_event_id == original.event_id
    assert correction.event.causation_id == original.event_id
    assert correction.event.aggregate_reference == original.aggregate_reference
    assert correction.event.aggregate_version == 4
    assert correction.event.event_type == "registro_corrigido"
    assert original.payload.canonical_bytes == original_bytes
    with pytest.raises(FrozenInstanceError):
        correction.justification = "outra"  # type: ignore[misc]


def test_correction_rejects_empty_reason_content_and_non_later_version() -> None:
    original = valid_event()

    def create(
        *, aggregate_version: int, justification: str, new_content: dict[str, int]
    ) -> Correction:
        return build_correction(
            correction_event_id=TypedId.new("domain_event"),
            original=original,
            aggregate_version=aggregate_version,
            change_kind=ChangeKind.COMPLEMENTACAO,
            justification=justification,
            new_content=new_content,
            corrected_at=CORRECTED_AT,
            actor_reference=reference("actor", original.organization_id),
            source_reference=reference("source", original.organization_id),
            correlation_id=TypedId.new("correlation"),
        )

    with pytest.raises(ValueError, match="justification"):
        create(aggregate_version=4, justification=" ", new_content={"x": 1})
    with pytest.raises(ValueError, match="new_content"):
        create(aggregate_version=4, justification="Complemento", new_content={})
    with pytest.raises(ValueError, match="versão posterior"):
        create(
            aggregate_version=original.aggregate_version,
            justification="Complemento",
            new_content={"x": 1},
        )
