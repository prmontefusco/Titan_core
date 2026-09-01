# CUT F3.5D - Market Supply privacy profile contract report

**Date:** 2026-09-01  
**Status:** IMPLEMENTED / VERIFIED  
**Scope:** explicit privacy profile loading contract for future F3.5 endpoint

## Summary

F3.5D adds an application-level contract for loading a versioned
`AggregationPrivacyProfile` from explicit configuration values.

It does not define a universal production threshold and does not create a
default production profile. Missing or invalid configuration fails closed.

## Files Changed

- `packages/livestock_application/market_supply_privacy.py`
- `tests/livestock_application/test_market_supply_privacy.py`
- `docs/plans/CUT_F3_5_MARKET_SUPPLY_RELEASE_GATE_PACKAGE.md`
- `docs/plans/CUT_F3_MARKET_SUPPLY_AGGREGATE_VISIBILITY_BUILD_PLAN.md`
- `docs/plans/MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_FINAL_REPORT.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

`market_supply_privacy.py` now defines:

- `AggregationPrivacyProfile`;
- `MARKET_SUPPLY_PRIVACY_PROFILE_CONFIG_KEYS`;
- `load_aggregation_privacy_profile(...)`.

The loader requires all values to be provided explicitly:

- `TITAN_MARKET_SUPPLY_PRIVACY_PROFILE_ID`;
- `TITAN_MARKET_SUPPLY_PRIVACY_POLICY_VERSION`;
- `TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_ORGANIZATIONS`;
- `TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_PROPERTIES`;
- `TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_SUBJECTS`;
- `TITAN_MARKET_SUPPLY_PRIVACY_MAX_FILTER_COUNT_WITHOUT_REVIEW`;
- `TITAN_MARKET_SUPPLY_PRIVACY_REPEATED_QUERY_WINDOW_SECONDS`.

No numeric value is hardcoded as production policy.

## Tests Added

`tests/livestock_application/test_market_supply_privacy.py` verifies:

- missing configuration fails closed;
- explicit configuration builds a versioned profile;
- invalid numeric values are rejected.

## Tests Executed

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_workflow.py tests/livestock_application/test_market_supply_response.py -q
python -m uv run --locked python -m ruff check packages/livestock_application/market_supply_privacy.py tests/livestock_application/test_market_supply_privacy.py
python -m uv run --locked python -m ruff format --check packages/livestock_application/market_supply_privacy.py tests/livestock_application/test_market_supply_privacy.py
python -m uv run --locked python -m mypy packages/livestock_application/market_supply_privacy.py tests/livestock_application/test_market_supply_privacy.py
```

Results:

```text
56 passed
ruff check passed
ruff format --check passed
mypy passed
```

## Impact

- **Security impact:** positive. Missing privacy configuration cannot silently
  release aggregates using implicit defaults.
- **Tenant isolation impact:** none. No access path was added.
- **Temporal semantics impact:** none.
- **Migrations:** none.
- **Public API:** no new route.

## Remaining Gates Before F3.5 Release

- Production Candidate Population source.
- Concrete deployment approval of profile values.
- Human release gate for the first buyer-facing cross-Organization aggregate
  surface.

## Required Status

Technical status: PASS  
Policy deviation: NONE  
Unresolved security findings: NONE  
New cross-tenant semantics: NONE  
Human decision required: YES, for concrete production profile values and the
remaining F3.5 release gates.
