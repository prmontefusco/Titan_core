"""Uniform public response mapping for future Market Supply aggregate access.

The mapper intentionally has no HTTP dependency. It encodes the application
semantics that denied and privacy-suppressed aggregate queries must look the
same to the requester.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from packages.core_domain import CanonicalPayload
from packages.livestock_application.market_supply_audit import (
    MarketSupplyAggregateQueryAuditEnvelope,
    MarketSupplyAuditExternalDisposition,
)

MARKET_SUPPLY_PUBLIC_AGGREGATE_RESPONSE_SCHEMA = "market_supply.public_aggregate_response"
MARKET_SUPPLY_PUBLIC_AGGREGATE_RESPONSE_VERSION = 1
MARKET_SUPPLY_PUBLIC_AGGREGATE_PAYLOAD_SCHEMA = "market_supply.public_aggregate_payload"
MARKET_SUPPLY_PUBLIC_AGGREGATE_PAYLOAD_VERSION = 1
MARKET_SUPPLY_NO_STORE_HEADERS = MappingProxyType(
    {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
    },
)

_ALLOWED_TOP_LEVEL_KEYS = frozenset(
    {
        "population_count",
        "readiness_counts",
        "ready_now",
        "conditioned",
        "indeterminate",
        "not_ready",
        "not_evaluated",
        "reassessment_required",
        "current_capacity",
        "requested_quantity",
        "estimated_shortage_now",
        "gap_summary",
        "limitations",
    },
)
_ALLOWED_READINESS_KEYS = frozenset(
    {
        "READY",
        "CONDITIONED",
        "INDETERMINATE",
        "NOT_READY",
        "NOT_EVALUATED",
        "REASSESSMENT_REQUIRED",
    },
)
_ALLOWED_GAP_KEYS = frozenset({"code", "count"})
_BLOCKED_KEY_FRAGMENTS = ("id", "identifier", "producer", "property", "animal")


class MarketSupplyPublicResponseStatus(StrEnum):
    RELEASED = "RELEASED"
    NOT_RELEASED = "NOT_RELEASED"


@dataclass(frozen=True, slots=True)
class MarketSupplyPublicAggregatePayload:
    """Allow-listed aggregate payload safe for the public Market Supply shape."""

    value: Mapping[str, Any]

    def __post_init__(self) -> None:
        sanitized = _sanitize_public_aggregate_payload(self.value)
        object.__setattr__(self, "value", MappingProxyType(sanitized))


@dataclass(frozen=True, slots=True)
class MarketSupplyPublicAggregateResponse:
    status: MarketSupplyPublicResponseStatus
    aggregate: Mapping[str, Any] | None

    @property
    def released(self) -> bool:
        return self.status is MarketSupplyPublicResponseStatus.RELEASED

    def to_canonical_payload(self) -> CanonicalPayload:
        value: dict[str, Any] = {"status": self.status.value}
        if self.aggregate is not None:
            value["aggregate"] = dict(self.aggregate)
        return CanonicalPayload.from_mapping(
            schema=MARKET_SUPPLY_PUBLIC_AGGREGATE_RESPONSE_SCHEMA,
            version=MARKET_SUPPLY_PUBLIC_AGGREGATE_RESPONSE_VERSION,
            value=value,
        )


class MarketSupplyPublicResponseMapper:
    """Maps internal audit dispositions into a stable public aggregate shape."""

    def validate_aggregate_payload(
        self,
        aggregate_payload: Mapping[str, Any] | None,
    ) -> Mapping[str, Any]:
        if aggregate_payload is None:
            raise ValueError("aggregate_payload e obrigatorio quando release e permitido.")
        return MarketSupplyPublicAggregatePayload(aggregate_payload).value

    def map_aggregate(
        self,
        *,
        envelope: MarketSupplyAggregateQueryAuditEnvelope,
        aggregate_payload: Mapping[str, Any] | None,
    ) -> MarketSupplyPublicAggregateResponse:
        if (
            envelope.external_disposition
            is not MarketSupplyAuditExternalDisposition.RELEASE_AGGREGATE
        ):
            return MarketSupplyPublicAggregateResponse(
                status=MarketSupplyPublicResponseStatus.NOT_RELEASED,
                aggregate=None,
            )
        public_payload = self.validate_aggregate_payload(aggregate_payload)
        return MarketSupplyPublicAggregateResponse(
            status=MarketSupplyPublicResponseStatus.RELEASED,
            aggregate=public_payload,
        )

    def sensitive_response_headers(self) -> Mapping[str, str]:
        """Headers required for every future buyer-facing Market Supply response."""
        return MARKET_SUPPLY_NO_STORE_HEADERS


def _sanitize_public_aggregate_payload(
    aggregate_payload: Mapping[str, Any],
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in aggregate_payload.items():
        _validate_public_key(key, allowed_keys=_ALLOWED_TOP_LEVEL_KEYS, path=key)
        sanitized[key] = _sanitize_public_value(key=key, value=value, path=key)
    return sanitized


def _validate_public_key(
    key: str,
    *,
    allowed_keys: frozenset[str],
    path: str,
) -> None:
    if not isinstance(key, str) or not key.strip():
        raise ValueError(f"{path} deve usar chave textual nao vazia.")
    normalized = key.casefold()
    if any(fragment in normalized for fragment in _BLOCKED_KEY_FRAGMENTS):
        raise ValueError(f"{path} nao pode expor identificadores ou membership protegido.")
    if key not in allowed_keys:
        raise ValueError(f"{path} nao pertence ao schema publico de aggregate_payload.")


def _sanitize_public_value(*, key: str, value: Any, path: str) -> Any:
    if key == "readiness_counts":
        if not isinstance(value, Mapping):
            raise ValueError("readiness_counts deve ser objeto agregado.")
        return _sanitize_readiness_counts(value)
    if key == "gap_summary":
        if not isinstance(value, tuple | list):
            raise ValueError("gap_summary deve ser lista agregada.")
        return tuple(_sanitize_gap(item, index=index) for index, item in enumerate(value))
    if key == "limitations":
        if not isinstance(value, tuple | list):
            raise ValueError("limitations deve ser lista de textos.")
        return tuple(
            _sanitize_public_text(item, path=f"{path}[{index}]") for index, item in enumerate(value)
        )
    if key in {
        "population_count",
        "ready_now",
        "conditioned",
        "indeterminate",
        "not_ready",
        "not_evaluated",
        "reassessment_required",
        "current_capacity",
    }:
        return _sanitize_non_negative_int(value, path=path)
    if key in {"requested_quantity", "estimated_shortage_now"}:
        if value is None:
            return None
        return _sanitize_non_negative_int(value, path=path)
    raise ValueError(f"{path} nao pertence ao schema publico de aggregate_payload.")


def _sanitize_readiness_counts(value: Mapping[str, Any]) -> Mapping[str, int]:
    sanitized: dict[str, int] = {}
    for key, count in value.items():
        _validate_public_key(
            key,
            allowed_keys=_ALLOWED_READINESS_KEYS,
            path=f"readiness_counts.{key}",
        )
        sanitized[key] = _sanitize_non_negative_int(count, path=f"readiness_counts.{key}")
    return MappingProxyType(sanitized)


def _sanitize_gap(value: Any, *, index: int) -> Mapping[str, Any]:
    path = f"gap_summary[{index}]"
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} deve ser objeto agregado.")
    if set(value) != _ALLOWED_GAP_KEYS:
        raise ValueError(f"{path} deve conter somente code e count.")
    return MappingProxyType(
        {
            "code": _sanitize_public_text(value["code"], path=f"{path}.code"),
            "count": _sanitize_non_negative_int(value["count"], path=f"{path}.count"),
        },
    )


def _sanitize_non_negative_int(value: Any, *, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path} deve ser inteiro agregado.")
    if value < 0:
        raise ValueError(f"{path} nao pode ser negativo.")
    return value


def _sanitize_public_text(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} deve ser texto nao vazio.")
    normalized = value.casefold()
    if any(fragment in normalized for fragment in _BLOCKED_KEY_FRAGMENTS):
        raise ValueError(f"{path} nao pode expor identificadores ou membership protegido.")
    return value
