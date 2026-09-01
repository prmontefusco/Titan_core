# First Market Supply Vertical Slice Proposal

Status: CUT F0, F1, F2, F2B, F2C, F2D, F2E, F2F, F2G AND F2H IMPLEMENTED WITH LIMITED SCOPE; CUT F2I ACCEPTED WITH CHANGES AS PRODUCTION GATE DESIGN CLOSURE / BUYER-FACING F3 REQUIRES BUILD SPEC

Date: 2026-08-28

## Objective

Define the smallest safe future implementation path after ADR-0069 and ADR-0070 acceptance. CUT F0 has been implemented as a synthetic/in-memory validation artifact. CUT F1 has been implemented as an internal single-Organization producer-side aggregation over existing MarketReadiness. CUT F2 has been implemented as preparation-only purpose/scope authorization guards over existing `AuthorizationGrant` shape. CUT F2B has been implemented as an in-memory aggregation privacy assessment runtime without production profile, persistence or API. CUT F2C has been implemented as an in-memory audit-envelope planner without persistence or public response contract. CUT F2D has been implemented as an application-level uniform public response mapper without API or HTTP semantics. CUT F2E has been implemented as revocation-time hardening in the authorization guard. CUT F2F has been implemented as in-memory aggregate gate orchestration. CUT F2G has been implemented as an in-memory CandidatePopulation criteria/resolver/snapshot model with canonical digests. CUT F2H has been implemented as optional CandidatePopulation snapshot binding inside the aggregate gate workflow. CUT F2I accepted the production gate closure for privacy, audit, idempotency, resolver, HTTP behavior, `DisclosureDecision`, temporal invariants, semantic differencing and CommercialDemand first-use semantics. This document does not itself implement buyer-facing BUILD, persistence, API, migration, UI, cross-tenant access, grant creation workflow, forecast engine or report persistence.

## Approved Boundary

The first commercial line must preserve:

- Commercial intent is not Policy.
- Projection is not Decision.
- Readiness is derived, not animal state.
- Missing information is not negative evidence.
- Aggregate-first, identity-last.
- Authorization precedes population resolution and disclosure.
- Organization isolation is the default.
- Revocation stops new access but does not rewrite history.
- SupplyIntelligenceReport is analytical, not regulatory.

## Preferred Future Flow

```text
Buyer/frigorifico creates or provides CommercialDemand context
        |
        v
Authorized producer participation
        |
        v
CandidatePopulationCriteria
        |
        v
PopulationResolver
        |
        v
CandidatePopulationSnapshot / resolved context
        |
        +--> MarketReadiness aggregate
        |
        +--> GapAnalysis aggregate
        |
        +--> optional deterministic SupplyForecast
                    |
                    v
            SupplyDemandAnalysis
                    |
                    v
            SupplyIntelligenceReport
```

The buyer-facing first result should expose only aggregate, authorization-safe fields:

- total authorized population considered;
- `READY`;
- `CONDITIONED`;
- `INDETERMINATE`;
- `NOT_READY`;
- `NOT_EVALUATED`;
- high-level gaps;
- current capacity;
- potential capacity in window, only if forecast is included;
- estimated shortage;
- limitations;
- generated_at/reference_time/knowledge_cutoff;
- Policy/version.

It should not expose producer names, properties, Animal IDs, treatments, Evidence, Dossiers, individual Evaluations or individual Decisions.

## Recommended CUT F Decomposition

### CUT F0 - Synthetic/In-Memory Analytical Prototype

Goal: validate vocabulary, counts, gap categories, report shape and buyer/producer comprehension using synthetic in-memory data only.

Business value: cheapest learning loop without authorization, tenant, privacy or persistence risk.

Status: implemented as `apps/validacao/market_supply_synthetic.py`, `docs/product/MARKET_SUPPLY_SYNTHETIC_REPORT_MOCK.md` and `docs/plans/CUT_F0_EXECUTION_REPORT.md`.

Domain concepts touched: none in production code; mock names mirror `CommercialDemand`, Candidate Population, `MarketReadiness`, `GapAnalysis`, optional `SupplyForecast`, `SupplyDemandAnalysis`, `SupplyIntelligenceReport`.

Persistence impact: none.

API impact: none.

Tenant/cross-tenant impact: none.

Authorization impact: none; all data synthetic.

Privacy/security risks: low; must avoid real producer data.

Temporal semantics: mock must include generated_at, reference_time and knowledge_cutoff so reviewers evaluate the language early.

Tests required: document/static artifact review, schema-like fixture checks if scripted.

Explicit non-goals: no production package, no migration, no endpoint, no real grants, no real forecast.

Rollback/containment: delete prototype artifacts.

### CUT F1 - Single-Organization Producer-Side Market Supply Analysis

Goal: produce aggregate readiness/gap analysis for one producer Organization over its own animals.

Business value: producer sees capacity and gaps before sharing anything externally.

Status: implemented as `packages/livestock_application/market_supply.py` without API, persistence, migration, forecast or buyer visibility.

Domain concepts touched: `MarketReadiness`, existing Evaluation/Decision/Policy outputs, GapAnalysis composition.

Persistence impact: preferably none for first cut; if a report is saved, require explicit SPEC for immutable `SupplyIntelligenceReport`.

API impact: producer-side endpoint or validation script only if approved.

Tenant/cross-tenant impact: no cross-tenant access.

Authorization impact: normal same-Organization permissions only.

Privacy/security risks: low to moderate; still avoid presenting partial/inaccessible as complete.

Temporal semantics: must require reference_time and knowledge_cutoff and preserve gaps/limitations.

Tests required: unit, temporal T0/T1/T2 where applicable, tenant isolation, authorization, no Animal readiness persistence, gap derivation from canonical results.

Explicit non-goals: no buyer access, no CommercialDemand persistence, no forecast unless separately approved.

Rollback/containment: isolated read behavior; no cross-tenant artifacts.

### CUT F2 - Authorization/Profile Preparation

Goal: define and implement the minimum Core-composed authorization profiles needed before buyer aggregate visibility.

Business value: creates safe path for producer opt-in and purpose-bound access.

Status: implemented as `packages/livestock_application/market_supply_authorization.py` without API, persistence, migration, grant creation, query audit persistence or cross-tenant analytics.

Domain concepts touched: `AccessPurpose`, `GrantScope`, `GrantScopeResolution`, `FieldScope`, `AccessRestriction`, `DataAccessRecord`, possibly profile/config objects for aggregation privacy.

Persistence impact: possible if existing grant/profile persistence is insufficient; requires explicit SPEC and migration review.

API impact: possible grant/profile management endpoints only if approved.

Tenant/cross-tenant impact: prepares cross-tenant access but should not expose aggregate herd data yet.

Authorization impact: high; must prove absence of grant denies access and aggregate purpose does not escalate to candidate disclosure.

Privacy/security risks: high; requires threat model checks.

Temporal semantics: valid_from, valid_until, revocation effective time, authorization context version.

Tests required: authorization, tenant isolation, revocation, purpose mismatch, FieldScope reduction, uniform denial, audit.

Explicit non-goals: no buyer aggregate analytics until privacy policy controls are ready.

Rollback/containment: feature disabled until attached to approved aggregate query.

### CUT F3 - Cross-Organization Aggregate Visibility

Goal: expose buyer aggregate Market Supply analysis under `MARKET_SUPPLY_AGGREGATE_ASSESSMENT` with producer opt-in and aggregation privacy controls.

Business value: buyer can answer whether authorized network capacity appears sufficient without seeing identities.

Domain concepts touched: `CommercialDemand` context, CandidatePopulationCriteria/Resolver/Snapshot, MarketReadiness aggregation, GapAnalysis aggregation, AggregationPrivacyPolicy, DataAccessRecord.

Persistence impact: likely CommercialDemand record and query/report audit; report persistence only if explicitly approved.

API impact: aggregate endpoint only; no details.

Tenant/cross-tenant impact: first real cross-Organization aggregate surface.

Authorization impact: critical; authorization must precede population resolution.

Privacy/security risks: critical; differencing, small groups, rare attributes, geography, repeated queries and timing.

Temporal semantics: generated_at, reference_time, knowledge_cutoff, Policy/version, authorization validity and revocation state.

Tests required: unit, integration, tenant isolation, purpose mismatch, revoked grant, uniform denial, aggregation threshold/risk controls, repeated-query/differencing controls, audit, temporal T0/T1/T2 for knowledge cutoff.

Explicit non-goals: no producer identity, property identity, Animal ID, treatments, Evidence, Dossier, individual Decisions, export or redistribution.

Rollback/containment: keep behind feature/profile switch and disable endpoint without altering historical reports/audit.

### CUT F2B - Aggregation Privacy Runtime Prerequisite

Goal: provide an explicit in-memory privacy gate for future aggregate release before any buyer-facing endpoint exists.

Business value: lets Product/Security validate suppression behavior for cohort, geography, filter, repeated-query and differencing risks without exposing producer data.

Status: implemented as `packages/livestock_application/market_supply_privacy.py` without API, persistence, migration, query audit store, CommercialDemand, CandidatePopulation resolver or cross-tenant analytics.

Domain concepts touched: `AggregationPrivacyPolicy`, `AggregationQueryFingerprint`, aggregate release assessment.

Persistence impact: none in this cut; production query audit remains a HUMAN GATE.

API impact: none.

Tenant/cross-tenant impact: none; the service receives already computed counts and fingerprints.

Authorization impact: complementary to F2; it does not replace purpose-bound grants.

Privacy/security risks: reduced for future aggregate release, but production risk remains high until policy values, audit retention, rate limits, revocation and uniform responses are approved.

Temporal semantics: requires UTC `requested_at` in query fingerprints and an explicit repeated-query window.

Tests required: cohort suppression, geospatial precision, rare attributes, filter combination, differencing, repeated query, validation.

Explicit non-goals: no production threshold, no endpoint, no persistence, no buyer result.

Rollback/containment: isolated module; unused until an approved F3 path composes it.

### CUT F2C - Market Supply Audit Envelope Prerequisite

Goal: define the auditable envelope for future aggregate Market Supply queries before persistence or endpoint work.

Business value: preserves the internal distinction between authorization denial, privacy suppression and release while keeping the external disposition uniform for denied/suppressed outputs.

Status: implemented as `packages/livestock_application/market_supply_audit.py` without API, persistence, migration, query repository, public HTTP contract or cross-tenant analytics.

Domain concepts touched: Market Supply audit envelope, authorization assessment, aggregation privacy assessment, query fingerprint.

Persistence impact: none in this cut; production audit storage remains a HUMAN GATE.

API impact: none.

Tenant/cross-tenant impact: none; the planner only composes assessments already supplied by future orchestration.

Authorization impact: positive; denial reasons remain internal audit material rather than public output.

Privacy/security risks: reduced for future release path, but still requires durable audit, retention, idempotency, rate limits and query similarity controls.

Temporal semantics: requires UTC `recorded_at` and composes the query fingerprint's UTC `requested_at`.

Tests required: authorization denial, privacy suppression, release, UTC validation, fingerprint/envelope consistency.

Explicit non-goals: no persistent audit model, no endpoint, no buyer result, no `shared_policy_access_log` semantic extension.

Rollback/containment: isolated module; unused until approved F3 or audit-persistence cut composes it.

### CUT F2D - Uniform Public Response Prerequisite

Goal: encode the application-level rule that authorization denial and privacy suppression must not expose different public response shapes.

Business value: reduces existence leaks before a buyer-facing endpoint exists.

Status: implemented as `packages/livestock_application/market_supply_response.py` without API, HTTP status decision, persistence, migration, cache policy or cross-tenant analytics.

Domain concepts touched: public aggregate response mapping, audit external disposition.

Persistence impact: none.

API impact: none; public HTTP semantics remain gated.

Tenant/cross-tenant impact: none.

Authorization impact: positive; denial reasons stay internal.

Privacy/security risks: reduced for future release path, but endpoint timing, pagination, cache and telemetry still require production design.

Temporal semantics: none changed.

Tests required: denied/suppressed same shape, no internal reasons in public response, released aggregate requires payload.

Explicit non-goals: no endpoint, no HTTP status, no buyer result, no persistent audit.

Rollback/containment: isolated mapper; unused until an approved F3 path composes it.

### CUT F2E - Revocation Semantics Hardening

Goal: make the Market Supply authorization guard deny new access from the effective `revoked_at` instant, even when a stale grant object still has active status.

Business value: reduces risk that operational lag or inconsistent projection state allows access after revocation.

Status: implemented in `packages/livestock_application/market_supply_authorization.py` without API, persistence, migration, revocation workflow or cross-tenant analytics.

Domain concepts touched: authorization grant assessment, revocation effective time.

Persistence impact: none.

API impact: none.

Tenant/cross-tenant impact: none.

Authorization impact: positive; revocation is enforced prospectively against `requested_at`.

Privacy/security risks: reduced for future release path, but opt-in/revocation UX, persistent audit and public response timing still require production design.

Temporal semantics: request before `revoked_at` may permit; request at or after `revoked_at` denies.

Tests required: before/at/after revoked_at.

Explicit non-goals: no grant creation/revocation endpoint, no audit storage, no mutation of historical material.

Rollback/containment: localized authorization check.

### CUT F2F - Aggregate Gate Workflow

Goal: compose authorization, aggregation privacy, audit envelope and public response mapping in a fixed order before any endpoint exists.

Business value: gives future application code one safe orchestration path instead of letting callers manually skip gates.

Status: implemented as `packages/livestock_application/market_supply_workflow.py` without API, persistence, migration, population resolution or cross-tenant analytics.

Domain concepts touched: aggregate access gate request/result, authorization assessment, privacy assessment, audit envelope and public response.

Persistence impact: none.

API impact: none.

Tenant/cross-tenant impact: none; the workflow accepts supplied inputs and does not query data.

Authorization impact: positive; authorization is evaluated before privacy/release.

Privacy/security risks: reduced for future release path, but production profile, persistent audit, rate limits, idempotency, query similarity and HTTP/timing/cache behavior remain gated.

Temporal semantics: preserves component temporal checks: authorization `requested_at`, revocation `revoked_at`, query fingerprint `requested_at`, audit `recorded_at` and privacy repeated-query window.

Tests required: denial before privacy, release path, privacy suppression, privacy required after allow, fingerprint consistency.

Explicit non-goals: no CandidatePopulation resolver, no endpoint, no persistence, no buyer result.

Rollback/containment: isolated workflow; unused until an approved F3 path composes it.

### CUT F2G - CandidatePopulation Snapshot

Goal: implement the approved `CandidatePopulationCriteria -> PopulationResolver -> CandidatePopulationSnapshot` shape in memory.

Business value: future Market Supply analysis can explain which supplied subjects were considered, excluded and under which criteria/digest without exposing individual membership in public summaries.

Status: implemented as `packages/livestock_application/market_supply_population.py` without API, persistence, migration, production data source, cross-tenant query or buyer visibility.

Domain concepts touched: CandidatePopulationCriteria, CandidatePopulationSubject, CandidatePopulationExclusion, CandidatePopulationSnapshot, CandidatePopulationResolver.

Persistence impact: none; persistent snapshot/digest storage remains gated.

API impact: none.

Tenant/cross-tenant impact: none; subjects from another Organization are excluded and no repository is read.

Authorization impact: preparatory; inaccessible subjects are excluded as `NOT_AUTHORIZED_OR_INACCESSIBLE`.

Privacy/security risks: reduced for future report shape because public summary omits individual subject IDs, but production resolver sources and disclosure policy remain gated.

Temporal semantics: requires UTC `reference_time`, `knowledge_cutoff`, commercial window and subject `known_at`; later-known subjects are excluded at cutoff.

Tests required: deterministic digest, explicit exclusions, inaccessible exclusions, late knowledge, Organization mismatch, public summary without IDs, tamper rejection.

Explicit non-goals: no aggregate root, no endpoint, no persistence, no real Animal/property lookup, no buyer result.

Rollback/containment: isolated module; unused until approved F3 composition.

### CUT F2H - CandidatePopulation Gate Composition

Goal: bind a supplied `CandidatePopulationSnapshot` to the aggregate gate workflow so future orchestration cannot mix authorization, privacy fingerprint and population evidence from different contexts.

Business value: reduces integration risk before buyer-facing access exists by making population mismatch fail before any public response is produced.

Status: implemented in `packages/livestock_application/market_supply_workflow.py` without API, persistence, migration, production resolver, data-source lookup, cross-tenant query or buyer visibility.

Domain concepts touched: aggregate gate request, `CandidatePopulationSnapshot`, authorization request and aggregation query fingerprint.

Persistence impact: none; persistent snapshot/digest storage and audit linkage remain gated.

API impact: none.

Tenant/cross-tenant impact: none; the workflow validates supplied inputs and rejects a snapshot whose Organization differs from the authorization owner.

Authorization impact: positive; the population snapshot must match the authorization purpose, owner Organization and Policy.

Privacy/security risks: reduced for future release path, but production resolver sources, durable audit linkage, privacy profile, idempotency, rate limits and HTTP/timing/cache behavior remain gated.

Temporal semantics: no new temporal model; the snapshot digest carries its criteria, including reference_time and knowledge_cutoff.

Tests required: release with matching snapshot, digest mismatch, included-count mismatch, Organization/Policy/purpose mismatch.

Explicit non-goals: no population resolver, no endpoint, no persistence, no buyer result.

Rollback/containment: optional request field and localized validation; unused until approved F3 composition.

### CUT F2I - Production Gate Design Closure

Goal: close the production design decisions that must be accepted before any buyer-facing cross-Organization aggregate API.

Business value: turns remaining security/architecture gates into a reviewable contract before F3.

Status: accepted with changes as `docs/specs/approved/2026-08-28-market-supply-production-gate-closure.md`, `docs/adr/0071-market-supply-production-gates-before-cross-tenant-aggregate-api.md` and `docs/plans/CUT_F2I_PRODUCTION_GATE_DESIGN_CLOSURE_REPORT.md`.

Domain concepts touched: AggregationPrivacyPolicy, audit/query log, CandidatePopulationSnapshot, idempotency scope, semantic differencing, uniform response, revocation and transient CommercialDemand context.

Persistence impact: none in F2I; future audit/query persistence and snapshot storage require HUMAN REVIEW.

API impact: none; future HTTP status/timing/cache/pagination remain HUMAN REVIEW.

Tenant/cross-tenant impact: none in F2I; F3 remains blocked until approved.

Authorization impact: design-only; confirms that aggregate purpose, grant, FieldScope, revocation and snapshot/fingerprint linkage must all pass before release.

Privacy/security risks: reduced by making the gate explicit; unresolved values and schemas remain HUMAN REVIEW.

Temporal semantics: design-only; future F3 must capture reference_time, knowledge_cutoff, requested/generated times and revocation state.

Tests required: no runtime tests for F2I; future F3 requires unit, integration, RLS, temporal, idempotency, revocation, differencing and uniform response tests.

Explicit non-goals: no endpoint, no migration, no persistence, no resolver, no buyer result.

Rollback/containment: supersede ADR-0071 with a later ADR; no runtime effect.

### CUT F4 - Detailed Candidate Disclosure

Goal: disclose selected candidate group or individual subject details only under `MARKET_SUPPLY_CANDIDATE_DISCLOSURE`.

Business value: supports transaction diligence after aggregate fit is established.

Domain concepts touched: Candidate selection, FieldScope detail, subject references, artifact sharing paths.

Persistence impact: likely disclosure records and audit; must be scoped by SPEC.

API impact: detailed disclosure endpoints only if approved.

Tenant/cross-tenant impact: high; exposes protected detail by grant.

Authorization impact: critical; detailed purpose and FieldScope required.

Privacy/security risks: critical; identity and sanitary data exposure.

Temporal semantics: disclosure validity, revocation, artifact freshness and historical access.

Tests required: authorization, FieldScope, purpose separation, revocation, audit, uniform denial, no evidence/dossier leakage unless separately authorized.

Explicit non-goals: no automatic Evidence/Dossier/VerificationBundle sharing, no export by default, no reservation/contract execution.

Rollback/containment: disable detail path while preserving historical audit of already delivered material.

## Recommended Next Implementation

CUT F2B implemented the in-memory `AggregationPrivacyPolicy` runtime and query fingerprint assessment. CUT F2C implemented the audit-envelope planner. CUT F2D implemented an application-level uniform public response mapper. CUT F2E hardened revocation effective-time handling. CUT F2F composed these gates into one application workflow. CUT F2G implemented the in-memory CandidatePopulation criteria/resolver/snapshot shape with canonical digests. CUT F2H binds an optional supplied population snapshot to the aggregate gate workflow by digest, count, purpose, Policy and Organization. CUT F2I accepted the production gate closure for concrete policy profile values, persistent audit storage, retention/rate-limit/idempotency behavior, production CandidatePopulation data sources, opt-in/revocation UX, `DisclosureDecision`, temporal invariants, semantic differencing and public HTTP/timing/cache semantics.

Reason: F2 now separates purposes and field scopes, F2B can suppress risky aggregates in memory, F2C can plan the audit envelope, F2D can keep denied/suppressed public output uniform, F2E enforces revocation effective time, F2F fixes the safe gate order, F2G fixes the snapshot/digest shape, F2H prevents supplied population snapshots from drifting away from the release fingerprint, and F2I accepted the remaining production gates. The concrete F3 SPEC/PLAN now exists and requires human approval of build details before endpoint implementation.

F3 SPEC/PLAN:

- `docs/specs/approved/2026-08-28-market-supply-f3-cross-organization-aggregate-visibility.md`
- `docs/plans/CUT_F3_MARKET_SUPPLY_AGGREGATE_VISIBILITY_BUILD_PLAN.md`

The F3 plan is `PROCEED WITH CHANGES`. It now requires `MarketSupplyRequestIdentity` before population resolution, explicit semantic differencing/history assessment before `DisclosureDecision`, durable audit for all outcomes including authorization denial and revoked grants, revocation recheck before release, and a HUMAN RELEASE GATE before F3.5 API exposure.

## Gates Before Production Cross-Organization Access

- Approved CUT F SPEC.
- Concrete `CommercialDemand` persistence/API decision, if needed.
- Concrete `CandidatePopulationSnapshot` and digest decision.
- Concrete `AggregationPrivacyPolicy` profile.
- Purpose-bound authorization with `MARKET_SUPPLY_AGGREGATE_ASSESSMENT`.
- Producer opt-in path.
- Query audit persistence and operational differencing controls.
- Uniform external behavior for nonexistent/invisible/excluded data.
- Revocation behavior implemented and tested.
- Export/redistribution explicitly denied unless separately authorized.
