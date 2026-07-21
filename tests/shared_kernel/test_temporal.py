from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from packages.shared_kernel import FixedClock, RecordTimestamps, SystemClock


def test_fixed_clock_freezes_recorded_time_and_preserves_fact_time() -> None:
    occurred_at = datetime(2026, 7, 20, 12, 30, tzinfo=UTC)
    recorded_at = datetime(2026, 7, 21, 9, 45, tzinfo=UTC)

    timestamps = RecordTimestamps.capture(
        occurred_at=occurred_at,
        clock=FixedClock(recorded_at),
    )

    assert timestamps.occurred_at == occurred_at
    assert timestamps.recorded_at == recorded_at
    assert timestamps.occurred_at != timestamps.recorded_at


def test_system_clock_returns_utc_aware_datetime() -> None:
    instant = SystemClock().now()

    assert instant.tzinfo is UTC
    assert instant.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "instant",
    [
        datetime(2026, 7, 21, 9, 45),
        datetime(2026, 7, 21, 9, 45, tzinfo=timezone(timedelta(hours=-4))),
    ],
)
def test_rejects_naive_or_non_utc_fixed_clock(instant: datetime) -> None:
    with pytest.raises(ValueError):
        FixedClock(instant)


@pytest.mark.parametrize("field", ["occurred_at", "recorded_at"])
def test_rejects_naive_record_timestamp(field: str) -> None:
    valid = datetime(2026, 7, 21, 9, 45, tzinfo=UTC)
    values = {"occurred_at": valid, "recorded_at": valid}
    values[field] = datetime(2026, 7, 21, 9, 45)

    with pytest.raises(ValueError, match="timezone explícito"):
        RecordTimestamps(**values)


def test_record_timestamps_are_immutable() -> None:
    instant = datetime(2026, 7, 21, 9, 45, tzinfo=UTC)
    timestamps = RecordTimestamps(occurred_at=instant, recorded_at=instant)

    with pytest.raises(FrozenInstanceError):
        timestamps.recorded_at = instant + timedelta(seconds=1)  # type: ignore[misc]
