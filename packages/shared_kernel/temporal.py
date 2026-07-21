"""Primitivas temporais universais e independentes de infraestrutura."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


def require_utc(instant: datetime, *, field_name: str) -> datetime:
    """Valida uma representação temporal inequívoca em UTC."""
    if not isinstance(instant, datetime):
        raise TypeError(f"{field_name} deve ser datetime.")
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError(f"{field_name} deve possuir timezone explícito.")
    if instant.utcoffset() != UTC.utcoffset(instant):
        raise ValueError(f"{field_name} deve estar representado em UTC.")
    return instant


@runtime_checkable
class Clock(Protocol):
    """Porta mínima para obter o instante observado pelo Titan."""

    def now(self) -> datetime:
        """Retorna o instante atual representado em UTC."""
        ...


@dataclass(frozen=True, slots=True)
class SystemClock:
    """Relógio baseado no sistema operacional."""

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class FixedClock:
    """Relógio determinístico para testes e reproduções controladas."""

    instant: datetime

    def __post_init__(self) -> None:
        require_utc(self.instant, field_name="instant")

    def now(self) -> datetime:
        return self.instant


@dataclass(frozen=True, slots=True)
class RecordTimestamps:
    """Distingue quando o fato teria ocorrido de quando o Titan o registrou."""

    occurred_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        require_utc(self.occurred_at, field_name="occurred_at")
        require_utc(self.recorded_at, field_name="recorded_at")

    @classmethod
    def capture(cls, *, occurred_at: datetime, clock: Clock) -> "RecordTimestamps":
        if not isinstance(clock, Clock):
            raise TypeError("clock deve implementar o contrato Clock.")
        recorded_at = require_utc(clock.now(), field_name="clock.now()")
        return cls(occurred_at=occurred_at, recorded_at=recorded_at)
