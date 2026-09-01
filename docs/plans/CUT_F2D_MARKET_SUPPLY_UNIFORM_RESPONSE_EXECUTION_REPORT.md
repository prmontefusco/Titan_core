# CUT F2D - Market Supply Uniform Response Execution Report

Status: IMPLEMENTED AS APPLICATION MAPPER / NO API / NO HTTP CONTRACT / NO BUYER-FACING ACCESS

Date: 2026-08-28

## 1. Scope

CUT F2D implements the public-response mapping rule required by ADR-0070: authorization denials and privacy suppressions must not expose distinct public shapes.

It does not implement CUT F3. It does not create a route, endpoint, HTTP status policy, persistence, migration, CommercialDemand, CandidatePopulation resolver, cross-tenant query or report storage.

## 2. Code Changed

- `packages/livestock_application/market_supply_response.py`
  - Defines `MarketSupplyPublicResponseStatus`.
  - Defines `MarketSupplyPublicAggregateResponse`.
  - Defines `MarketSupplyPublicResponseMapper`.

The mapper receives a `MarketSupplyAggregateQueryAuditEnvelope`. It releases the supplied aggregate payload only when the envelope's external disposition is `RELEASE_AGGREGATE`. Otherwise, it returns `NOT_RELEASED` with no aggregate payload and no internal denial/suppression reason.

## 3. Semantics

Public output is intentionally smaller than audit material:

- internal audit envelope preserves authorization and privacy reasons;
- public response for denied/suppressed outputs exposes only `NOT_RELEASED`;
- aggregate payload is required only for permitted release;
- no HTTP status, message wording or API schema is decided in this cut.

## 4. Architectural Boundaries

- No endpoint or API contract was created.
- No persistence or migration was introduced.
- No cross-Organization query was introduced.
- No Animal, Policy, Rule, Evaluation, Decision, Dossier or VerificationBundle semantics changed.
- No Evidence/Fact boundary changed.

## 5. Security Impact

Positive but preparatory. F2D prevents application-level callers from accidentally exposing different shapes for missing authorization versus privacy suppression.

Remaining production risk: endpoint behavior, timing behavior, pagination, cache headers, HTTP status, retry behavior and telemetry must be approved and tested before buyer-facing release.

## 6. Tenant Isolation Impact

No tenant read path exists. The mapper only consumes an envelope from F2C and a caller-supplied aggregate payload.

## 7. Temporal Semantics Impact

No temporal model changed. Temporal evidence remains in F2/F2B/F2C inputs.

## 8. Tests Added

- `tests/livestock_application/test_market_supply_response.py`

Covered scenarios:

- authorization denial and privacy suppression produce the same public response;
- not-released response does not expose internal reasons;
- released response contains only the supplied aggregate payload;
- release requires an aggregate payload.

## 9. Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_authorization.py`
- `python -m uv run --locked python -m ruff check packages/livestock_application/market_supply_response.py tests/livestock_application/test_market_supply_response.py`
- `python -m uv run --locked python -m ruff format --check packages/livestock_application/market_supply_response.py tests/livestock_application/test_market_supply_response.py`
- `python -m uv run --locked python -m mypy packages/livestock_application/market_supply_response.py tests/livestock_application/test_market_supply_response.py`

## 10. Migrations

None.

## 11. HUMAN GATES Remaining

- Approve public HTTP/API semantics for uniform denial/suppression.
- Approve timing/cache/pagination behavior for non-release responses.
- Approve persistent audit model.
- Approve concrete production `AggregationPrivacyPolicy` profile.
- Approve CUT F3 before any buyer-facing cross-Organization aggregate visibility.
