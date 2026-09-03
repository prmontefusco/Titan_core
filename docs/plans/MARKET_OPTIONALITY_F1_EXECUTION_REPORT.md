# Market Optionality F1 Execution Report

**Status:** COMPLETED  
**Date:** 2026-09-03  
**Scope:** pure transient `MarketOptionAssessment` projection in Titan Livestock application.

## Summary

F1 introduces an application-only Market Optionality projection. It maps canonical Evaluation/Decision/RuleResult material into explicit market option states without executing Rules, emitting Decisions, persisting artifacts or changing Animal state.

## Files Changed

- `packages/livestock_application/market_optionality.py`
- `tests/livestock_application/test_market_optionality.py`
- `docs/adr/0073-temporal-market-optionality-and-policy-versioned-readiness.md`
- `docs/specs/approved/2026-09-03-market-optionality-temporal-readiness.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

Added:

- `MarketOptionContext`;
- `MarketOptionState`;
- `MarketOptionReversibility`;
- `MarketOptionAssessment`;
- `MarketOptionAssessmentService`.

The service delegates context compatibility to existing `MarketReadinessService` and then derives optionality-specific states:

- `OPTION_OPEN`;
- `OPTION_AT_RISK`;
- `MISSING_EVIDENCE`;
- `UNKNOWN`;
- `POLICY_UNAVAILABLE`;
- `REASSESSMENT_REQUIRED`;
- `TEMPORARILY_INCOMPATIBLE`;
- `IRREVERSIBLY_INCOMPATIBLE`;
- `NOT_EVALUATED`.

## Invariants Preserved

- `MarketOptionAssessment` is not `Evaluation`.
- `MarketOptionAssessment` is not `Decision`.
- `MarketOptionAssessment` is not `MarketReadiness`.
- No Animal eligibility field was created.
- No Policy or Rule logic was embedded in application services.
- `reference_time` and `knowledge_cutoff` are mandatory.
- Missing evidence is not incompatibility.
- Policy unavailable is not non-compliance.
- Policy mismatch requires reassessment and does not mutate historical Decision.
- Reversibility remains derived from canonical reasons/limitations.

## Tests Added

`tests/livestock_application/test_market_optionality.py` covers:

- ready Decision preserves option;
- missing evidence remains distinct from incompatibility;
- Policy V1 to V2 requires reassessment without mutating historical Decision;
- unavailable Policy remains distinct from unknown and not-ready;
- rejected Decision defaults to temporary incompatibility;
- irreversible marker keeps permanent loss distinct;
- temporal coordinates and target window validation;
- missing Decision is `NOT_EVALUATED`, not open.

## Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_optionality.py tests/livestock_application/test_market_readiness.py -q` - 19 passed.
- `python -m uv run --locked ruff check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked ruff format --check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked python -m mypy packages/livestock_application/market_optionality.py` - passed.
- `python -m uv run --locked python -m pytest -q` with PostgreSQL active - 1625 passed, 1 skipped, 4 warnings.
- `python -m uv run --locked ruff check .` - passed.
- `python -m uv run --locked ruff format --check .` - passed.
- `python -m uv run --locked python -m mypy` - passed.
- `python -m uv run --locked python -m alembic check` - passed with the known PostGIS `geometry` warning.

## Migrations

None.

## Security Impact

No new API, route, permission, grant, data sharing path or cross-tenant query was introduced.

## Tenant Isolation Impact

No infrastructure access was introduced. The context requires an Organization and reuses existing readiness checks that reject Organization mismatch.

## Temporal Semantics Impact

Positive. `MarketOptionContext` requires UTC `reference_time` and `knowledge_cutoff`; target window, when provided, must be a non-empty semi-open interval.

## Remaining Gaps

- State naming needs real-world validation before public API/UX.
- F2 multi-market report is not implemented.
- Policy change impact integration remains future F3.
- Preservation warnings remain future F4.
- Supply readiness aggregation remains future F5.

## Human Decisions Required

No additional decision is required for F1. Future persistence, API, cross-tenant aggregate optionality, AI explanations or Dossier changes require separate approval.
