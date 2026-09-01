# CUT F2E - Market Supply Revocation Semantics Execution Report

Status: IMPLEMENTED AS AUTHORIZATION HARDENING / NO API / NO PERSISTENCE CHANGE / NO BUYER-FACING ACCESS

Date: 2026-08-28

## 1. Scope

CUT F2E hardens the Market Supply authorization guard so `revoked_at` is treated as an effective temporal boundary for new aggregate or candidate-disclosure access.

It does not implement CUT F3. It does not create persistence, migration, route, endpoint, cross-tenant query, CommercialDemand, CandidatePopulation resolver, audit storage or report storage.

## 2. Code Changed

- `packages/livestock_application/market_supply_authorization.py`
  - Added `MarketSupplyAuthorizationReason.REVOKED_GRANT`.
  - Denies access when `grant.revoked_at <= request.requested_at`, even if a stale grant object still says `status="ATIVO"`.

## 3. Semantics

Revocation remains prospective:

- request before `revoked_at` can still be permitted if all other checks pass;
- request at `revoked_at` is denied;
- request after `revoked_at` is denied;
- inactive/revoked status still denies independently.

This does not erase, rewrite or invalidate material previously delivered under a valid grant.

## 4. Architectural Boundaries

- No `AuthorizationGrant` domain or persistence schema changed.
- No cross-Organization data read was introduced.
- No public response/API behavior changed.
- No Evaluation, Decision, Dossier or VerificationBundle semantics changed.

## 5. Security Impact

Positive. Future Market Supply access cannot pass through the preparation guard using a stale active status when `revoked_at` is already effective.

## 6. Tenant Isolation Impact

No tenant boundary changed.

## 7. Temporal Semantics Impact

The authorization check now explicitly observes the temporal revocation boundary relative to `requested_at`.

## 8. Tests Added

- `tests/livestock_application/test_market_supply_authorization.py`

Covered scenarios:

- `revoked_at == requested_at` denies;
- `requested_at < revoked_at` may permit;
- `requested_at > revoked_at` denies.

## 9. Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_response.py`
- `python -m uv run --locked python -m ruff check packages/livestock_application/market_supply_authorization.py tests/livestock_application/test_market_supply_authorization.py packages/livestock_application/market_supply_audit.py tests/livestock_application/test_market_supply_audit.py packages/livestock_application/market_supply_response.py tests/livestock_application/test_market_supply_response.py`
- `python -m uv run --locked python -m mypy packages/livestock_application/market_supply_authorization.py tests/livestock_application/test_market_supply_authorization.py packages/livestock_application/market_supply_audit.py tests/livestock_application/test_market_supply_audit.py packages/livestock_application/market_supply_response.py tests/livestock_application/test_market_supply_response.py`

## 10. Migrations

None.

## 11. HUMAN GATES Remaining

- Approve producer opt-in/revocation UX and authority model.
- Approve persistent audit model and revocation audit retention.
- Approve public HTTP/timing/cache semantics after revocation.
- Approve CUT F3 before buyer-facing cross-Organization aggregate visibility.
