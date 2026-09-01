# CUT F2 Execution Report - Market Supply Authorization/Profile Preparation

Date: 2026-08-28

Status: IMPLEMENTED WITHIN PREPARATION-ONLY LIMITS

## Scope

CUT F2 prepares purpose-bound authorization checks for future Market Supply visibility by composing the existing Core `AuthorizationGrant` shape.

It does not implement:

- buyer aggregate analytics;
- cross-Organization herd query;
- production API;
- persistence;
- migration;
- grant creation workflow;
- new Core authorization aggregate;
- Livestock-only consent model;
- FieldScope persistence;
- AggregationPrivacyPolicy runtime;
- query audit persistence;
- CommercialDemand persistence;
- Dossier or VerificationBundle changes.

## Implementation

Created `packages/livestock_application/market_supply_authorization.py`.

The module defines:

- `MARKET_SUPPLY_AGGREGATE_ASSESSMENT`;
- `MARKET_SUPPLY_CANDIDATE_DISCLOSURE`;
- `MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE`;
- `MARKET_SUPPLY_CANDIDATE_DISCLOSURE_FIELD_SCOPE`;
- `MarketSupplyAuthorizationRequest`;
- `MarketSupplyAuthorizationAssessment`;
- `MarketSupplyAuthorizationService`.

The service evaluates a supplied `AuthorizationGrant` for:

- grant presence;
- active status;
- validity window using `valid_from <= requested_at < valid_until`;
- owner Organization match;
- beneficiary Organization match;
- Policy match;
- exact AccessPurpose match;
- exact field scope profile match.

Aggregate assessment and candidate disclosure are separate methods. An aggregate grant cannot authorize candidate disclosure.

## Production Code Changed

Added one production application module:

- `packages/livestock_application/market_supply_authorization.py`

No existing production behavior was changed.

## Tests Added

Created `tests/livestock_application/test_market_supply_authorization.py` with coverage for:

- active matching aggregate grant permits;
- missing grant denies;
- revoked, expired, owner mismatch, beneficiary mismatch, Policy mismatch, purpose mismatch and field-scope mismatch deny;
- aggregate purpose never authorizes candidate disclosure;
- candidate disclosure requires its own purpose and field scope;
- request requires Policy ID and UTC requested_at.

## Verification

Focused checks:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply.py tests/livestock_application/test_market_readiness.py
```

Result: 26 passed.

```text
python -m uv run --locked python -m ruff check packages/livestock_application/market_supply_authorization.py tests/livestock_application/test_market_supply_authorization.py packages/livestock_application/market_supply.py tests/livestock_application/test_market_supply.py
```

Result: all checks passed.

```text
python -m uv run --locked python -m ruff format --check packages/livestock_application/market_supply_authorization.py tests/livestock_application/test_market_supply_authorization.py packages/livestock_application/market_supply.py tests/livestock_application/test_market_supply.py
```

Result: 4 files already formatted.

```text
python -m uv run --locked python -m mypy packages/livestock_application/market_supply_authorization.py tests/livestock_application/test_market_supply_authorization.py packages/livestock_application/market_supply.py tests/livestock_application/test_market_supply.py
```

Result: success, no issues found in 4 source files.

```text
python -m uv run --locked python -m pytest
```

Result: 1198 passed, 284 skipped.

```text
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m alembic check
```

Result: `No new upgrade operations detected`, with the known PostGIS `geometry` warning.

Repository-wide checks still have preexisting failures outside CUT F2:

- `python -m uv run --locked python -m ruff check .` fails in BuyerPolicy realistic integration tests and one migration import block.
- `python -m uv run --locked python -m mypy` reports existing BuyerPolicy protocol/type errors.

## Security and Tenant Isolation

Positive: F2 encodes denial-by-default preparation and purpose separation without reading protected data. No query, endpoint, repository read or cross-tenant traversal was introduced.

## Temporal Semantics

Grant validity uses a half-open interval: `valid_from <= requested_at < valid_until`. Revoked/inactive grants deny. No historical Evaluation, Decision, Dossier or VerificationBundle is changed.

## Remaining Gates

- Approve concrete production `AggregationPrivacyPolicy` profile values before F3.
- Implement persistent query audit, retention and operational differencing controls before production cross-Organization aggregate API.
- Decide whether existing `AuthorizationGrant` persistence is sufficient for Market Supply or whether a specific grant/profile migration is required.
- Approve `CommercialDemand` persistence/API before buyer aggregate demand analysis.
- Approve F3 explicitly before any buyer-facing aggregate visibility.
