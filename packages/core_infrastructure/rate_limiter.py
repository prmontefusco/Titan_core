"""Módulo de limitação de taxa (Rate Limiting 429) para resiliência na borda (ADR-0039)."""

import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Final, NamedTuple
from uuid import UUID


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


# BuyerPolicy Fase 3, ADR-0066 D3: o limite da autoavaliacao compartilhada e por
# grant, e nao por IP ou por Organization. E o grant que delimita finalidade,
# validade e contraparte -- dois contratos distintos com a mesma fornecedora nao
# devem competir pela mesma cota, e um contrato premium pode receber cota maior
# sem mexer nos demais.
SHARED_POLICY_EVALUATIONS_PER_MINUTE: Final = 10


def shared_policy_evaluation_key(grant_id: UUID) -> str:
    """Chave do balde de um grant. O prefixo evita colisao com outros usos."""
    return f"shared-policy-evaluate:{grant_id}"


@lru_cache(maxsize=1)
def shared_policy_evaluation_rate_limiter() -> InMemoryRateLimiter:
    """Uma instancia por processo.

    **Limitacao aceita no MVP:** a contagem vive na memoria do processo, entao N
    workers toleram ate N vezes o limite, e cada grant ja avaliado mantem um
    balde de no maximo dez instantes ate o processo reiniciar. Trocar por um
    contador compartilhado (Redis ou tabela) exige decisao propria -- o
    compartilhamento bilateral hoje roda em processo unico, e introduzir
    dependencia externa aqui custaria mais do que o risco residual que ela
    removeria.
    """
    return InMemoryRateLimiter(requests_per_minute=SHARED_POLICY_EVALUATIONS_PER_MINUTE)
