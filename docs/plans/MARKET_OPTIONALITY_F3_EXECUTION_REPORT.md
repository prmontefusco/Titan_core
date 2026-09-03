# Market Optionality F3 Execution Report

**Status:** COMPLETED  
**Date:** 2026-09-03  
**Scope:** transient Policy-change optionality impact classification over NEXT-07.

## Summary

F3 connects Market Optionality to the existing NEXT-07 `MarketChangeImpactAssessment` without executing Rules, creating new Evaluations/Decisions, persisting a plan, sending notifications or using workers.

The new service composes:

```text
MarketChangeImpactAssessment
  + previous MarketOptionAssessment
  + optional replacement MarketOptionAssessment
  -> MarketOptionChangeImpactReport
```

If a replacement optionality assessment is not supplied, an affected entry remains `REASSESSMENT_NEEDED`; the service does not infer the result of the replacement Policy.

## Files Changed

- `packages/livestock_application/market_optionality.py`
- `tests/livestock_application/test_market_optionality.py`
- `docs/adr/0073-temporal-market-optionality-and-policy-versioned-readiness.md`
- `docs/specs/approved/2026-09-03-market-optionality-temporal-readiness.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

Added:

- `MarketOptionChangeImpactState`;
- `MarketOptionChangeImpactEntry`;
- `MarketOptionChangeImpactReport`;
- `MarketOptionChangeImpactService`.

The service classifies potential optionality impact as:

- `UNCHANGED`;
- `REASSESSMENT_NEEDED`;
- `OPTIONALITY_UNKNOWN_UNDER_REPLACEMENT`;
- `OPTIONALITY_PRESERVED`;
- `OPTIONALITY_AT_RISK`;
- `OPTIONALITY_LOST`;
- `LIMITED`.

## Invariants Preserved

- F3 does not execute Rules.
- F3 does not emit Evaluation or Decision.
- F3 does not mutate historical Evaluation/Decision hashes or results.
- `AFFECTED` from NEXT-07 remains potential impact, not non-compliance.
- Replacement optionality must be supplied explicitly if the caller wants comparison against a new known conclusion.
- Missing replacement material becomes `REASSESSMENT_NEEDED`, not an inferred failure.
- Unrelated market purpose remains `UNCHANGED`.

## Tests Added

`tests/livestock_application/test_market_optionality.py` now also covers:

- Policy v1 open -> replacement v2 unavailable yields `REASSESSMENT_NEEDED`;
- Policy v1 open -> supplied replacement v3 incompatible yields `OPTIONALITY_LOST`;
- unrelated market remains `UNCHANGED`.

## Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_optionality.py tests/livestock_application/test_market_change_impact.py -q` - 19 passed.
- `python -m uv run --locked ruff check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked ruff format --check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked python -m mypy packages/livestock_application/market_optionality.py` - passed.

## Migrations

None.

## Security Impact

No new API, route, permission, grant, notification, worker, sharing path or cross-tenant query was introduced.

## Tenant Isolation Impact

No infrastructure access was introduced. F3 composes supplied application objects and inherits NEXT-07 Organization filtering.

## Temporal Semantics Impact

Positive. F3 uses the existing NEXT-07 context containing `reference_time`, `knowledge_cutoff`, previous Policy/version and replacement Policy/version. It does not treat a Policy change as a historical rewrite.

## Remaining Gaps

- Persistent `NormativeReevaluationPlan` remains outside this cut.
- Worker execution and notification remain outside this cut.
- F4 option preservation warnings remain future work.
- F5 supply readiness aggregation remains future work.

## Human Decisions Required

No additional decision is required for F3. Persistence, async re-evaluation, public API, notification, real regulatory change handling or Dossier changes require separate approval.
