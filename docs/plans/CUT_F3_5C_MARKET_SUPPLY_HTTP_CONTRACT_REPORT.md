# CUT F3.5C - Market Supply HTTP behavior contract report

**Date:** 2026-09-01  
**Status:** IMPLEMENTED / VERIFIED  
**Scope:** application-level HTTP behavior contract for future F3.5 endpoint

## Summary

The F3.5 HTTP/public behavior gate is closed at the application contract level.
No endpoint was created.

The accepted behavior remains:

- released aggregate: `200 OK` with `status=RELEASED`;
- protected non-release: `200 OK` with `status=NOT_RELEASED`;
- invalid request shape: existing validation convention;
- idempotency conflict: existing Core idempotency conflict behavior;
- no pagination in F3.5;
- no reason-specific timing class;
- every future buyer-facing Market Supply response uses:

```text
Cache-Control: no-store
Pragma: no-cache
```

## Files Changed

- `packages/livestock_application/market_supply_response.py`
- `tests/livestock_application/test_market_supply_response.py`
- `docs/plans/CUT_F3_5_MARKET_SUPPLY_RELEASE_GATE_PACKAGE.md`
- `docs/plans/CUT_F3_MARKET_SUPPLY_AGGREGATE_VISIBILITY_BUILD_PLAN.md`
- `docs/plans/MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_FINAL_REPORT.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

`MarketSupplyPublicResponseMapper` now exposes `sensitive_response_headers()`,
returning an immutable no-store header mapping for the future F3.5 route.

This keeps FastAPI concerns outside the application mapper while still making
the cache behavior an executable contract before the endpoint exists.

## Tests Added

`tests/livestock_application/test_market_supply_response.py` now verifies that
the Market Supply public response headers are:

- `Cache-Control: no-store`;
- `Pragma: no-cache`.

## Tests Executed

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_response.py tests/api/test_core_public_surface.py -q
python -m uv run --locked python -m ruff check packages/livestock_application/market_supply_response.py tests/livestock_application/test_market_supply_response.py tests/api/test_core_public_surface.py
python -m uv run --locked python -m ruff format --check packages/livestock_application/market_supply_response.py tests/livestock_application/test_market_supply_response.py tests/api/test_core_public_surface.py
python -m uv run --locked python -m mypy packages/livestock_application/market_supply_response.py tests/livestock_application/test_market_supply_response.py tests/api/test_core_public_surface.py
```

## Impact

- **Security impact:** positive. Cache behavior is explicit before public
  release.
- **Tenant isolation impact:** none. No access path was added.
- **Temporal semantics impact:** none.
- **Migrations:** none.
- **Public API:** no new route.

## Remaining Gates Before F3.5 Release

- Production Candidate Population source.
- Initial production privacy profile.
- Human release gate for the first buyer-facing cross-Organization aggregate
  surface.

## Required Status

Technical status: PASS  
Policy deviation: NONE  
Unresolved security findings: NONE  
New cross-tenant semantics: NONE  
Human decision required: YES, for the remaining F3.5 release gates listed above.
