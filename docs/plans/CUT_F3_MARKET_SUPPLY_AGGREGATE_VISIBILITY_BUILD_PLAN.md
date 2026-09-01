# CUT F3 - Market Supply Aggregate Visibility Build Plan

Status: PROCEED WITH CHANGES / F3.1-F3.2 APPLICATION CONTRACTS IN PROGRESS / F3.5 NOT RELEASED

Date: 2026-08-28

## 1. Objective

Implement the first buyer-facing cross-Organization aggregate Market Supply surface after ADR-0071.

The first F3 is aggregate-only. It must not expose producer identity, property identity, Animal identifiers, treatments, raw Evidence, Dossier, VerificationBundle, individual Evaluation, individual Decision, export rights or forecast.

## 2. Required Architecture Order

```text
CommercialDemandContext
        |
        v
Canonicalization / MarketSupplyRequestIdentity
        |
        v
Authorization / opt-in grants
        |
        v
CandidatePopulationSnapshot
        |
        v
QueryFingerprint
        |
        v
Historical Query Relationship Assessment
        |
        v
DisclosureDecision
        |
        +--> NOT_RELEASED
        |
        v
AggregateResult
        |
        v
MarketSupplyQueryAuditRecord
        |
        v
UniformPublicResponse
```

Any implementation path that calculates an aggregate before snapshot/disclosure/audit linkage is rejected.

No externally releasable Market Supply result exists without:

- `CandidatePopulationSnapshot`;
- `DisclosureDecision`;
- durable `MarketSupplyQueryAuditRecord`.

Internal temporary calculation is not a public result and cannot be projected externally when durable audit persistence fails.

## 3. Proposed Implementation Cuts

### F3.0 - Production contract/spec closure

Close the remaining concrete production decisions before code:

- audit schema and retention proposal;
- privacy profile values or an explicitly non-production profile;
- production population source/opt-in mechanism;
- permission/capability name;
- HTTP status/cache/timing/retry behavior;
- confirmation that first F3 uses transient `CommercialDemandContext`.

Schema design is allowed in this phase. Generating or applying a migration is blocked until schema, RLS and retention are approved.

Implementation status on 2026-08-29:

- `MarketSupplyRequestIdentity` can build a Core `IdempotencyRequest` with
  buyer Organization, principal reference, purpose, canonical Market Supply
  operation and 32-byte semantic intent digest;
- `MarketSupplyIdempotencyGate` delegates execution to the existing Core
  `IdempotencyService`, preserving replay/conflict behavior without creating a
  Market Supply-specific idempotency store;
- `MarketSupplyPublicAggregateResponse` can produce a stable Core
  `CanonicalPayload` for application-level idempotent replay using only the
  already-filtered public shape;
- `MarketSupplyIdempotentAggregateGateWorkflow` executes the aggregate gate
  through the Market Supply/Core idempotency adapter and validates request
  identity linkage before handler execution;
- `CommercialDemandContext` is implemented as a transient value object that
  contributes buyer Organization, purpose, Policy/version, quantity and
  commercial window to the demand context digest without persistence or
  Aggregate Root lifecycle;
- principal/Organization consistency is delegated to the existing Core
  idempotency contract;
- no HTTP status, retry contract or persistence behavior was invented.

### F3.1 - Privacy Profile + DisclosureDecision

Introduce `DisclosureDecision` as explicit value/result from privacy service and finalize the first privacy profile.

Implementation status on 2026-08-28:

- `DisclosureDecision` is implemented as an immutable application value in the
  privacy boundary, separated from authorization and regulatory
  Evaluation/Decision;
- `MarketSupplyRequestIdentity` is implemented as a semantic idempotency
  identity before population resolution;
- authorization denial audit outcomes now preserve specific internal reasons
  for purpose mismatch and revoked grants while still mapping to uniform public
  non-release;
- no production privacy profile values, endpoint, migration, persistence or
  buyer-facing cross-tenant access were introduced.

Files likely affected:

- `packages/livestock_application/market_supply_privacy.py`
- `tests/livestock_application/test_market_supply_privacy.py`

Acceptance:

- states `ALLOW`, `GENERALIZE`, `SUPPRESS`, `DENY`;
- carries internal reason codes, privacy policy version, query fingerprint, candidate population digest and evaluated_at;
- remains separate from authorization and regulatory Evaluation/Decision;
- can suppress, generalize or exclude authorized contributions due to privacy risk;
- maps to public disposition without leaking internal reason.

### F3.2 - Query Audit + Query Fingerprint persistence

Create `MarketSupplyQueryAuditRecord` and persistence for append-only query audit.

Implementation status on 2026-08-28:

- `MarketSupplyQueryAuditRecord` is implemented as an immutable application
  contract with minimized audit material, digests, temporal coordinates,
  disclosure state and internal/public dispositions;
- `MarketSupplyQueryAuditRepositoryPort` and
  `InMemoryMarketSupplyQueryAuditRepository` are implemented for tests and
  future orchestration;
- append-only behavior, released-result `result_digest` requirement and related
  query lookup are covered by tests;
- a production schema/RLS/retention proposal is documented in
  `docs/plans/CUT_F3_4_MARKET_SUPPLY_QUERY_AUDIT_SCHEMA_PROPOSAL.md`;
- no production database table, migration, RLS policy, transactional repository
  or endpoint was introduced.

Implementation status on 2026-08-31 after schema approval:

- migration `20260831_0078_create_market_supply_query_audit_records.py`
  creates `core_audit.market_supply_query_audit_records`;
- RLS is owner-only by default through `record_owner_organization_id` and
  `titan.organization_id`;
- runtime mutation remains append-only: no UPDATE/DELETE policy is created;
- `TransactionalMarketSupplyQueryAuditRepository` implements append/get/history
  mapping in `livestock_infrastructure`, preserving Core/vertical dependency
  boundaries;
- persistence contract and repository mapping tests are in place;
- PostgreSQL integration verifies owner-only RLS, hidden related history across
  Organizations and no effective UPDATE/DELETE mutation under runtime role;
- no endpoint, HTTP contract, production Candidate Population resolver,
  cross-tenant query or buyer-facing visibility was introduced.

Files likely affected:

- `packages/livestock_application/market_supply_audit.py`
- `packages/core_infrastructure/persistence/...`
- `packages/core_infrastructure/persistence/migrations/versions/...`
- `tests/livestock_application/test_market_supply_audit.py`
- `tests/infrastructure/...`
- `tests/integration/...`

Acceptance:

- stores audit record with buyer/requester, purpose, authorization context digest, Policy/version, privacy profile, population digest, query fingerprint, reference_time, knowledge_cutoff, disclosure decision, reason codes, result digest, requested/evaluated times, revocation state, correlation/idempotency references;
- append-only;
- tenant-safe RLS;
- no sensitive payload storage.
- records queries that never reach aggregation, including `AUTHORIZATION_DENIED`, `PURPOSE_MISMATCH`, `GRANT_REVOKED`, `POPULATION_SUPPRESSED`, `DIFFERENCING_BLOCKED`, `PRIVACY_DENIED`, `GENERALIZED` and `RELEASED`.

HUMAN GATE: schema and retention.

### F3.2B - Semantic differencing/history protection

Implement query relationship assessment over persisted query history before disclosure decision.

Implementation status on 2026-08-28:

- the in-memory audit repository can expose related `AggregationQueryFingerprint`
  history by requester, beneficiary, purpose and Policy context digest;
- the privacy service already consumes previous query fingerprints to detect
  differencing and repeated-query risk;
- the in-memory workflow now loads related fingerprints from the audit
  repository and injects them into the privacy input before disclosure
  assessment;
- no production persistence, semantic similarity policy, retention model or
  Differential Privacy mechanism was introduced.

Files likely affected:

- `packages/livestock_application/market_supply_privacy.py`
- `packages/livestock_application/market_supply_audit.py`
- `packages/livestock_application/market_supply_workflow.py`
- audit repository/query-history adapter
- `tests/livestock_application/test_market_supply_privacy.py`
- `tests/livestock_application/test_market_supply_audit.py`
- `tests/livestock_application/test_market_supply_workflow.py`

Acceptance:

- `DisclosureDecision` can depend on current query plus semantically related previous queries;
- repeated-query window is not the only protection;
- query history supports `QueryHistory -> SemanticSimilarity -> DisclosureRisk`;
- no formal mathematical Differential Privacy is required in F3;
- difference attacks with individually safe queries are suppressed or denied.

### F3.3 - Production Candidate Population resolver boundary

Implement the first resolver that uses only approved opt-in/grant-authorized sources.

Implementation status on 2026-08-29:

- Candidate Population snapshot now exposes an internal universe summary with
  authorized sources digest, selection criteria digest, population digest,
  population size, Organization count, subject count and unknown property count;
- `public_summary()` still omits individual subject identifiers;
- `MarketSupplyAuditRecordContext` can carry a distinct internal
  `population_digest` and the workflow validates it when supplied;
- no production resolver, database lookup, cross-tenant read or opt-in source
  selection was introduced.

Files likely affected:

- `packages/livestock_application/market_supply_population.py`
- `packages/livestock_application/market_readiness.py`
- possible repository ports only after schema/source approval
- tests for tenant isolation and temporal selection

Acceptance:

- no global Animal lookup;
- reference_time and knowledge_cutoff mandatory;
- source/criteria/population digests produced;
- inaccessible/unknown/excluded tracked internally;
- public summaries omit IDs.

HUMAN GATE: source of opt-in/grants if existing contracts are insufficient.

### F3.4 - Aggregate service composition

Compose authorization, population, disclosure, aggregation, audit and public response.

Implementation status on 2026-08-31:

- the in-memory workflow can optionally receive `MarketSupplyAuditRecordContext`
  and a `MarketSupplyQueryAuditRepositoryPort`;
- when supplied, it builds and appends `MarketSupplyQueryAuditRecord` before
  mapping the public response;
- it validates snapshot, query fingerprint and audit population digest linkage;
- it refuses audit context without an audit repository;
- it rechecks authorization at release time and converts a grant revoked between
  admission and release into uniform `NOT_RELEASED` with internal
  `REVOKED_OBSERVED` audit state;
- durable audit persistence now exists for the approved
  `core_audit.market_supply_query_audit_records` table and is verified under
  owner-only PostgreSQL RLS;
- integration coverage proves the workflow can produce an internally releasable
  aggregate only after a durable audit append through the transactional
  repository;
- no endpoint, contract HTTP, query cross-tenant, production population resolver
  or buyer-facing release was introduced.

Files likely affected:

- `packages/livestock_application/market_supply_workflow.py`
- `packages/livestock_application/market_supply.py`
- `packages/livestock_application/market_supply_response.py`
- new application service module only if existing modules become too crowded

Acceptance:

- authorization precedes population;
- population snapshot precedes disclosure;
- disclosure precedes aggregate;
- audit exists for all outcomes;
- no externally releasable result without snapshot/disclosure/durable audit;
- when an audit repository is configured, a released aggregate requires an
  audit record context and successful audit append before public projection;
- internally releasable `MarketSupplyAggregateResult` may be materialized only
  after Candidate Population snapshot, `DisclosureDecision` and audit record
  are linked and consistent;
- revocation is checked at workflow admission and rechecked before release;
- `NOT_RELEASED` uniform externally.

### F3.5 - API endpoint

Expose the first endpoint only after F3.1-F3.4 pass and a HUMAN RELEASE GATE approves the public surface.

Release gate package:

- `docs/plans/CUT_F3_5_MARKET_SUPPLY_RELEASE_GATE_PACKAGE.md`

Implementation status on 2026-08-31:

- proposed route, headers, public payload shapes, cache posture, no-pagination
  constraint, feature flag and permission name are documented for review;
- remaining policy gates are isolated: HTTP/public behavior,
  production Candidate Population source and production privacy profile values;
- `tests/api/test_core_public_surface.py` now explicitly fails if the proposed
  Market Supply aggregate route appears before the F3.5 release gate is
  accepted;
- no route, endpoint, permission seed, migration, production resolver,
  cross-tenant query or buyer-facing release was introduced.

Implementation status on 2026-09-01 after permission approval:

- `MARKET_SUPPLY.AGGREGATE_ASSESS` is catalogued in
  `packages/livestock_application/authorization.py`;
- the permission is included in `LIVESTOCK_PERMISSIONS` for seed/catalog
  creation;
- no default role receives the permission automatically;
- no route, endpoint, migration, production resolver, cross-tenant query or
  buyer-facing release was introduced.

Implementation status on 2026-09-01 after HTTP behavior approval:

- `MarketSupplyPublicResponseMapper` exposes immutable no-store headers for the
  future F3.5 route;
- response payload shape remains the existing `RELEASED`/`NOT_RELEASED`
  application contract;
- no route, endpoint, migration, production resolver, cross-tenant query or
  buyer-facing release was introduced.

Implementation status on 2026-09-01 after privacy profile loader:

- `AggregationPrivacyProfile` can be loaded only from explicit configuration;
- absent or invalid profile configuration fails closed;
- no production threshold values are embedded in code;
- no route, endpoint, migration, production resolver, cross-tenant query or
  buyer-facing release was introduced.

Implementation status on 2026-09-01 after Candidate Population source contract:

- `AuthorizedCandidatePopulationResolver` can compose owner-scoped
  contributions only when backed by valid Market Supply aggregate grants;
- rejected contributions preserve internal reason/count without producing
  snapshots;
- no database adapter, Animal lookup, endpoint, migration, cross-tenant query or
  buyer-facing release was introduced.

Proposed route:

```text
POST /v1/livestock/market-supply/aggregate-assessments
```

Files likely affected:

- `apps/api/...`
- API tests;
- OpenAPI/public schema tests if present;
- validation script in `apps/validacao`.

Acceptance:

- idempotency key required;
- Organization header is buyer/requester;
- permission/capability checked;
- no protected membership leakage in response;
- status/cache/timing behavior follows approved decision.

HUMAN GATE: HTTP status/cache/timing and permission name.

Release gate:

```text
F3.1
F3.2
F3.2B
F3.3
F3.4
  |
  v
HUMAN RELEASE GATE
  |
  v
F3.5
```

## 4. Test Matrix

Required:

- allow release with aggregate only;
- generalize release when precision must be reduced;
- suppress on small cohort;
- deny on missing/invalid/revoked grant;
- deny on purpose mismatch;
- suppress/deny on semantic differencing;
- same idempotency key + same digest returns same result;
- same idempotency key + different digest conflicts;
- T0/T1/T2 knowledge cutoff;
- Organization isolation;
- audit append-only;
- no IDs in public response;
- uniform non-release response for nonexistent/invisible/excluded/denied/suppressed.
- same HTTP behavior, response schema, cache policy, pagination behavior and retry semantics for protected non-release cases;
- no materially distinguishable latency class that enables reliable inference of membership or internal reason;
- grant valid at admission, revoked before disclosure, returns `NOT_RELEASED` and audit records revocation observed.
- audit append failure blocks public response mapping for releasable aggregate
  outcomes.
- auditable workflow requires audit context for all outcomes, including
  authorization-denied `NOT_RELEASED` queries that never resolve a Candidate
  Population snapshot.

## 5. Migrations

Expected: yes, for audit/query persistence.

Schema proposal, indexes, unique constraints, foreign keys, RLS model, retention proposal and expected query patterns may be prepared for review.

No migration should be generated or applied until schema, RLS and retention are approved.

## 6. Security Review Points

- aggregation privacy values;
- contribution concentration risk;
- geographic uniqueness;
- query similarity/differencing;
- public response timing/cache;
- audit payload minimization;
- revocation state;
- telemetry/log redaction.

## 7. Rollback

- feature flag/route disablement for endpoint;
- preserve audit records already written;
- no rewrite of historical reports or decisions;
- feature disablement must not disable audit/history read capability;
- migrations require normal downgrade path only if safe for non-production.

## 8. Build Prerequisites

Before BUILD starts, Product/Security must approve:

- audit schema and retention;
- privacy profile initial values;
- production population source/opt-in mechanism;
- permission/capability name;
- HTTP status/cache/timing behavior;
- whether first F3 accepts only transient `CommercialDemandContext`.

## 9. Non-Goals

- no detailed candidate disclosure;
- no individual data response;
- no forecast;
- no persistent CommercialDemand;
- no SupplyIntelligenceReport persistence;
- no official source integration;
- no Dossier/VerificationBundle change.
