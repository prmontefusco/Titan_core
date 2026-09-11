"""Testes unitários de domínio para `SLIContract` (A2, módulo `sustainment`).

Cobre I‑SLI‑1/2 (seleção temporal de versão, isolada de regra de cobertura),
I‑SLI‑3 (versão imutável, sequência sem lacuna) e I‑SLI‑6 (cobertura de
contratos concorrentes não ambígua). `docs/asset/07_INVARIANTS.md`.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.asset_domain.sustainment_contract import (
    CoberturaAmbigua,
    ContractScope,
    ContractVersion,
    CoverageLine,
    KnownValidInterval,
    ResolvedCoverage,
    SLIContract,
    VersaoDeContratoInvalida,
    require_unambiguous_coverage,
)
from packages.shared_kernel import OrganizationId, TypedId

MOMENTO = datetime(2026, 9, 11, tzinfo=UTC)
DEPOIS = datetime(2026, 12, 1, tzinfo=UTC)


def _interval(valid_from: datetime = MOMENTO, known_at: datetime = MOMENTO) -> KnownValidInterval:
    return KnownValidInterval(valid_from=valid_from, known_at=known_at)


def _version(no: int = 1, *, valid_from: datetime = MOMENTO) -> ContractVersion:
    return ContractVersion(version_no=no, effective=_interval(valid_from=valid_from))


def _contract(**overrides: object) -> SLIContract:
    defaults: dict[str, object] = dict(
        contract_id=TypedId.new("sli_contract"),
        organization_id=OrganizationId(uuid4()),
        customer_ref=TypedId.new("customer"),
    )
    defaults.update(overrides)
    return SLIContract(**defaults)  # type: ignore[arg-type]


def test_contract_creation_without_versions() -> None:
    contract = _contract()
    assert contract.current_version_no is None
    assert contract.resolve_version_at(MOMENTO) is None


# --- I-SLI-3 ------------------------------------------------------------------------


def test_issue_version_appends_sequentially() -> None:
    contract = _contract().issue_version(_version(1))
    assert contract.current_version_no == 1
    contract = contract.issue_version(_version(2, valid_from=DEPOIS))
    assert contract.current_version_no == 2


def test_issue_version_rejects_out_of_sequence() -> None:
    contract = _contract().issue_version(_version(1))
    with pytest.raises(VersaoDeContratoInvalida):
        contract.issue_version(_version(3))


def test_construction_rejects_gap_in_version_numbers() -> None:
    with pytest.raises(VersaoDeContratoInvalida):
        _contract(versions=(_version(1), _version(3, valid_from=DEPOIS)))


def test_issue_version_rejects_retroactive_valid_from() -> None:
    contract = _contract().issue_version(_version(1, valid_from=DEPOIS))
    with pytest.raises(ValueError, match="não pode retroceder"):
        contract.issue_version(_version(2, valid_from=MOMENTO))


def test_previous_version_is_untouched_by_issuing_a_new_one() -> None:
    """I-SLI-3: emitir uma nova versão não edita a anterior."""
    v1 = _version(1)
    contract = _contract().issue_version(v1)
    contract2 = contract.issue_version(_version(2, valid_from=DEPOIS))
    assert contract2.versions[0] is v1
    assert contract2.versions[0].version_no == 1


# --- I-SLI-1 / I-SLI-2 ---------------------------------------------------------------


def test_resolve_version_at_picks_the_latest_version_already_valid() -> None:
    contract = (
        _contract()
        .issue_version(_version(1, valid_from=MOMENTO))
        .issue_version(_version(2, valid_from=DEPOIS))
    )
    meio = datetime(2026, 10, 1, tzinfo=UTC)
    resolved_meio = contract.resolve_version_at(meio)
    resolved_depois = contract.resolve_version_at(DEPOIS)
    assert resolved_meio is not None
    assert resolved_depois is not None
    assert resolved_meio.version_no == 1
    assert resolved_depois.version_no == 2


def test_resolve_version_at_returns_none_before_first_version() -> None:
    contract = _contract().issue_version(_version(1, valid_from=DEPOIS))
    assert contract.resolve_version_at(MOMENTO) is None


def test_scenario_e_contract_amended_after_work_order_opened() -> None:
    """Cenário E da constituição §41: a WO usa a versão vigente NO INSTANTE em
    que abriu, mesmo depois de o contrato ser emendado."""
    contract = _contract().issue_version(_version(1, valid_from=MOMENTO))
    work_order_opened_at = datetime(2026, 10, 1, tzinfo=UTC)
    resolved_at_opening = contract.resolve_version_at(work_order_opened_at)

    # Contrato é emendado DEPOIS que a WO abriu.
    amended = contract.issue_version(_version(2, valid_from=DEPOIS))

    # A resolução histórica não muda: consultar o mesmo instante de abertura
    # continua devolvendo a versão 1, mesmo no contrato já emendado.
    resolved_after_amendment = amended.resolve_version_at(work_order_opened_at)
    assert resolved_after_amendment is not None
    assert resolved_at_opening is not None
    assert resolved_after_amendment.version_no == 1
    assert resolved_at_opening.version_no == 1


def test_resolve_version_at_respects_known_at() -> None:
    """I-SLI-2: seleção também pode considerar o tempo de conhecimento."""
    late_knowledge = datetime(2026, 9, 20, tzinfo=UTC)
    version = ContractVersion(
        version_no=1, effective=KnownValidInterval(valid_from=MOMENTO, known_at=late_knowledge)
    )
    contract = _contract().issue_version(version)
    # Em MOMENTO, a versão já era válida (valid_from) mas ainda não era CONHECIDA.
    assert contract.resolve_version_at(MOMENTO, known_at=MOMENTO) is None
    assert contract.resolve_version_at(MOMENTO, known_at=late_knowledge) is not None


# --- CoverageLine --------------------------------------------------------------------


def test_coverage_line_rejects_part_in_both_covered_and_excluded() -> None:
    part_ref = TypedId.new("part")
    with pytest.raises(ValueError, match="covered_parts e excluded_parts"):
        CoverageLine(
            scope=ContractScope.VEHICLE,
            scope_value="veh-1",
            covered_parts=(part_ref,),
            excluded_parts=(part_ref,),
        )


def test_coverage_line_covers_part_when_no_allowlist_and_not_excluded() -> None:
    line = CoverageLine(scope=ContractScope.MODEL, scope_value="M1")
    assert line.covers_part(TypedId.new("part")) is True


def test_coverage_line_excluded_part_is_never_covered() -> None:
    excluded = TypedId.new("part")
    line = CoverageLine(scope=ContractScope.MODEL, scope_value="M1", excluded_parts=(excluded,))
    assert line.covers_part(excluded) is False


# --- I-SLI-6 ---------------------------------------------------------------------------


def test_require_unambiguous_coverage_accepts_disjoint_scopes() -> None:
    contract_a = _contract().issue_version(
        ContractVersion(
            version_no=1,
            effective=_interval(),
            coverage_lines=(CoverageLine(scope=ContractScope.VEHICLE, scope_value="veh-1"),),
        )
    )
    contract_b = _contract().issue_version(
        ContractVersion(
            version_no=1,
            effective=_interval(),
            coverage_lines=(CoverageLine(scope=ContractScope.VEHICLE, scope_value="veh-2"),),
        )
    )
    require_unambiguous_coverage(
        ResolvedCoverage(contract_a, contract_a.versions[0]),
        others=[ResolvedCoverage(contract_b, contract_b.versions[0])],
        at=MOMENTO,
    )


def test_require_unambiguous_coverage_rejects_same_scope_in_different_contracts() -> None:
    line = CoverageLine(scope=ContractScope.VEHICLE, scope_value="veh-1")
    contract_a = _contract().issue_version(
        ContractVersion(version_no=1, effective=_interval(), coverage_lines=(line,))
    )
    contract_b = _contract().issue_version(
        ContractVersion(version_no=1, effective=_interval(), coverage_lines=(line,))
    )
    with pytest.raises(CoberturaAmbigua):
        require_unambiguous_coverage(
            ResolvedCoverage(contract_a, contract_a.versions[0]),
            others=[ResolvedCoverage(contract_b, contract_b.versions[0])],
            at=MOMENTO,
        )


def test_require_unambiguous_coverage_ignores_same_contract() -> None:
    line = CoverageLine(scope=ContractScope.VEHICLE, scope_value="veh-1")
    contract = _contract().issue_version(
        ContractVersion(version_no=1, effective=_interval(), coverage_lines=(line,))
    )
    require_unambiguous_coverage(
        ResolvedCoverage(contract, contract.versions[0]),
        others=[ResolvedCoverage(contract, contract.versions[0])],
        at=MOMENTO,
    )
