"""Testes unitários de domínio para `ConfigurationBaseline` (A2).

Cobre I‑CFG‑1 (cadeia de revisão acíclica) e I‑CFG‑2 (efetividade não
sobrepõe para a mesma posição). `docs/asset/07_INVARIANTS.md`.
"""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.asset_domain.configuration import (
    BaselinePosition,
    CadeiaDeRevisaoCiclica,
    ConfigurationBaseline,
    ConfigurationRevision,
    EfetividadeSobreposta,
    Effectivity,
    require_acyclic_revision_chain,
    require_no_overlapping_effectivity,
)
from packages.shared_kernel import OrganizationId, TypedId

MOMENTO = datetime(2026, 9, 11, tzinfo=UTC)
DEPOIS = datetime(2026, 12, 1, tzinfo=UTC)


def _position(code: str = "ENGINE") -> BaselinePosition:
    return BaselinePosition(
        position_code=code,
        part_ref=TypedId.new("part"),
        part_revision_ref=TypedId.new("part_revision"),
    )


def _baseline(**overrides: object) -> ConfigurationBaseline:
    defaults: dict[str, object] = dict(
        baseline_id=TypedId.new("configuration_baseline"),
        organization_id=OrganizationId(uuid4()),
        model_ref=TypedId.new("vehicle_model"),
        revision=ConfigurationRevision(number=1),
        effectivity=Effectivity(valid_from=MOMENTO),
        positions=(_position(),),
    )
    defaults.update(overrides)
    return ConfigurationBaseline(**defaults)  # type: ignore[arg-type]


def test_baseline_creation() -> None:
    baseline = _baseline()
    assert baseline.revision.number == 1
    assert baseline.revision.supersedes_ref is None


def test_position_codes_must_be_unique_within_baseline() -> None:
    with pytest.raises(ValueError, match="duplicado"):
        _baseline(positions=(_position("ENGINE"), _position("ENGINE")))


def test_baseline_cannot_supersede_itself() -> None:
    baseline_id = TypedId.new("configuration_baseline")
    with pytest.raises(CadeiaDeRevisaoCiclica):
        ConfigurationBaseline(
            baseline_id=baseline_id,
            organization_id=OrganizationId(uuid4()),
            model_ref=TypedId.new("vehicle_model"),
            revision=ConfigurationRevision(number=2, supersedes_ref=baseline_id),
            effectivity=Effectivity(valid_from=MOMENTO),
        )


# --- I-CFG-1 (cadeia acíclica, cross-agregado) -----------------------------------


def test_require_acyclic_revision_chain_accepts_linear_history() -> None:
    b1 = _baseline(revision=ConfigurationRevision(number=1))
    b2 = _baseline(revision=ConfigurationRevision(number=2, supersedes_ref=b1.baseline_id))
    # Não levanta.
    require_acyclic_revision_chain(b2, history=[b1])


def test_require_acyclic_revision_chain_rejects_direct_cycle() -> None:
    b1 = _baseline(revision=ConfigurationRevision(number=1))
    b2 = _baseline(revision=ConfigurationRevision(number=2, supersedes_ref=b1.baseline_id))
    # Reescrever b1 para apontar de volta para b2 fecharia o ciclo.
    b1_cyclic = replace(b1, revision=ConfigurationRevision(number=1, supersedes_ref=b2.baseline_id))
    with pytest.raises(CadeiaDeRevisaoCiclica):
        require_acyclic_revision_chain(b1_cyclic, history=[b2])


def test_require_acyclic_revision_chain_rejects_transitive_cycle() -> None:
    b1 = _baseline(revision=ConfigurationRevision(number=1))
    b2 = _baseline(revision=ConfigurationRevision(number=2, supersedes_ref=b1.baseline_id))
    b3 = _baseline(revision=ConfigurationRevision(number=3, supersedes_ref=b2.baseline_id))
    b1_cyclic = replace(b1, revision=ConfigurationRevision(number=1, supersedes_ref=b3.baseline_id))
    with pytest.raises(CadeiaDeRevisaoCiclica):
        require_acyclic_revision_chain(b1_cyclic, history=[b2, b3])


# --- I-CFG-2 (efetividade não sobrepõe) -------------------------------------------


def test_require_no_overlapping_effectivity_accepts_disjoint_time_ranges() -> None:
    model_ref = TypedId.new("vehicle_model")
    b1 = _baseline(
        model_ref=model_ref,
        effectivity=Effectivity(valid_from=MOMENTO, valid_to=DEPOIS),
        positions=(_position("ENGINE"),),
    )
    b2 = _baseline(
        model_ref=model_ref,
        effectivity=Effectivity(valid_from=DEPOIS),
        positions=(_position("ENGINE"),),
    )
    require_no_overlapping_effectivity(b2, others=[b1])


def test_require_no_overlapping_effectivity_rejects_same_position_overlapping_time() -> None:
    model_ref = TypedId.new("vehicle_model")
    b1 = _baseline(
        model_ref=model_ref,
        effectivity=Effectivity(valid_from=MOMENTO),
        positions=(_position("ENGINE"),),
    )
    b2 = _baseline(
        model_ref=model_ref,
        effectivity=Effectivity(valid_from=MOMENTO),
        positions=(_position("ENGINE"),),
    )
    with pytest.raises(EfetividadeSobreposta):
        require_no_overlapping_effectivity(b2, others=[b1])


def test_require_no_overlapping_effectivity_allows_different_positions() -> None:
    """Mesmo período, mas posições diferentes — sem conflito."""
    model_ref = TypedId.new("vehicle_model")
    b1 = _baseline(
        model_ref=model_ref,
        effectivity=Effectivity(valid_from=MOMENTO),
        positions=(_position("ENGINE"),),
    )
    b2 = _baseline(
        model_ref=model_ref,
        effectivity=Effectivity(valid_from=MOMENTO),
        positions=(_position("TRANSMISSION"),),
    )
    require_no_overlapping_effectivity(b2, others=[b1])


def test_require_no_overlapping_effectivity_ignores_different_models() -> None:
    b1 = _baseline(
        model_ref=TypedId.new("vehicle_model"),
        effectivity=Effectivity(valid_from=MOMENTO),
        positions=(_position("ENGINE"),),
    )
    b2 = _baseline(
        model_ref=TypedId.new("vehicle_model"),
        effectivity=Effectivity(valid_from=MOMENTO),
        positions=(_position("ENGINE"),),
    )
    require_no_overlapping_effectivity(b2, others=[b1])


def test_effectivity_serial_range_can_overlap_independently_of_time() -> None:
    """Faixa de série sobreposta MAS tempo disjunto -> sem conflito (as duas
    dimensões precisam sobrepor simultaneamente)."""
    a = Effectivity(valid_from=MOMENTO, valid_to=DEPOIS, serial_from="0001", serial_to="0100")
    b = Effectivity(valid_from=DEPOIS, serial_from="0050", serial_to="0150")
    assert a.conflicts_with(b) is False


def test_effectivity_rejects_valid_to_before_valid_from() -> None:
    with pytest.raises(ValueError, match="valid_to deve ser posterior"):
        Effectivity(valid_from=DEPOIS, valid_to=MOMENTO)
