# Market Optionality F5 Execution Report

**Status:** COMPLETED  
**Date:** 2026-09-03  
**Scope:** internal aggregation of optionality/readiness over authorized Candidate Population snapshots.

## Summary

F5 adds an internal Market Supply aggregation that composes authorized `CandidatePopulationSnapshot` material, canonical `MarketReadinessReport` values and supplied `MarketOptionAssessment` values.

The aggregation keeps included, excluded, rejected, evaluated and missing optionality counts explicit. It does not resolve herd data, query another tenant, decide disclosure, bypass privacy gates, create a public response, forecast future eligibility or persist any report.

## Files Changed

- `packages/livestock_application/market_supply.py`
- `tests/livestock_application/test_market_supply.py`
- `docs/adr/0073-temporal-market-optionality-and-policy-versioned-readiness.md`
- `docs/specs/approved/2026-09-03-market-optionality-temporal-readiness.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

Added:

- `MarketSupplyOptionalityAggregation`;
- `MarketSupplyOptionalityAggregationService`.

The service validates:

- readiness reports correspond one-to-one with authorized snapshots;
- readiness reports cover exactly the included snapshot subjects;
- optionality assessments belong to the included candidate population;
- optionality assessments match Organization, purpose, Policy/version, `reference_time` and `knowledge_cutoff`.

## Invariants Preserved

- F5 does not perform global Animal lookup.
- F5 does not resolve cross-tenant data.
- F5 does not create or change privacy thresholds.
- F5 does not decide disclosure or release a public aggregate.
- F5 does not execute Rules.
- F5 does not emit Evaluation or Decision.
- F5 does not create forecast or CommercialDemand persistence.
- Missing optionality remains explicit and is not treated as negative fact.
- Exclusions and rejected contributions remain visible internally and are not removed from accounting.

## Tests Added

`tests/livestock_application/test_market_supply.py` now also covers:

- readiness and optionality counts over an authorized snapshot;
- explicit missing optionality and excluded subject counts;
- rejection of optionality assessments outside the candidate population.

## Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply.py tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_optionality.py -q` - 48 passed.
- `python -m uv run --locked ruff check packages/livestock_application/market_supply.py tests/livestock_application/test_market_supply.py` - passed.
- `python -m uv run --locked ruff format --check packages/livestock_application/market_supply.py tests/livestock_application/test_market_supply.py` - passed.
- `python -m uv run --locked python -m mypy packages/livestock_application/market_supply.py` - passed.

## Migrations

None.

## Security Impact

No new API, route, permission, grant, sharing path, notification, worker or cross-tenant query was introduced.

## Tenant Isolation Impact

Positive. The service refuses optionality material outside the supplied authorized candidate population and validates context alignment against each snapshot.

## Temporal Semantics Impact

Positive. Optionality assessments must match the snapshot `reference_time` and `knowledge_cutoff`; later knowledge cannot be blended into the aggregate.

## Remaining Gaps

- Public release still depends on existing privacy/disclosure/audit gates.
- Forecast remains outside this cut.
- CommercialDemand persistence remains outside this cut.
- F6 Dossier/VerificationBundle integration remains future work and may require a separate semantic decision.

## Human Decisions Required

No additional decision is required for F5. New privacy profile semantics, detailed disclosure, forecast, persisted reports, CommercialDemand lifecycle or Dossier/VerificationBundle changes require separate approval.
