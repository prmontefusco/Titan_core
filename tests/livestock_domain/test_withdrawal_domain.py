"""Testes de domínio do cálculo de carência (Passo 9.4 - Titan Livestock)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.livestock_domain.withdrawal import (
    WITHDRAWAL_RULE_VERSION,
    WithdrawalContribution,
    build_animal_withdrawal_status,
    compute_withdrawal_ends,
)
from packages.shared_kernel import TypedId

T0 = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def _contribution(applied_at: datetime, days: int) -> WithdrawalContribution:
    return WithdrawalContribution.create(
        application_id=TypedId.new("treatment_application"),
        medication_batch_id=TypedId.new("medication_batch"),
        applied_at=applied_at,
        withdrawal_period_days=days,
    )


def test_compute_withdrawal_ends_adds_calendar_days() -> None:
    assert compute_withdrawal_ends(T0, 122) == T0 + timedelta(days=122)


def test_compute_withdrawal_ends_rejects_naive() -> None:
    with pytest.raises(ValueError, match="timezone"):
        compute_withdrawal_ends(datetime(2026, 7, 20, 12, 0), 30)  # noqa: DTZ001


def test_compute_withdrawal_ends_rejects_negative_days() -> None:
    with pytest.raises(ValueError, match="withdrawal_period_days"):
        compute_withdrawal_ends(T0, -1)


def test_zero_days_is_eligible_immediately_at_application() -> None:
    status = build_animal_withdrawal_status(TypedId.new("animal"), (_contribution(T0, 0),))
    assert status.eligible_from == T0
    assert status.is_eligible_at(T0) is True  # instante == eligible_from já é elegível


def test_animal_eligible_from_is_the_latest_end() -> None:
    """Carência do animal = maior prazo entre as aplicações."""
    curta = _contribution(T0, 30)
    longa = _contribution(T0, 122)
    status = build_animal_withdrawal_status(TypedId.new("animal"), (curta, longa))

    assert status.eligible_from == T0 + timedelta(days=122)
    assert status.rule_version == WITHDRAWAL_RULE_VERSION
    # Dentro da carência da mais longa, mesmo já fora da mais curta.
    assert status.is_in_withdrawal_at(T0 + timedelta(days=60)) is True
    # Depois de todas: elegível.
    assert status.is_eligible_at(T0 + timedelta(days=122)) is True


def test_no_treatment_means_always_eligible() -> None:
    status = build_animal_withdrawal_status(TypedId.new("animal"), ())
    assert status.eligible_from is None
    assert status.is_in_withdrawal_at(T0) is False
    assert status.is_eligible_at(T0) is True


def test_contribution_rejects_inconsistent_end() -> None:
    with pytest.raises(ValueError, match="não confere"):
        WithdrawalContribution(
            application_id=TypedId.new("treatment_application"),
            medication_batch_id=TypedId.new("medication_batch"),
            applied_at=T0,
            withdrawal_period_days=30,
            withdrawal_ends_at=T0 + timedelta(days=999),
        )
