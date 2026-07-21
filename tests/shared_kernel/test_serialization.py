import hashlib
import unicodedata
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from packages.shared_kernel import CanonicalSerializer


def test_mapping_order_produces_identical_bytes_and_hash() -> None:
    serializer = CanonicalSerializer()
    first: dict[str, str | Decimal | datetime] = {
        "subject": "abc",
        "amount": Decimal("10.500"),
        "recorded_at": datetime(2026, 7, 21, 10, 30, tzinfo=UTC),
    }
    second: dict[str, str | Decimal | datetime] = {
        "recorded_at": datetime(2026, 7, 21, 10, 30, tzinfo=UTC),
        "amount": Decimal("10.5"),
        "subject": "abc",
    }

    first_bytes = serializer.serialize(first)
    second_bytes = serializer.serialize(second)

    assert first_bytes == second_bytes
    assert hashlib.sha256(first_bytes).digest() == hashlib.sha256(second_bytes).digest()
    assert first_bytes.startswith(b'["titan-json-v1",')


def test_unicode_equivalents_produce_identical_bytes() -> None:
    serializer = CanonicalSerializer()
    composed = "informação"
    decomposed = unicodedata.normalize("NFD", composed)

    assert serializer.serialize({composed: composed}) == serializer.serialize(
        {decomposed: decomposed}
    )


def test_list_order_is_semantically_significant() -> None:
    serializer = CanonicalSerializer()

    assert serializer.serialize(["a", "b"]) != serializer.serialize(["b", "a"])


@pytest.mark.parametrize("value", [1.5, float("nan"), float("inf")])
def test_rejects_float_values(value: float) -> None:
    with pytest.raises((TypeError, ValueError)):
        CanonicalSerializer().serialize(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity")])
def test_rejects_nonfinite_decimal(value: Decimal) -> None:
    with pytest.raises(ValueError, match="não finito"):
        CanonicalSerializer().serialize(value)


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 7, 21, 10, 30),
        datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=-4))),
    ],
)
def test_rejects_naive_or_non_utc_datetime(value: datetime) -> None:
    with pytest.raises(ValueError):
        CanonicalSerializer().serialize(value)


def test_rejects_nontextual_mapping_key() -> None:
    with pytest.raises(TypeError, match="chaves textuais"):
        CanonicalSerializer().serialize({1: "value"})  # type: ignore[dict-item]


def test_rejects_keys_that_collide_after_unicode_normalization() -> None:
    composed = "informação"
    decomposed = unicodedata.normalize("NFD", composed)

    with pytest.raises(ValueError, match="colidem"):
        CanonicalSerializer().serialize({composed: 1, decomposed: 2})


def test_rejects_cyclic_structure() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)

    with pytest.raises(ValueError, match="cíclicas"):
        CanonicalSerializer().serialize(cyclic)  # type: ignore[arg-type]


def test_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Tipo não suportado"):
        CanonicalSerializer().serialize({"value": object()})  # type: ignore[dict-item]
