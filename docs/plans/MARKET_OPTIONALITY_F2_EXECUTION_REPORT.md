# Market Optionality F2 Execution Report

**Status:** COMPLETED  
**Date:** 2026-09-03  
**Scope:** transient multi-market optionality report in Titan Livestock application.

## Summary

F2 adds a pure application report that assesses one Animal subject across multiple explicit market purposes. It composes F1 `MarketOptionAssessment` results and keeps every conclusion derived from existing Evaluation/Decision/Policy material.

The report is deterministic, non-persistent and non-decisional. It does not introduce a market catalog, country-specific services, global Animal lookup, API, migration, UI, worker, forecast or cross-tenant query.

## Files Changed

- `packages/livestock_application/market_optionality.py`
- `tests/livestock_application/test_market_optionality.py`
- `docs/adr/0073-temporal-market-optionality-and-policy-versioned-readiness.md`
- `docs/specs/approved/2026-09-03-market-optionality-temporal-readiness.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

Added:

- `MarketOptionInput`;
- `MultiMarketOptionReport`;
- `MultiMarketOptionReportService`.

The service validates that all inputs in a report refer to the same Organization, subject, `reference_time`, `knowledge_cutoff`, target window and result boundary. It rejects duplicate `market_purpose` values because they make policy selection ambiguous for this transient report.

## Invariants Preserved

- `MultiMarketOptionReport` is not `Evaluation`.
- `MultiMarketOptionReport` is not `Decision`.
- `MultiMarketOptionReport` is not `MarketReadiness`.
- No Animal eligibility field was created.
- No market/country registry was introduced.
- No Policy or Rule logic was embedded in application services.
- `reference_time` and `knowledge_cutoff` remain mandatory and common to the report.
- Unsupported Policy remains `POLICY_UNAVAILABLE`, not non-compliance.
- Policy version mismatch affects only the corresponding market purpose and does not mutate historical Decisions.

## Tests Added

`tests/livestock_application/test_market_optionality.py` now also covers:

- synthetic EU/US/CN market purposes in one deterministic report;
- unsupported market as `POLICY_UNAVAILABLE`;
- ambiguous duplicate market purpose rejection;
- one Policy version change requiring reassessment without affecting other market purposes.

## Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_optionality.py -q` - 12 passed.

The direct form `python -m uv run --locked pytest ...` failed locally with `uv trampoline failed to canonicalize script path`; the repository-compatible `python -m pytest` invocation inside `uv run --locked` was used.

## Migrations

None.

## Security Impact

No new API, route, permission, grant, sharing path or cross-tenant query was introduced.

## Tenant Isolation Impact

Positive application-level validation: a multi-market report cannot mix Organizations or subjects.

## Temporal Semantics Impact

Positive. The report requires every market assessment to share the same `reference_time`, `knowledge_cutoff` and target window.

## Remaining Gaps

- F3 policy change impact integration remains future work.
- F4 option preservation warnings remain future work.
- F5 supply readiness aggregation remains future work.
- Public naming and UX remain intentionally unapproved.

## Human Decisions Required

No additional decision is required for F2. Future persistence, API, cross-tenant aggregate optionality, real market catalog semantics, AI explanations or Dossier changes require separate approval.
