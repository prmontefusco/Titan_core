# CUT F3.5 - Market Supply Aggregate API Release Gate Package

- **Status:** RELEASE GATE PACKAGE / NO API IMPLEMENTATION
- **Date:** 2026-08-31
- **Scope:** first future buyer-facing aggregate Market Supply API surface
- **Decision basis:** ADR-0069, ADR-0070, ADR-0071, ADR-0072,
  approved F3 SPEC and F3 build plan

## 1. Purpose

This package defines what must be true before Titan exposes the first
buyer-facing cross-Organization Market Supply aggregate endpoint.

It does not implement the endpoint, route, permission seed, production
Candidate Population resolver, HTTP contract, cache behavior or public release.

The goal is to make F3.5 releasable only when already-approved invariants can be
verified automatically and the remaining policy choices are explicitly accepted.

## 2. Proposed Endpoint

```text
POST /v1/livestock/market-supply/aggregate-assessments
```

This endpoint remains proposed. It must not be created until the release gate is
accepted.

The endpoint is aggregate-only:

- no producer identity;
- no property identity;
- no Animal identifiers;
- no individual sanitary/treatment data;
- no raw Evidence;
- no Dossier;
- no VerificationBundle;
- no forecast;
- no `CommercialDemand` persistence;
- no export authorization or regulatory recognition.

## 3. Required Pipeline

The API handler, when implemented, must be a thin adapter over the application
pipeline:

```text
HTTP Request
  |
  v
OrganizationContext / principal
  |
  v
Idempotency-Key + MarketSupplyRequestIdentity
  |
  v
AuthorizationGrant assessment
  |
  v
CandidatePopulationCriteria
  |
  v
CandidatePopulationSnapshot
  |
  v
AggregationQueryFingerprint
  |
  v
Historical query relationship assessment
  |
  v
DisclosureDecision
  |
  v
MarketSupplyAggregateGateWorkflow
  |
  v
durable MarketSupplyQueryAuditRecord
  |
  v
UniformPublicResponse
```

No endpoint code may query Animals directly, run `GROUP BY` over livestock
tables, or build a public aggregate outside this pipeline.

## 4. Releasable Result Invariant

No externally releasable Market Supply result exists unless all of the following
are present and linked:

- `CandidatePopulationSnapshot`;
- `DisclosureDecision`;
- durable `MarketSupplyQueryAuditRecord`;
- public response derived from the audit envelope;
- replay identity bound by Core idempotency.

Internal temporary calculation is allowed only as a private implementation
detail. If durable audit append fails, no public aggregate may be returned.

## 5. Proposed External Contract

### Headers

- `X-Organization-Id`: buyer/requester Organization context, following the
  existing Titan API organization-context convention.
- `Idempotency-Key`: required.

### Request Body

```json
{
  "policy_id": "uuid",
  "policy_version": 1,
  "purpose": "MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
  "quantity": 8000,
  "commercial_window": {
    "from": "2026-09-01T00:00:00Z",
    "until": "2026-10-15T00:00:00Z"
  },
  "reference_time": "2026-08-31T00:00:00Z",
  "knowledge_cutoff": "2026-08-31T00:00:00Z",
  "candidate_criteria": {
    "subject_type": "animal",
    "required_tags": []
  }
}
```

`CommercialDemandContext` remains transient. The request does not create a
commercial aggregate root or lifecycle.

### Released Response

```json
{
  "status": "RELEASED",
  "assessment_id": "uuid",
  "generated_at": "2026-08-31T12:00:00Z",
  "reference_time": "2026-08-31T00:00:00Z",
  "knowledge_cutoff": "2026-08-31T00:00:00Z",
  "policy_id": "uuid",
  "policy_version": 1,
  "population_digest": "sha256:...",
  "disclosure_decision": "ALLOW",
  "aggregate": {
    "subjects_considered": 12430,
    "ready": 7820,
    "conditioned": 1210,
    "indeterminate": 910,
    "not_ready": 1640,
    "not_evaluated": 850,
    "estimated_shortage": 180
  },
  "limitations": []
}
```

The released response may expose only aggregate information approved by the
privacy profile and disclosure decision.

### Not-Released Response

```json
{
  "status": "NOT_RELEASED",
  "assessment_id": "uuid",
  "generated_at": "2026-08-31T12:00:00Z"
}
```

The not-released response must not reveal whether the internal cause was
absence, invisibility, exclusion, authorization denial, revocation, privacy
suppression, differencing risk or unknown population.

## 6. External Behavior Proposal

These are recommended contract choices, not implemented behavior:

| Surface | Recommended contract | Reason |
| --- | --- | --- |
| Successful aggregate release | `200 OK` with `status=RELEASED` | Read-like analytical command with idempotency and no persisted demand lifecycle. |
| Protected non-release | `200 OK` with `status=NOT_RELEASED` | Avoids an authorization/privacy oracle across absence, invisibility and suppression. |
| Invalid request shape | Existing validation error convention | Does not reveal protected membership; standard client error is useful. |
| Idempotency conflict | Existing Core idempotency conflict mapping | Already-approved semantic idempotency contract. |
| Missing authentication | Existing authentication error convention | Outside Market Supply privacy oracle; platform-wide auth behavior. |
| Missing Organization context | Existing organization-context error convention | Platform boundary before Market Supply semantics. |
| Cache | `Cache-Control: no-store` and `Pragma: no-cache` | Matches sensitive verification surfaces and avoids cache-based inference/replay leakage. |
| Pagination | Not supported in F3.5 | Aggregate-only response; pagination would create a new oracle surface. |
| Retry | Same idempotency key + same semantic digest replays canonical result | Existing Core idempotency behavior. |
| Timing | No intentional reason-specific timing differences | Exact equal latency is not required, but no materially distinguishable class may reveal internal cause. |

## 7. Permission / Capability Proposal

Recommended permission code:

```text
MARKET_SUPPLY.AGGREGATE_ASSESS
```

Rationale:

- names the capability, not a regulatory conclusion;
- matches aggregate-only F3.5 scope;
- does not authorize candidate disclosure or individual access;
- keeps `MARKET_SUPPLY_CANDIDATE_DISCLOSURE` separate.

Alternative rejected:

- reusing `POLICY.LER` or livestock read permissions, because reading a Policy or
  an Organization's own herd is not equivalent to requesting derived
  cross-Organization aggregate intelligence.

## 8. Feature Flag Proposal

Recommended flag:

```text
TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED=false
```

The default must be disabled. Disabling the route must not disable historical
audit read/verification capability.

## 9. Required Automated Gates

Before release, F3.5 must have tests for:

- endpoint requires authentication and Organization context;
- endpoint requires idempotency key;
- same idempotency key and same semantic digest replays canonical result;
- same idempotency key and different semantic digest returns conflict;
- buyer/requester Organization is the active Organization context;
- missing or invalid grant returns uniform `NOT_RELEASED`;
- revoked grant returns uniform `NOT_RELEASED`;
- grant valid at admission but revoked before release returns uniform
  `NOT_RELEASED` and durable audit records `REVOKED_OBSERVED`;
- insufficient cohort returns uniform `NOT_RELEASED`;
- differencing/repeated-query risk returns uniform `NOT_RELEASED`;
- released aggregate contains no producer/property/Animal identifiers;
- released aggregate contains no raw Evidence, Dossier or VerificationBundle;
- no public aggregate is returned if durable audit append fails;
- `MarketSupplyQueryAuditRecord` is append-only and RLS owner-only;
- response schema is identical across protected non-release causes;
- cache headers are non-store for release and non-release;
- no pagination in F3.5;
- no forecast fields in F3.5;
- no `CommercialDemand` row or lifecycle is created;
- no Animal eligibility/readiness field is written.
- buyer/requester cannot read raw owner-owned `MarketSupplyQueryAuditRecord`
  rows;
- differencing history is evaluated through the approved audit-history
  visibility model from ADR-0072;
- required query-history completeness for the active privacy profile is
  demonstrated before `RELEASED`;
- missing, unreadable or incomplete required query history fails closed rather than
  releasing an aggregate.
- multi-owner assessments correlate each owner-scoped contribution to the same
  assessment/audit/disclosure context before any public aggregate is released.

## 10. Validation Script Requirement

When the endpoint is implemented, create:

```text
apps/validacao/market_supply_f3_aggregate.py
```

The script must:

- seed or discover only synthetic Organizations/data;
- create or discover the required buyer principal and producer-side grants using
  approved mechanisms;
- never require manual identifier copying;
- print each request and response body;
- explain each step in one line;
- support `--pausar`;
- demonstrate `RELEASED`, `NOT_RELEASED`, idempotent replay and idempotency
  conflict;
- avoid real producer data.

## 11. Remaining Policy Gates

### POLICY_GATE: F3.5 HTTP/public behavior

Why required:

The endpoint will be the first public surface for buyer-facing derived
cross-Organization knowledge. ADR-0071 requires approval of status/cache/timing
and related externally observable behavior.

Existing evidence:

- ADR-0071 section 7;
- approved F3 SPEC public contract notes;
- sensitive verification API precedent uses non-store cache headers.

Recommended:

- use the external behavior proposal in section 6;
- make protected non-release `200 OK` with `status=NOT_RELEASED`;
- use `Cache-Control: no-store` and `Pragma: no-cache`;
- no pagination in F3.5;
- rely on Core idempotency conflict behavior.

Implementation blocked:

- public route response mapping;
- API contract tests;
- validation script against the route.

Work that can continue:

- internal service composition;
- persistence/RLS tests;
- contract proposal and negative tests at application level.

### POLICY_GATE: F3.5 permission seeding

Why required:

Creating a permission changes the external authorization surface and role
seeding.

Existing evidence:

- ADR-0070 separates aggregate assessment from candidate disclosure;
- ADR-0071 requires permission/capability approval before API.

Recommended:

- create `MARKET_SUPPLY.AGGREGATE_ASSESS` for the aggregate endpoint only;
- do not grant candidate disclosure permission in F3.5.

Implementation blocked:

- permission seed/migration;
- API authorization dependency;
- validation script role setup.

Work that can continue:

- documentation;
- application pipeline and audit verification.

### POLICY_GATE: production Candidate Population source

Why required:

F3.5 cannot decide which producer Organizations contribute to a buyer aggregate
without an approved opt-in/grant/source rule.

Existing evidence:

- ADR-0070 aggregate-first, identity-last;
- ADR-0071 Candidate Population resolver section;
- current implementation only resolves caller-supplied in-memory subjects.

Recommended:

- first production resolver uses existing bilateral `AuthorizationGrant`
  records for `MARKET_SUPPLY_AGGREGATE_ASSESSMENT`;
- no inferred network membership;
- no implicit access from Policy sharing alone;
- no global Animal lookup.

Implementation blocked:

- production resolver that reads real Livestock data;
- F3.5 endpoint returning real aggregate counts.

Work that can continue:

- synthetic validation artifacts;
- resolver interface tests with in-memory subjects;
- audit/idempotency/privacy composition.

### CLOSED POLICY_GATE: F3.5 audit-history visibility for differencing

Why required:

F3.5 needs persisted query history to detect semantic differencing, but raw
Market Supply audit rows can reveal protected membership, revocation and
suppression information. Owner-only RLS protects raw audit, while buyer-only API
execution would make differencing history invisible.

Existing evidence:

- ADR-0071 requires historical query relationship assessment;
- migration `20260831_0078` implements owner-only RLS for
  `core_audit.market_supply_query_audit_records`;
- audit F-09 closed arbitrary `audit_owner_organization_id` at application
  boundary, but left buyer/owner history visibility as a release policy choice;
- proposed ADR-0072 recommends owner-only raw audit plus application-mediated
  owner-scoped differencing.

Accepted decision:

- ADR-0072 is `ACCEPTED WITH CHANGES`;
- alternative B is accepted for F3.5;
- keep raw audit rows owner-only by default;
- evaluate differencing through application-mediated owner/contributor-scoped
  contexts;
- do not introduce a broad audit/security role under ADR-0072;
- require demonstrably complete query-history coverage for the active privacy
  profile before any `RELEASED`;
- treat missing, unreadable or incomplete required history as fail-closed or
  `NOT_RELEASED`;
- make multi-owner audit/disclosure correlation explicit and testable;
- return only uniform public projection to the buyer.

Implementation blocked:

- none by ADR-0072 itself.

Work that can continue:

- disabled-route guard;
- application-level pipeline tests with synthetic repositories;
- documentation and release-gate review.

Remaining release blockers live in the other F3.5 gates below: HTTP behavior,
production permission, production Candidate Population source and initial privacy
profile.

### POLICY_GATE: initial production privacy profile

Why required:

ADR-0071 explicitly rejects a universal domain threshold. Numeric values for
cohort size, filters, geography and differencing are privacy policy choices.

Existing evidence:

- ADR-0071 Privacy profile section;
- current `AggregationPrivacyPolicy` requires explicit values and ships no
  global production defaults.

Recommended:

- approve a versioned profile before buyer-facing release;
- keep values configurable and recorded in audit;
- do not embed unreviewed constants as business policy.

Implementation blocked:

- production route execution against real populations;
- public aggregate release.

Work that can continue:

- tests using explicit synthetic/non-production profiles;
- profile loading design.

## 12. Release Decision Template

```text
F3.5 RELEASE DECISION

Decision:
APPROVED / APPROVED WITH CHANGES / NOT APPROVED

Approved external behavior:
<status/cache/timing/retry/pagination>

Approved permission:
<permission/capability code>

Approved population source:
<grant/opt-in/source rule>

Approved privacy profile:
<profile id/version or config reference>

Approved audit-history visibility:
<ADR-0072 option / operational model>

Required feature flag state:
<enabled/disabled/default>

Restrictions:
<any release constraints>
```

## 13. Recommended Next Cut

Do not implement F3.5 yet.

Recommended next safe cut:

```text
F3.5A - application API contract tests with route disabled
```

This cut would add tests/spec fixtures proving the route is absent or disabled
until the release gate is approved, plus application-level contract tests for the
public payload mapper and idempotency behavior. It should still avoid creating a
buyer-facing route.
