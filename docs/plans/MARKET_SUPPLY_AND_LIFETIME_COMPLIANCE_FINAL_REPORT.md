# Market Supply and Lifetime Compliance Final Report

Date: 2026-08-28

## Files Altered

Code:

- `packages/livestock_application/sanitary_test_coverage.py`
- `packages/livestock_application/market_readiness.py`
- `packages/livestock_application/market_supply.py`
- `packages/livestock_application/market_supply_authorization.py`
- `packages/livestock_application/market_supply_privacy.py`
- `packages/livestock_application/market_supply_audit.py`
- `packages/livestock_application/market_supply_response.py`
- `packages/livestock_application/market_supply_workflow.py`
- `packages/livestock_application/market_supply_population.py`
- `packages/livestock_application/market_supply_request.py`
- `apps/validacao/market_supply_synthetic.py`

Tests:

- `tests/livestock_application/test_sanitary_test_coverage.py`
- `tests/livestock_application/test_dimensional_coverage.py`
- `tests/livestock_application/test_market_readiness.py`
- `tests/livestock_application/test_market_supply.py`
- `tests/livestock_application/test_market_supply_authorization.py`
- `tests/livestock_application/test_market_supply_privacy.py`
- `tests/livestock_application/test_market_supply_audit.py`
- `tests/livestock_application/test_market_supply_response.py`
- `tests/livestock_application/test_market_supply_workflow.py`
- `tests/livestock_application/test_market_supply_population.py`
- `tests/livestock_application/test_market_supply_request.py`
- `tests/unit/test_market_supply_synthetic.py`

Documentation:

- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`
- `docs/plans/CUT_A_EXECUTION_REPORT.md`
- `docs/plans/CUT_C_EXECUTION_REPORT.md`
- `docs/plans/CUT_F0_EXECUTION_REPORT.md`
- `docs/plans/CUT_F1_EXECUTION_REPORT.md`
- `docs/plans/CUT_F2_EXECUTION_REPORT.md`
- `docs/plans/CUT_F2B_AGGREGATION_PRIVACY_EXECUTION_REPORT.md`
- `docs/plans/CUT_F2C_MARKET_SUPPLY_AUDIT_ENVELOPE_EXECUTION_REPORT.md`
- `docs/plans/CUT_F2D_MARKET_SUPPLY_UNIFORM_RESPONSE_EXECUTION_REPORT.md`
- `docs/plans/CUT_F2E_MARKET_SUPPLY_REVOCATION_SEMANTICS_EXECUTION_REPORT.md`
- `docs/plans/CUT_F2F_MARKET_SUPPLY_GATE_WORKFLOW_EXECUTION_REPORT.md`
- `docs/plans/CUT_F2G_CANDIDATE_POPULATION_SNAPSHOT_EXECUTION_REPORT.md`
- `docs/plans/CUT_F2H_POPULATION_GATE_COMPOSITION_EXECUTION_REPORT.md`
- `docs/plans/CUT_F2I_PRODUCTION_GATE_DESIGN_CLOSURE_REPORT.md`
- `docs/plans/CUT_F3_1_DISCLOSURE_DECISION_AND_REQUEST_IDENTITY_EXECUTION_REPORT.md`
- `docs/plans/CUT_F3_2_QUERY_AUDIT_APPLICATION_CONTRACT_REPORT.md`
- `docs/specs/approved/2026-08-28-market-supply-production-gate-closure.md`
- `docs/adr/0071-market-supply-production-gates-before-cross-tenant-aggregate-api.md`
- `docs/specs/approved/2026-08-28-market-supply-f3-cross-organization-aggregate-visibility.md`
- `docs/plans/CUT_F3_MARKET_SUPPLY_AGGREGATE_VISIBILITY_BUILD_PLAN.md`
- `docs/specs/approved/MARKET_SUPPLY_INTELLIGENCE_SPEC.md`
- `docs/specs/approved/PROGRESSIVE_DISCLOSURE_SPEC.md`
- `docs/plans/MARKET_SUPPLY_INTELLIGENCE_DESIGN_PACKAGE.md`
- `docs/plans/PROGRESSIVE_DISCLOSURE_DATA_SHARING_DESIGN_PACKAGE.md`
- `docs/plans/PROGRESSIVE_DISCLOSURE_THREAT_MODEL.md`
- `docs/plans/FIRST_MARKET_SUPPLY_VERTICAL_SLICE_PROPOSAL.md`
- `docs/adr/0069-market-supply-intelligence-analises-nao-regulatorias.md`
- `docs/adr/0070-progressive-disclosure-e-visibilidade-agregada.md`
- `TITAN_MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_EXECUTION_REPORT.md`

## Code Changed

- CUT A: half-open upper boundary for `SANITARY_TEST_A_v1` treatment selection.
- CUT C: deterministic divergent Decision/Evaluation fallback in MarketReadiness population reader.
- CUT F0: synthetic in-memory validation script and static mock for Market Supply report vocabulary.
- CUT F1: producer-side single-Organization aggregation over existing `MarketReadinessReport`.
- CUT F2: purpose-bound Market Supply authorization guard over existing `AuthorizationGrant`.
- CUT F2B: in-memory aggregation privacy assessment runtime with explicit policy input and query fingerprints.
- CUT F2C: in-memory audit-envelope planner composing authorization and privacy outcomes.
- CUT F2D: application-level uniform public response mapper for aggregate release.
- CUT F2E: revocation effective-time hardening in Market Supply authorization.
- CUT F2F: in-memory workflow composing authorization, privacy, audit and public response gates.
- CUT F2G: in-memory CandidatePopulation criteria/resolver/snapshot with canonical digests.
- CUT F2H: optional CandidatePopulation snapshot binding inside the aggregate gate workflow.
- CUT F2I: design-only production gate closure accepted with changes for privacy, audit, idempotency, resolver, HTTP behavior, `DisclosureDecision`, temporal invariants, semantic differencing and CommercialDemand first-use semantics.
- CUT F3.1: internal implementation started with semantic `MarketSupplyRequestIdentity`,
  explicit `DisclosureDecision` and more specific internal authorization-denial
  audit outcomes. No endpoint, migration, persistence or buyer-facing
  cross-Organization visibility was introduced.
- CUT F3.2: internal application audit contract started with immutable
  `MarketSupplyQueryAuditRecord`, append-only in-memory repository, canonical
  record digest and schema/RLS/retention proposal. No production persistence,
  migration, endpoint or buyer-facing visibility was introduced.
- CUT F3 request context: transient `CommercialDemandContext` implemented as a
  value object for buyer Organization, purpose, Policy/version, quantity and
  commercial window. No CommercialDemand Aggregate Root or persistence was
  introduced.
- CUT F3 idempotency gate: `MarketSupplyIdempotencyGate` delegates Market Supply
  semantic request execution to the existing Core `IdempotencyService`; no
  Market Supply-specific idempotency store or external retry contract was
  introduced.
- CUT F3 canonical response: `MarketSupplyPublicAggregateResponse` now produces
  a stable Core `CanonicalPayload` for application-level idempotent replay
  without adding HTTP, cache, pagination or retry semantics.
- CUT F3 idempotent workflow composition:
  `MarketSupplyIdempotentAggregateGateWorkflow` executes aggregate assessment
  through the Core idempotency path and validates identity/request linkage
  before handler execution.

## Tests Added

- Treatment at `required_until` is excluded from direct coverage path.
- Treatment at `required_until` is excluded from classified material path.
- Treatment at `required_until` is excluded from dimensional contribution path.
- Divergent Evaluation is surfaced as `REASSESSMENT_REQUIRED` instead of hidden by orphan Decision.
- Synthetic report shape preserves non-regulatory, non-identifying constraints.
- Producer-side aggregation counts readiness statuses and gaps without buyer visibility.
- Aggregate authorization denies missing/inactive/mismatched grants and separates aggregate from candidate disclosure.
- Aggregation privacy suppresses small cohorts, high geographic precision, rare attributes, excessive filters, differencing risk and repeated-query risk.
- Market Supply audit envelope preserves internal denial/suppression reasons while keeping denied/suppressed external disposition uniform.
- Public aggregate response maps authorization denial and privacy suppression to the same `NOT_RELEASED` shape.
- Authorization now denies stale active grants when `revoked_at <= requested_at`.
- Aggregate gate workflow fixes ordering so authorization runs before privacy and public response derives from the audit envelope.
- CandidatePopulation snapshot records included/excluded counts, exclusion reasons and digests without exposing IDs in public summary.
- Aggregate gate workflow validates supplied CandidatePopulation snapshot Organization, Policy, purpose, digest and included count against authorization and privacy/audit fingerprint inputs.
- Market Supply request identity binds idempotency key to buyer Organization,
  purpose, Policy/version, demand digest, candidate criteria digest,
  `reference_time` and `knowledge_cutoff`.
- Market Supply request identity can build a Core `IdempotencyRequest` with the
  canonical operation and 32-byte semantic intent digest.
- Transient `CommercialDemandContext` produces a canonical demand context digest
  and composes into `MarketSupplyRequestIdentity` without lifecycle or storage.
- Market Supply idempotency adapter replays equivalent semantic requests and
  raises Core `IdempotencyConflict` for a reused key with divergent digest.
- Public Market Supply responses produce stable canonical bytes while
  `NOT_RELEASED` omits aggregate payload and internal reasons.
- Idempotent aggregate workflow replay returns stored canonical bytes without
  reexecuting the workflow or duplicating audit; divergent semantic digest with
  the same key raises Core `IdempotencyConflict`.
- Disclosure decision is an explicit immutable value separate from authorization
  and regulatory Evaluation/Decision.
- Authorization-denied audit planning preserves internal `PURPOSE_MISMATCH` and
  `GRANT_REVOKED` outcomes while keeping the external disposition uniform.
- Market Supply query audit record links audit envelope, `DisclosureDecision`,
  Candidate Population digest, idempotency reference, semantic request digest,
  correlation id and temporal coordinates before future durable persistence.
- F3.4 auditable release hardening rejects release without audit context when an
  audit repository is configured and blocks public response mapping when audit
  append fails.
- F3.4 aggregate result linkage materializes `MarketSupplyAggregateResult` only
  when Candidate Population snapshot, `DisclosureDecision`, audit record, query
  fingerprint and result digest are consistent.
- F3.4 auditable non-release hardening requires audit context for every
  auditable outcome and records authorization-denied pre-population queries
  without fabricating a Candidate Population snapshot or population digest.
- F3.4 query audit persistence adds the approved
  `core_audit.market_supply_query_audit_records` migration and transactional
  Livestock infrastructure repository without creating any public API.
- F3.4 PostgreSQL/RLS verification proves owner-only visibility and append-only
  behavior for the Market Supply audit table under a runtime role without
  `BYPASSRLS`.
- F3.4 workflow/PostgreSQL integration verifies that an internally releasable
  Market Supply aggregate is materialized only after durable audit append via the
  transactional repository and remains invisible to the buyer Organization under
  owner-only RLS.
- F3.5 release gate package documents the future endpoint proposal, public
  response shapes, no-store/no-pagination posture, feature flag, permission
  proposal and remaining policy gates without creating any public route.
- F3.5A adds an API public-surface guard that fails if the proposed Market
  Supply aggregate endpoint appears before the release gate is accepted.
- Independent audit F-02 is addressed by migration 20260831_0079, which enables
  and forces RLS on six protected `core_audit` tables. `authorization_grants`
  now supports bilateral SELECT for owner/beneficiary, owner-only INSERT/UPDATE
  and no runtime DELETE policy.

## Tests Executed

Passed:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
python -m uv run --locked python -m pytest tests/unit/test_market_supply_synthetic.py tests/livestock_application/test_market_supply.py tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/livestock_application/test_market_supply_population.py
python -m uv run --locked python -m pytest
python -m uv run --locked python -m ruff check packages/livestock_application/sanitary_test_coverage.py packages/livestock_application/market_readiness.py tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
python -m uv run --locked python -m ruff check packages/livestock_application/market_supply.py packages/livestock_application/market_supply_authorization.py packages/livestock_application/market_supply_privacy.py packages/livestock_application/market_supply_audit.py packages/livestock_application/market_supply_response.py packages/livestock_application/market_supply_workflow.py packages/livestock_application/market_supply_population.py apps/validacao/market_supply_synthetic.py tests/unit/test_market_supply_synthetic.py tests/livestock_application/test_market_supply.py tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/livestock_application/test_market_supply_population.py
python -m uv run --locked python -m ruff format --check packages/livestock_application/sanitary_test_coverage.py packages/livestock_application/market_readiness.py tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
python -m uv run --locked python -m ruff format --check packages/livestock_application/market_supply.py packages/livestock_application/market_supply_authorization.py packages/livestock_application/market_supply_privacy.py packages/livestock_application/market_supply_audit.py packages/livestock_application/market_supply_response.py packages/livestock_application/market_supply_workflow.py packages/livestock_application/market_supply_population.py apps/validacao/market_supply_synthetic.py tests/unit/test_market_supply_synthetic.py tests/livestock_application/test_market_supply.py tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/livestock_application/test_market_supply_population.py
python -m uv run --locked python -m mypy packages/livestock_application/market_supply.py packages/livestock_application/market_supply_authorization.py packages/livestock_application/market_supply_privacy.py packages/livestock_application/market_supply_audit.py packages/livestock_application/market_supply_response.py packages/livestock_application/market_supply_workflow.py packages/livestock_application/market_supply_population.py apps/validacao/market_supply_synthetic.py tests/unit/test_market_supply_synthetic.py tests/livestock_application/test_market_supply.py tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/livestock_application/test_market_supply_population.py
```

Latest focused Market Supply F0-F3.4 internal result: 93 passed.

Latest full pytest result with `TITAN_DATABASE_URL` active after PostgreSQL/RLS
verification and realistic policy-sharing test cleanup: 1560 passed, 1 skipped.

Latest full pytest result after F3.5A disabled-route release guard:
1562 passed, 1 skipped.

Latest focused F-02 hardening result:

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m pytest tests/infrastructure/test_core_audit_tenant_rls_hardening_contract.py tests/integration/test_core_audit_tenant_rls_hardening_postgresql.py tests/integration/test_policy_sharing_api.py tests/integration/test_policy_sharing_api_realistic.py tests/integration/test_policy_sharing_realistic_v2.py
```

Result: 24 passed.

Latest full pytest result after F-02 hardening:
1565 passed, 1 skipped.

Latest focused F-01 semantic differencing result:

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_workflow.py tests/infrastructure/test_market_supply_query_audit_repository.py tests/integration/test_market_supply_query_audit_postgresql.py tests/integration/test_market_supply_workflow_postgresql.py
```

Result: 59 passed.

Latest full pytest result after F-01 semantic differencing fix:
1567 passed, 1 skipped.

Latest focused F-03 revocation/idempotency result:

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_request.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/infrastructure/test_market_supply_query_audit_repository.py tests/integration/test_market_supply_query_audit_postgresql.py tests/integration/test_market_supply_workflow_postgresql.py
```

Result: 76 passed.

Latest focused F-04 durable-audit release result:

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_request.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/infrastructure/test_market_supply_query_audit_repository.py tests/integration/test_market_supply_query_audit_postgresql.py tests/integration/test_market_supply_workflow_postgresql.py
```

Result: 77 passed.

Latest focused F-05 fresh-grant revocation recheck result:

```text
Remove-Item Env:TITAN_DATABASE_URL -ErrorAction SilentlyContinue
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_workflow.py tests/livestock_application/test_market_supply_request.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_population.py tests/integration/test_market_supply_workflow_postgresql.py
```

Result: 67 passed, 1 skipped. The PostgreSQL integration was skipped because the
local Docker/PostgreSQL runtime was unavailable during this verification window.

Latest focused F-06 snapshot-derived privacy counts result:

```text
Remove-Item Env:TITAN_DATABASE_URL -ErrorAction SilentlyContinue
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_request.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/infrastructure/test_market_supply_query_audit_repository.py tests/integration/test_market_supply_workflow_postgresql.py
```

Result: 79 passed, 1 skipped. The PostgreSQL integration was skipped because the
local Docker/PostgreSQL runtime was unavailable during this verification window.

Latest focused F-07 audit/population temporal binding result:

```text
Remove-Item Env:TITAN_DATABASE_URL -ErrorAction SilentlyContinue
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_request.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/infrastructure/test_market_supply_query_audit_repository.py tests/integration/test_market_supply_workflow_postgresql.py
```

Result: 81 passed, 1 skipped. The PostgreSQL integration was skipped because the
local Docker/PostgreSQL runtime was unavailable during this verification window.

Latest focused F-08 public aggregate payload allow-list result:

```text
Remove-Item Env:TITAN_DATABASE_URL -ErrorAction SilentlyContinue
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py -q
```

Result: 41 passed.

Latest focused F-09 audit-owner validation result:

```text
Remove-Item Env:TITAN_DATABASE_URL -ErrorAction SilentlyContinue
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py -q
```

Result: 42 passed.

Latest focused F-10 integration database gate result:

```text
Remove-Item Env:TITAN_DATABASE_URL -ErrorAction SilentlyContinue
$env:TITAN_REQUIRE_INTEGRATION_DB='1'
python -m uv run --locked python -m pytest tests/integration/test_market_supply_workflow_postgresql.py --collect-only -q
```

Result: failed during collection with the expected configuration error:
`TITAN_REQUIRE_INTEGRATION_DB=1 exige TITAN_DATABASE_URL configurada.`

```text
Remove-Item Env:TITAN_REQUIRE_INTEGRATION_DB -ErrorAction SilentlyContinue
Remove-Item Env:TITAN_DATABASE_URL -ErrorAction SilentlyContinue
python -m uv run --locked python -m pytest tests/integration/test_market_supply_workflow_postgresql.py -q
```

Result: 1 skipped.

Latest focused F-11 revocation reason preservation result:

```text
python -m uv run --locked python -m pytest tests/infrastructure/test_authorization_grant_repository.py tests/livestock_application/test_market_supply_workflow.py -q
```

Result: 32 passed.

Latest focused F-12 divergent MarketReadiness tie-break result:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_market_readiness.py -q
```

Result: 11 passed.

Latest focused F-13 half-open treatment boundary reconciliation result:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_coverage_contribution_service.py -q
```

Result: 16 passed.

Latest focused F3.4 persistence/workflow integration result:

```text
$env:TITAN_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m pytest tests/integration/test_market_supply_workflow_postgresql.py tests/integration/test_market_supply_query_audit_postgresql.py tests/infrastructure/test_market_supply_query_audit_repository.py tests/infrastructure/test_market_supply_query_audit_persistence_contract.py
```

Result: 8 passed.

Latest F3.5 release-gate package:

- `docs/plans/CUT_F3_5_MARKET_SUPPLY_RELEASE_GATE_PACKAGE.md`

Global quality gates after audit F-08 through F-13 cleanup:

- `TITAN_DATABASE_URL` and `TITAN_REQUIRE_INTEGRATION_DB=1`
  `python -m uv run --locked python -m pytest -q` passed with
  `1585 passed, 1 skipped, 4 warnings`.
- `python -m uv run --locked python -m ruff check .` passed.
- `python -m uv run --locked python -m ruff format --check .` passed.
- `python -m uv run --locked python -m mypy` passed.
- `python -m uv run --locked python -m alembic check` passed with
  `No new upgrade operations detected`.

Earlier global quality gates after BuyerPolicy cleanup:

- `python -m uv run --locked python -m ruff check .` passed.
- `python -m uv run --locked python -m ruff format --check .` passed.
- `python -m uv run --locked python -m mypy` passed.

Alembic metadata check passed with the local migration URL:

```text
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m alembic check
```

Result: `No new upgrade operations detected.` The run emitted the repository's known PostGIS `geometry` type warning for `property_geometries.geom`.

## Migrations

- `packages/core_infrastructure/persistence/migrations/versions/20260831_0078_create_market_supply_query_audit_records.py`
- `packages/core_infrastructure/persistence/migrations/versions/20260831_0079_harden_core_audit_tenant_rls.py`

## Security Impact

No new external access, API, grant, consent model, official integration or cross-tenant query was implemented. ADR-0070 now accepts the architecture baseline. CUT F2B adds an in-memory suppression assessment for future aggregate release. Audit F-01 is addressed by separating stable semantic policy context from material Candidate Population snapshot identity, making repeated-query and differencing history reachable without weakening snapshot/audit linkage. Audit F-02 is addressed by forced RLS on protected `core_audit` tenant tables. Audit F-03 is addressed in the Market Supply idempotent workflow by checking revocation before canonical replay and producing a fresh `NOT_RELEASED` audited outcome when a grant was revoked. Audit F-04 is addressed by refusing any releasable aggregate response without a persisted `MarketSupplyQueryAuditRecord`. Audit F-05 is addressed in the application workflow by requiring a `MarketSupplyAuthorizationGrantReaderPort` for auditable grant-backed release and using the freshly read grant for pre-release and replay revocation checks. Audit F-06 is addressed by deriving known privacy cohort counts from `CandidatePopulationSnapshot` and rejecting caller-supplied count divergence. Audit F-07 is addressed by binding audit `reference_time` and `knowledge_cutoff` to the resolved population criteria. Concrete production privacy profiles and external behavior remain gated.
Audit F-08 is addressed by introducing an explicit allow-listed public aggregate payload projection before release audit creation; released payloads now reject unapproved keys, identifier-like membership fields, negative counts and unapproved nested shapes, and audit `result_digest` is computed over the sanitized public projection.
Audit F-09 is partially addressed at the application boundary by requiring
`MarketSupplyAggregateGateRequest.audit_owner_organization_id` to equal
`authorization_request.owner_organization_id`. The remaining F-09 question is a
real policy/release-gate decision: how a future buyer-facing F3.5 endpoint should
read related audit history for differencing under RLS without broadening protected
audit visibility silently.
Audit F-10 is addressed as a verification-process control: integration tests can
still be skipped for local no-Docker runs, but `TITAN_REQUIRE_INTEGRATION_DB=1`
now converts a missing `TITAN_DATABASE_URL` into an explicit pytest usage error,
and `CLAUDE.md` no longer documents a nonexistent database fallback.
Audit F-11 is addressed by preserving `revocation_reason` in
`TransactionalAuthorizationGrantRepository.revoke(...)`; no grant lifecycle or
authorization semantics changed.
Audit F-12 is addressed by replacing UUID-string ordering for divergent
Decision/Evaluation candidates with a domain temporal criterion (`issued_at`) and
failing closed on same-instant divergent ambiguity. `REASSESSMENT_REQUIRED`
entries now retain Decision/Evaluation identifiers for traceability.
Audit F-13 required no additional code in this pass: CUT A already changed
`SANITARY_TEST_A_v1` material selection to the half-open interval
`[required_from, reference_time)`, and the focused coverage tests confirm the
boundary.

The remaining F-09 policy question is now captured as proposed ADR-0072:
`docs/adr/0072-market-supply-audit-history-visibility-for-differencing.md`.
The recommendation is to keep raw `MarketSupplyQueryAuditRecord` rows owner-only
by RLS and perform semantic differencing through application-mediated
owner/contributor-scoped contexts, returning only uniform public projections to
the buyer. The F3.5 release gate package now depends on this ADR before any
buyer-facing endpoint can be released.

## Tenant Isolation Impact

No tenant boundary changed. MarketReadiness remains Organization-scoped. Producer-side analysis is single-Organization. Authorization and privacy modules do not perform data access. Progressive disclosure is accepted as architecture baseline only; no cross-tenant API exists. `authorization_grants` now has database-enforced bilateral read and owner-only write semantics, while other hardened `core_audit` tables remain owner-only.

## Temporal Semantics Impact

CUT A strengthens interval correctness. CUT C keeps context mismatch visible. CUT F2 checks authorization validity windows. CUT F2B requires UTC query fingerprints and explicit repeated-query windows. CUT F2C requires UTC audit `recorded_at`. Audit F-01 preserves `reference_time` and `knowledge_cutoff` inside the stable policy context digest used for query-history correlation. Audit F-03 uses the reexecution `requested_at` as the pre-replay revocation check coordinate. Audit F-05 uses the workflow `recorded_at` coordinate for the fresh pre-release authorization check. Audit F-07 prevents audit records from declaring temporal coordinates different from the resolved Candidate Population criteria. No historical Evaluation, Decision, Dossier or VerificationBundle was rewritten.

## HUMAN GATES Remaining

- Approve concrete persistence/API contracts before production code.
- Approve concrete `CandidatePopulationSnapshot` digest representation.
- Approve concrete production `AggregationPrivacyPolicy` profile values.
- Approve query audit persistence, retention, rate limits and operational differencing controls.
- Approve whether persistent Market Supply audit reuses/extends `shared_policy_access_log` or receives a dedicated model.
- Approve public HTTP, timing, cache and pagination semantics for uniform non-release.
- Approve producer opt-in/revocation UX and authority model.
- Approve concrete FieldScope/GrantScope profiles.
- Approve `SupplyIntelligenceReport` storage/hash/export behavior.
- Approve concrete schema/profile/source decisions before F3.2/F3.3 production
  persistence or resolver implementation.
- Approve Market Supply audit-history visibility for F3.5 differencing under RLS
  (recommended: accept ADR-0072 alternative B, owner-only raw audit plus
  application-mediated owner/contributor-scoped differencing).
- Approve the HUMAN RELEASE GATE before F3.5 creates any buyer-facing cross-Organization aggregate visibility.

## Product Owner Decisions Needed

The Product Owner decided ownership and boundaries for CommercialDemand, MarketReadiness, SupplyForecast, Candidate Population principles, GapAnalysis derivation, progressive disclosure, revocation, SupplyIntelligenceReport separation and official source non-authorization. ADR-0069 and ADR-0070 are accepted.

Remaining approval is needed for production contracts that create durable audit
  persistence, production contribution sources, public API behavior or
  buyer-facing cross-Organization visibility. Internal reversible F3.1/F3.2
  code has started under the accepted ADR/SPEC boundaries.
