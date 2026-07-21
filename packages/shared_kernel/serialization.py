"""Serialização canônica, determinística e versionada do Titan."""

import json
import math
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal

from packages.shared_kernel.temporal import require_utc

type CanonicalScalar = None | bool | int | str | Decimal | datetime
type CanonicalValue = CanonicalScalar | Sequence[CanonicalValue] | Mapping[str, CanonicalValue]
type NormalizedValue = list[object] | str


class CanonicalSerializer:
    """Produz bytes JSON inequívocos segundo o contrato ``titan-json-v1``."""

    version = "titan-json-v1"

    def serialize(self, value: CanonicalValue) -> bytes:
        normalized = self._normalize(value, ancestors=set())
        envelope = [self.version, normalized]
        text = json.dumps(
            envelope,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        return text.encode("utf-8")

    def _normalize(self, value: CanonicalValue, *, ancestors: set[int]) -> NormalizedValue:
        if value is None:
            return ["null"]
        if isinstance(value, bool):
            return ["boolean", "true" if value else "false"]
        if isinstance(value, int):
            return ["integer", str(value)]
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("Valores float não finitos não são suportados.")
            raise TypeError("Valores float não são suportados; utilize Decimal.")
        if isinstance(value, Decimal):
            return ["decimal", self._canonical_decimal(value)]
        if isinstance(value, datetime):
            return ["datetime", self._canonical_datetime(value)]
        if isinstance(value, str):
            return ["string", unicodedata.normalize("NFC", value)]
        if isinstance(value, Mapping):
            return self._normalize_mapping(value, ancestors=ancestors)
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, memoryview)):
            return self._normalize_sequence(value, ancestors=ancestors)
        raise TypeError(f"Tipo não suportado pela serialização canônica: {type(value).__name__}.")

    def _normalize_mapping(
        self,
        value: Mapping[str, CanonicalValue],
        *,
        ancestors: set[int],
    ) -> NormalizedValue:
        identity = id(value)
        self._enter_container(identity, ancestors)
        try:
            normalized_items: list[tuple[str, NormalizedValue]] = []
            normalized_keys: set[str] = set()
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError("Mapas canônicos aceitam somente chaves textuais.")
                normalized_key = unicodedata.normalize("NFC", key)
                if normalized_key in normalized_keys:
                    raise ValueError("Chaves distintas colidem após normalização Unicode NFC.")
                normalized_keys.add(normalized_key)
                normalized_items.append(
                    (normalized_key, self._normalize(item, ancestors=ancestors))
                )
            normalized_items.sort(key=lambda item: item[0].encode("utf-8"))
            return ["map", [[key, item] for key, item in normalized_items]]
        finally:
            ancestors.remove(identity)

    def _normalize_sequence(
        self,
        value: Sequence[CanonicalValue],
        *,
        ancestors: set[int],
    ) -> NormalizedValue:
        identity = id(value)
        self._enter_container(identity, ancestors)
        try:
            return ["list", [self._normalize(item, ancestors=ancestors) for item in value]]
        finally:
            ancestors.remove(identity)

    @staticmethod
    def _enter_container(identity: int, ancestors: set[int]) -> None:
        if identity in ancestors:
            raise ValueError("Estruturas cíclicas não podem ser serializadas.")
        ancestors.add(identity)

    @staticmethod
    def _canonical_decimal(value: Decimal) -> str:
        if not value.is_finite():
            raise ValueError("Decimal não finito não é suportado.")
        if value.is_zero():
            return "0"
        normalized = value.normalize()
        rendered = format(normalized, "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        return rendered

    @staticmethod
    def _canonical_datetime(value: datetime) -> str:
        require_utc(value, field_name="datetime")
        rendered = value.astimezone(UTC).isoformat(timespec="microseconds")
        return rendered.replace("+00:00", "Z")
