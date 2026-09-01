# CUT F3.5B - Market Supply aggregate permission report

**Date:** 2026-09-01  
**Status:** IMPLEMENTED / VERIFIED  
**Scope:** permission catalog for future F3.5 aggregate endpoint

## Summary

The approved F3.5 permission gate is now implemented at the application
permission catalog level.

The permission code is:

```text
MARKET_SUPPLY.AGGREGATE_ASSESS
```

It is included in `LIVESTOCK_PERMISSIONS` so seed/test environments can create
the catalog record, but it is not granted by any default role. This preserves
the approved separation between the existence of a capability and operational
authorization to use it.

## Files Changed

- `packages/livestock_application/authorization.py`
- `tests/livestock_application/test_livestock_authorization.py`
- `docs/plans/CUT_F3_5_MARKET_SUPPLY_RELEASE_GATE_PACKAGE.md`
- `docs/plans/CUT_F3_MARKET_SUPPLY_AGGREGATE_VISIBILITY_BUILD_PLAN.md`
- `docs/plans/MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_FINAL_REPORT.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

`packages/livestock_application/authorization.py` now defines
`MARKET_SUPPLY_AGGREGATE_ASSESS` and includes it in the Market Supply permission
set that feeds `LIVESTOCK_PERMISSIONS`.

The permission is deliberately absent from:

- `OPERADOR_PECUARIO`;
- `AUDITOR`;
- `FRIGORIFICO`;
- every other default role.

No role receives buyer-facing aggregate visibility by default.

## Tests Added

`tests/livestock_application/test_livestock_authorization.py` verifies:

- the permission code is the approved `MARKET_SUPPLY.AGGREGATE_ASSESS`;
- the permission is catalogued in `LIVESTOCK_PERMISSIONS`;
- default roles do not receive the permission.

## Tests Executed

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_livestock_authorization.py tests/api/test_core_public_surface.py -q
python -m uv run --locked python -m ruff check packages/livestock_application/authorization.py tests/livestock_application/test_livestock_authorization.py tests/api/test_core_public_surface.py
python -m uv run --locked python -m mypy packages/livestock_application/authorization.py tests/livestock_application/test_livestock_authorization.py tests/api/test_core_public_surface.py
```

Results:

```text
13 passed
ruff check passed
mypy passed
```

## Impact

- **Security impact:** positive. Capability exists, but no default role gains it.
- **Tenant isolation impact:** none. No access path was added.
- **Temporal semantics impact:** none.
- **Migrations:** none.
- **Public API:** no new route.

## Remaining Gates Before F3.5 Release

- HTTP behavior, cache and external response contract.
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
