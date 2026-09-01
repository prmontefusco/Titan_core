# CUT F2I - Production Gate Design Closure Report

Status: ADR-0071 ACCEPTED WITH CHANGES / NO API / NO PERSISTENCE / NO MIGRATION / F3 NOT STARTED

Date: 2026-08-28

## 1. Scope

CUT F2I consolidates the remaining production decisions required before a buyer-facing cross-Organization aggregate Market Supply API can be implemented.

This cut does not implement CUT F3. It creates no endpoint, migration, persistence, production resolver, worker, forecast, buyer-facing result or cross-tenant data access.

## 2. Documents Created

- `docs/specs/approved/2026-08-28-market-supply-production-gate-closure.md`
- `docs/adr/0071-market-supply-production-gates-before-cross-tenant-aggregate-api.md`

## 3. Decisions Proposed

- `AggregationPrivacyPolicy` must be configurable and versioned; concrete production values remain HUMAN REVIEW.
- Market Supply should have a dedicated audit/query persistence model unless an ADR explicitly extends an existing audit table.
- Production Candidate Population resolution must operate only over authorized sources and must not be a global Animal lookup.
- `CandidatePopulationSnapshot` digest must be linked to privacy/audit fingerprints before release.
- Future API idempotency should use Core idempotency with a semantic scope based on buyer, purpose, Policy/version, demand/context digest, criteria digest, reference_time and knowledge_cutoff.
- Semantic differencing belongs to the application/audit layer; pure volume rate limiting may live at deployment/gateway.
- Public `NOT_RELEASED` behavior must be uniform across nonexistent, invisible, excluded, denied and suppressed data.
- The first F3 should prefer transient `CommercialDemand` context rather than persisted commercial lifecycle.
- `reference_time` and `knowledge_cutoff` are mandatory semantic coordinates.
- `AuthorizationDecision` and `DisclosureDecision` are distinct.
- `DisclosureDecision` is an explicit architectural concept with ALLOW/GENERALIZE/SUPPRESS/DENY.
- No aggregate result exists independently of CandidatePopulationSnapshot, DisclosureDecision and audit record.
- Semantic query history must support differencing risk evaluation without requiring formal Differential Privacy in this phase.

## 4. Architectural Boundaries Preserved

- Organization isolation remains the default.
- No cross-tenant query was implemented.
- No `CommercialDemand` persistence was implemented.
- No `SupplyForecast` was implemented.
- No `SupplyIntelligenceReport` persistence was implemented.
- No Dossier, VerificationBundle, Evaluation, Decision, Policy, Rule, Fact or Evidence semantics changed.

## 5. Security Impact

Positive, design-only. The proposed ADR makes explicit that F3 remains blocked until privacy profile, audit persistence, idempotency, differencing and uniform HTTP behavior are approved.

## 6. Tenant Isolation Impact

No runtime tenant behavior changed. The proposed resolver contract requires opt-in/grant-authorized sources before any future aggregation.

## 7. Temporal Semantics Impact

No runtime temporal behavior changed. The proposed idempotency/audit/snapshot contracts require `reference_time`, `knowledge_cutoff`, requested/generated times and revocation state to be captured by future F3.

## 8. Tests

No code tests were added because this is a design-only cut.

Verification performed after the adjacent global cleanup:

- `python -m uv run --locked python -m pytest`
- `python -m uv run --locked python -m ruff check .`
- `python -m uv run --locked python -m ruff format --check .`
- `python -m uv run --locked python -m mypy`
- `python -m uv run --locked python -m alembic check`

## 9. HUMAN GATES Remaining

- Approve concrete privacy profile values.
- Approve audit/query persistence schema and retention.
- Approve production Candidate Population resolver sources.
- Approve HTTP/timing/cache/pagination semantics.
- Approve transient versus persisted `CommercialDemand` for F3.
- Approve CUT F3 before any buyer-facing cross-Organization aggregate API.
