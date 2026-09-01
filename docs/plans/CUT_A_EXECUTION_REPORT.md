# CUT A Execution Report - Lifetime Coverage Completion

Date: 2026-08-28

Status: IMPLEMENTED WITHIN APPROVED LIMITS

## Scope

CUT A was limited to already approved NEXT-01/LIV-C02 semantics for explicit dimensional coverage, historical temporal boundaries, and the fictitious `SANITARY_TEST_A_v1` Policy. No commercial concept, migration, API, cross-tenant access, official source integration, Dossier change, or new aggregate was introduced.

## Gaps Identified

The real code already had `DimensionalCoverageService` using half-open intervals and rejecting empty intervals. The `SANITARY_TEST_A_v1` material selection still included treatments at exactly `reference_time` with `<= reference_time`, while the coverage interval is represented as `[required_from, required_until)`.

## Owners

- Semantic owner: Livestock application.
- Persistence owner: none changed.
- API owner: none changed.
- Tenant boundary: unchanged; all affected behavior runs inside one Organization context.

## ADRs and Invariants

- ADR-0052: temporal selection distinguishes valid time and knowledge time.
- NEXT-01: dimensional coverage uses explicit intervals and must not infer absence without coverage.
- DOMAIN.md P-072, P-112, P-138 and P-207 remain preserved.

## Implementation

Changed `packages/livestock_application/sanitary_test_coverage.py` so all `SANITARY_TEST_A_v1` paths use `required_from <= occurred_at < reference_time`:

- direct `TreatmentCoverageDeclaration`;
- composed `CoverageContribution`;
- classified medication material.

## Tests Added

- `test_treatment_at_required_until_stays_outside_half_open_coverage_window`
- `test_classified_treatment_at_required_until_is_not_selected`
- `test_composed_coverage_uses_required_until_as_exclusive_boundary`

## Verification

Focused verification passed:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
```

Result: 31 passed.

Full pytest passed:

```text
python -m uv run --locked python -m pytest
```

Result: 1177 passed, 284 skipped.

## Migrations

None.

## Security and Tenant Isolation

No data sharing, permissions, grants, RLS policy, API or persistence changed.

## Temporal Impact

Positive: upper-boundary selection now matches the semi-open interval contract. No `known_at`, `reference_time`, `knowledge_cutoff`, Evaluation, Decision or Dossier history is rewritten.

## Residual Gaps

Remaining source-specific historical readers from ADR-0062/NEXT-01 require separate approved cuts if a concrete gap is selected.
