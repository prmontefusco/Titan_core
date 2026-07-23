"""Módulo de limitação de taxa (Rate Limiting 429) para resiliência na borda (ADR-0039)."""

import time
from dataclasses import dataclass, field
from typing import NamedTuple


class RateLimitStatus(NamedTuple):
    is_allowed: bool
    limit: int
    remaining: int
    reset_after_seconds: int


@dataclass(slots=True)
class InMemoryRateLimiter:
    """Implementação sliding-window / token-bucket para rate limiting por chave (IP ou OrgId)."""

    requests_per_minute: int = 60
    _buckets: dict[str, list[float]] = field(default_factory=dict)

    def check_rate_limit(self, key: str, current_time: float | None = None) -> RateLimitStatus:
        now = current_time if current_time is not None else time.time()
        window_start = now - 60.0

        timestamps = self._buckets.get(key, [])
        # Filtra timestamps dentro da janela móvel de 60s
        valid_timestamps = [t for t in timestamps if t > window_start]

        if len(valid_timestamps) >= self.requests_per_minute:
            oldest = valid_timestamps[0]
            reset_after = max(1, int(oldest + 60.0 - now))
            self._buckets[key] = valid_timestamps
            return RateLimitStatus(
                is_allowed=False,
                limit=self.requests_per_minute,
                remaining=0,
                reset_after_seconds=reset_after,
            )

        valid_timestamps.append(now)
        self._buckets[key] = valid_timestamps
        remaining = self.requests_per_minute - len(valid_timestamps)

        return RateLimitStatus(
            is_allowed=True,
            limit=self.requests_per_minute,
            remaining=remaining,
            reset_after_seconds=60,
        )
