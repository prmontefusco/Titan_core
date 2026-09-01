# CUT F2C - Market Supply Audit Envelope Execution Report

Status: IMPLEMENTED AS IN-MEMORY AUDIT PLANNER / NO PERSISTENCE / NO BUYER-FACING ACCESS

Date: 2026-08-28

## 1. Scope

CUT F2C defines the audit envelope that future Market Supply aggregate access must produce around authorization and aggregation privacy decisions.

It does not implement CUT F3. It does not create persistence, migration, API, worker, endpoint, CommercialDemand, CandidatePopulation resolver, cross-tenant herd query, report storage or external response contract.

## 2. Code Changed

- `packages/livestock_application/market_supply_audit.py`
  - Defines `MarketSupplyAggregateQueryAuditRequest`.
  - Defines `MarketSupplyAggregateQueryAuditEnvelope`.
  - Defines `MarketSupplyAggregateQueryAuditPlanner`.
  - Defines internal audit outcomes and external disposition categories.

The planner composes existing F2 authorization assessments and F2B privacy assessments into an auditable envelope.

## 3. Semantics

The planner distinguishes:

- authorization denial;
- privacy suppression;
- aggregate release.

For denial and privacy suppression, the external disposition is `UNIFORM_NOT_RELEASED`. Internal reasons are preserved in the envelope for future audit/review, without requiring a public error shape or HTTP status decision in this cut.

## 4. Architectural Boundaries

- No new Core audit subsystem was created.
- No database schema was introduced.
- No existing `SharedPolicyAccessLogEntry` contract was stretched to represent missing-grant or differencing-specific Market Supply metadata.
- No Organization boundary was changed.
- No protected producer data is read or released.
- No Dossier or VerificationBundle semantics changed.

## 5. Security Impact

Positive but preparatory. F2C makes authorization denial and privacy suppression explicitly auditable before any aggregate release path exists.

Remaining production risk: durable storage, retention, deduplication/idempotency, rate limits, query similarity, revocation enforcement and external response uniformity still require approval and implementation.

## 6. Tenant Isolation Impact

No cross-tenant query or repository access was introduced. The envelope carries explicit requester, beneficiary and audit-owner Organizations so a future persistent implementation can enforce ownership and visibility.

## 7. Temporal Semantics Impact

The audit envelope requires UTC `recorded_at`. It references the query fingerprint's UTC `requested_at` from CUT F2B. No historical Evaluation, Decision, Dossier or VerificationBundle is rewritten.

## 8. Tests Added

- `tests/livestock_application/test_market_supply_audit.py`

Covered scenarios:

- authorization denial creates `UNIFORM_NOT_RELEASED` envelope;
- privacy suppression creates `UNIFORM_NOT_RELEASED` envelope with internal privacy reason;
- release requires permitted authorization and permitted privacy;
- privacy assessment is required after authorization permits;
- query fingerprint requester/beneficiary/purpose must match envelope;
- `recorded_at` must be UTC.

## 9. Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_authorization.py`
- `python -m uv run --locked python -m ruff check packages/livestock_application/market_supply_audit.py tests/livestock_application/test_market_supply_audit.py`
- `python -m uv run --locked python -m mypy packages/livestock_application/market_supply_audit.py tests/livestock_application/test_market_supply_audit.py`

## 10. Migrations

None.

## 11. HUMAN GATES Remaining

- Approve persistent audit model and storage location.
- Approve whether Market Supply audit should reuse/extend Core `shared_policy_access_log` or introduce a dedicated table.
- Approve retention, rate limits, idempotency and query similarity behavior.
- Approve public uniform response semantics.
- Approve concrete production `AggregationPrivacyPolicy` values.
- Approve CUT F3 before any buyer-facing cross-Organization aggregate visibility.
