# CUT F3.1 - Disclosure Decision and Request Identity Execution Report

Date: 2026-08-28

Status: IMPLEMENTED PARTIALLY / INTERNAL APPLICATION BOUNDARY ONLY

## Scope

This cut implements the safe, non-persistent portion of F3.1 approved by
ADR-0071 and the F3 build plan:

- semantic Market Supply request identity for idempotency;
- explicit `DisclosureDecision` value produced from aggregation privacy
  assessment;
- clearer internal audit outcomes for authorization denials that must remain
  uniform externally.

No buyer-facing endpoint, migration, persistent audit table, production privacy
profile, cross-tenant query or CommercialDemand persistence was introduced.

## Code Changed

- `packages/livestock_application/market_supply_request.py`
  - Added `MarketSupplyRequestIdentity`.
  - Binds buyer Organization, purpose, Policy/version, demand digest, candidate
    criteria digest, `reference_time`, `knowledge_cutoff` and idempotency key.
  - Produces a stable semantic digest so same key plus different semantics can
    be detected before population resolution in a later orchestration cut.

- `packages/livestock_application/market_supply_privacy.py`
  - Added `DisclosureDecisionState`.
  - Added immutable `DisclosureDecision`.
  - Added conversion from `AggregationPrivacyAssessment` to
    `DisclosureDecision`.
  - Preserves privacy reason codes, policy version, query fingerprint,
    candidate population digest and UTC evaluation time.

- `packages/livestock_application/market_supply_audit.py`
  - Split internal authorization denial outcomes into
    `PURPOSE_MISMATCH`, `GRANT_REVOKED` and generic
    `DENIED_BY_AUTHORIZATION`.
  - Kept external disposition uniform through
    `UNIFORM_NOT_RELEASED`.

## Tests Added

- Stable semantic digest for identical Market Supply request identity.
- Same idempotency key with different temporal coordinates produces a distinct
  semantic digest.
- Request identity requires Policy identity and UTC temporal coordinates.
- Privacy assessment maps permitted and suppressed outcomes to explicit
  `DisclosureDecision` values.
- `DisclosureDecision` requires candidate population digest and UTC
  `evaluated_at`.
- Authorization failures preserve specific internal audit outcomes while keeping
  the public disposition uniform.

## Tests Executed

Passed:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_request.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_workflow.py
```

Result: 28 passed.

Passed:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_request.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply.py tests/unit/test_market_supply_synthetic.py
```

Result: 63 passed.

Passed:

```text
python -m uv run --locked python -m ruff check packages/livestock_application/market_supply.py packages/livestock_application/market_supply_authorization.py packages/livestock_application/market_supply_privacy.py packages/livestock_application/market_supply_audit.py packages/livestock_application/market_supply_response.py packages/livestock_application/market_supply_workflow.py packages/livestock_application/market_supply_population.py packages/livestock_application/market_supply_request.py tests/livestock_application/test_market_supply.py tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_supply_request.py tests/unit/test_market_supply_synthetic.py
python -m uv run --locked python -m ruff format --check packages/livestock_application/market_supply.py packages/livestock_application/market_supply_authorization.py packages/livestock_application/market_supply_privacy.py packages/livestock_application/market_supply_audit.py packages/livestock_application/market_supply_response.py packages/livestock_application/market_supply_workflow.py packages/livestock_application/market_supply_population.py packages/livestock_application/market_supply_request.py tests/livestock_application/test_market_supply.py tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_supply_request.py tests/unit/test_market_supply_synthetic.py
python -m uv run --locked python -m mypy packages/livestock_application/market_supply.py packages/livestock_application/market_supply_authorization.py packages/livestock_application/market_supply_privacy.py packages/livestock_application/market_supply_audit.py packages/livestock_application/market_supply_response.py packages/livestock_application/market_supply_workflow.py packages/livestock_application/market_supply_population.py packages/livestock_application/market_supply_request.py tests/livestock_application/test_market_supply.py tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_supply_request.py tests/unit/test_market_supply_synthetic.py
```

Result: Ruff passed. Ruff format check passed. Mypy passed.

Global verification passed:

```text
python -m uv run --locked python -m pytest
python -m uv run --locked python -m ruff check .
python -m uv run --locked python -m ruff format --check .
python -m uv run --locked python -m mypy
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m alembic check
```

Result: 1240 passed, 284 skipped. Ruff passed. Ruff format check passed. Mypy
passed. Alembic reported `No new upgrade operations detected` and emitted the
known repository PostGIS `geometry` warning for `property_geometries.geom`.

## Migrations

None.

## Security Impact

This cut strengthens the internal security model by separating:

- request idempotency key from semantic request identity;
- authorization result from disclosure decision;
- internal audit reason from external public disposition.

No new external behavior or access path was introduced.

## Tenant Isolation Impact

No tenant boundary changed. The request identity and disclosure value require
Organization coordinates but do not read cross-tenant data.

## Temporal Semantics Impact

`reference_time` and `knowledge_cutoff` are mandatory UTC coordinates in
`MarketSupplyRequestIdentity`. `DisclosureDecision.evaluated_at` is also UTC.
Changing temporal coordinates changes request semantics.

## Remaining Work

- F3.2: durable append-only `MarketSupplyQueryAuditRecord` design approval and
  implementation.
- F3.2B: persisted query-history/differencing assessment.
- F3.3: production Candidate Population resolver over approved contribution
  source.
- F3.4: orchestration with durable audit-before-release invariant.
- F3.5: buyer-facing API only after release gate.

## Human Decisions Required

None for this internal implementation cut.

Schema, retention, production privacy profile values, production contribution
source and public HTTP behavior remain future policy decisions before later F3
cuts.
