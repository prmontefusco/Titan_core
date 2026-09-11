"""Testes unitários de domínio para `Applicability` (A2).

Cobre I‑APP‑1 (evidência obrigatória; nunca aplicabilidade booleana) e I‑APP‑2
(retirada por correção, não por delete). `docs/asset/07_INVARIANTS.md`.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.asset_domain.applicability import (
    AplicabilidadeJaRetirada,
    Applicability,
    ApplicabilityState,
    ApplicabilityTarget,
)
from packages.shared_kernel import OrganizationId, TypedId

MOMENTO = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def _target(**overrides: object) -> ApplicabilityTarget:
    defaults: dict[str, object] = dict(
        model_ref=TypedId.new("vehicle_model"),
        variant_ref=None,
        serial_from=None,
        serial_to=None,
        valid_from=MOMENTO,
        valid_until=None,
    )
    defaults.update(overrides)
    return ApplicabilityTarget(**defaults)  # type: ignore[arg-type]


def _applicability(**overrides: object) -> Applicability:
    defaults: dict[str, object] = dict(
        applicability_id=TypedId.new("applicability"),
        organization_id=OrganizationId(uuid4()),
        part_ref=TypedId.new("part"),
        part_revision_ref=TypedId.new("part_revision"),
        target=_target(),
        evidence_ref=TypedId.new("evidence"),
        asserted_at=MOMENTO,
        asserted_by=TypedId.new("user"),
    )
    defaults.update(overrides)
    return Applicability(**defaults)  # type: ignore[arg-type]


# --- I-APP-1 ----------------------------------------------------------------------


def test_applicability_requires_evidence_of_the_right_type() -> None:
    with pytest.raises(ValueError, match="entity_type 'evidence'"):
        _applicability(evidence_ref=TypedId.new("document"))


def test_applicability_asserted_never_answers_only_true() -> None:
    """A garantia estrutural de I-APP-1: consultar uma Applicability sempre
    devolve o objeto com evidence_ref, nunca um bool solto."""
    applicability = _applicability()
    assert applicability.state is ApplicabilityState.ASSERTED
    assert applicability.evidence_ref is not None
    assert isinstance(applicability.evidence_ref, TypedId)


def test_applicability_target_covers_instant_within_effectivity() -> None:
    target = _target(valid_from=MOMENTO, valid_until=datetime(2027, 1, 1, tzinfo=UTC))
    assert target.covers(at=datetime(2026, 12, 1, tzinfo=UTC)) is True
    assert target.covers(at=datetime(2025, 1, 1, tzinfo=UTC)) is False
    assert target.covers(at=datetime(2027, 1, 1, tzinfo=UTC)) is False  # limite exclusivo


def test_applicability_target_open_ended_covers_indefinitely() -> None:
    target = _target(valid_from=MOMENTO, valid_until=None)
    assert target.covers(at=datetime(2030, 1, 1, tzinfo=UTC)) is True


def test_target_rejects_valid_until_before_valid_from() -> None:
    with pytest.raises(ValueError, match="valid_until deve ser posterior"):
        _target(valid_from=MOMENTO, valid_until=datetime(2020, 1, 1, tzinfo=UTC))


def test_is_active_at_requires_both_asserted_state_and_effectivity() -> None:
    applicability = _applicability(target=_target(valid_from=MOMENTO, valid_until=None))
    assert applicability.is_active_at(datetime(2026, 12, 1, tzinfo=UTC)) is True
    assert applicability.is_active_at(datetime(2020, 1, 1, tzinfo=UTC)) is False


# --- I-APP-2 ----------------------------------------------------------------------


def test_withdraw_preserves_original_and_marks_withdrawn() -> None:
    applicability = _applicability()
    withdrawn = applicability.withdraw(
        reason="Peça deixou de ser aplicável após retrofit.", withdrawn_at=MOMENTO
    )

    assert withdrawn.state is ApplicabilityState.WITHDRAWN
    assert withdrawn.withdrawal_reason is not None
    # O agregado original (não mutado) continua ASSERTED — imutabilidade padrão
    # do domínio; é o event log quem preserva o evento "asserted" original.
    assert applicability.state is ApplicabilityState.ASSERTED


def test_withdraw_requires_reason() -> None:
    applicability = _applicability()
    with pytest.raises(ValueError, match="reason é obrigatório"):
        applicability.withdraw(reason="  ", withdrawn_at=MOMENTO)


def test_withdraw_twice_is_rejected() -> None:
    applicability = _applicability().withdraw(reason="motivo", withdrawn_at=MOMENTO)
    with pytest.raises(AplicabilidadeJaRetirada):
        applicability.withdraw(reason="outro motivo", withdrawn_at=MOMENTO)


def test_is_active_at_is_false_after_withdrawal() -> None:
    applicability = _applicability().withdraw(reason="motivo", withdrawn_at=MOMENTO)
    assert applicability.is_active_at(datetime(2026, 12, 1, tzinfo=UTC)) is False


def test_withdrawal_fields_require_withdrawn_state() -> None:
    with pytest.raises(ValueError, match="só fazem sentido em state WITHDRAWN"):
        _applicability(withdrawal_reason="motivo")
