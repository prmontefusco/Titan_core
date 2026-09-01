# CUT F3.4 - Market Supply Query Audit Schema Proposal

**Status:** APPROVED AND IMPLEMENTED AS MIGRATION 20260831_0078

**Date:** 2026-08-31

This document proposed the production persistence shape for
`MarketSupplyQueryAuditRecord`. After human approval, the schema was implemented
as migration
`packages/core_infrastructure/persistence/migrations/versions/20260831_0078_create_market_supply_query_audit_records.py`.
It still does not authorize an endpoint, cross-tenant query, buyer-facing
release, public HTTP behavior, or production privacy profile values.

## 1. Scope

This proposal covers only durable audit persistence for the already implemented
application contract:

```text
MarketSupplyAggregateGateWorkflow
  -> CandidatePopulationSnapshot, when resolved
  -> DisclosureDecision
  -> MarketSupplyQueryAuditRecord
  -> append before public projection
```

The table exists to preserve minimized audit metadata for authorization,
privacy/disclosure, differencing, idempotency replay evidence and forensic
review. It must not become a public analytics source.

## 2. Repository Evidence

- `docs/adr/0071-market-supply-production-gates-before-cross-tenant-aggregate-api.md`
  accepts a dedicated `MarketSupplyQueryAuditRecord` concept instead of
  overloading `shared_policy_access_log`.
- `docs/specs/approved/2026-08-28-market-supply-f3-cross-organization-aggregate-visibility.md`
  allows schema proposal before migration and keeps schema/RLS/retention under
  review.
- `packages/livestock_application/market_supply_audit.py` defines the immutable
  application record and in-memory append-only repository.
- `packages/livestock_application/market_supply_workflow.py` now requires audit
  context for every auditable outcome and materializes releasable aggregate
  results only after audit append.
- Existing protected audit tables use `core_audit`, `record_owner_organization_id`,
  RLS and `FORCE ROW LEVEL SECURITY`.

## 3. Recommended Placement

Recommended schema:

```text
core_audit
```

Recommended table:

```text
market_supply_query_audit_records
```

Rationale: this is an audit record, not Livestock operational state. `core_audit`
already stores protected audit/evidence structures and keeps module ownership
explicit through table comments.

Alternative rejected for now: `livestock_audit.market_supply_query_audit_records`.
It would make ownership feel vertical-specific, but the current repository has
stronger conventions and tooling around `core_audit` for protected immutable
records.

## 4. Proposed Columns

```text
audit_id uuid not null primary key
record_owner_organization_id uuid not null
requester_organization_id uuid not null
beneficiary_organization_id uuid not null

access_purpose text not null
authorization_context_digest text not null
policy_id uuid not null
policy_version integer not null
privacy_profile_id text not null
privacy_profile_version integer not null

candidate_population_digest text not null
population_digest text null
query_fingerprint_digest text not null
policy_context_digest text not null
filter_fingerprint text not null
result_subject_count integer not null

reference_time timestamptz not null
knowledge_cutoff timestamptz not null
requested_at timestamptz not null
evaluated_at timestamptz not null
created_at timestamptz not null

disclosure_state text not null
decision_reason_codes jsonb not null
outcome text not null
external_disposition text not null
result_digest text null
revocation_state text not null

correlation_id uuid not null
idempotency_reference text not null
semantic_request_digest text not null
grant_id uuid null
record_digest text not null
```

Notes:

- `record_owner_organization_id` is the audit owner and should equal
  `audit_owner_organization_id` from the application object.
- `candidate_population_digest` is always present. For pre-population denials it
  stores the unresolved candidate/query context digest already validated against
  `query_fingerprint.policy_context_digest`.
- `population_digest` is nullable because authorization-denied queries can be
  audited before population resolution.
- `result_digest` is nullable except for `RELEASED`.
- `decision_reason_codes` is JSONB only for a list of codes, not sensitive
  payload.

## 5. Foreign Keys

Recommended:

```text
record_owner_organization_id -> core_identity.organizations.organization_id
requester_organization_id -> core_identity.organizations.organization_id
beneficiary_organization_id -> core_identity.organizations.organization_id
policy_id -> core_audit.policies.policy_id
grant_id -> core_audit.authorization_grants.grant_id, nullable
```

No FK is proposed for `correlation_id` or idempotency reference. They are audit
correlation values, not durable aggregate ownership.

## 6. Check Constraints

Recommended:

```text
policy_version >= 1
privacy_profile_version >= 1
result_subject_count >= 0
access_purpose <> ''
authorization_context_digest <> ''
privacy_profile_id <> ''
candidate_population_digest <> ''
query_fingerprint_digest <> ''
policy_context_digest <> ''
filter_fingerprint <> ''
idempotency_reference <> ''
semantic_request_digest <> ''
record_digest <> ''

outcome in (
  'RELEASED',
  'DENIED_BY_AUTHORIZATION',
  'PURPOSE_MISMATCH',
  'GRANT_REVOKED',
  'SUPPRESSED_BY_PRIVACY'
)

external_disposition in (
  'RELEASE_AGGREGATE',
  'UNIFORM_NOT_RELEASED'
)

disclosure_state in (
  'ALLOW',
  'GENERALIZE',
  'SUPPRESS',
  'DENY'
)

revocation_state in (
  'NOT_APPLICABLE',
  'NOT_REVOKED',
  'REVOKED_OBSERVED'
)

outcome = 'RELEASED'
  implies external_disposition = 'RELEASE_AGGREGATE'

outcome = 'RELEASED'
  implies result_digest is not null

outcome <> 'RELEASED'
  implies external_disposition = 'UNIFORM_NOT_RELEASED'

outcome <> 'RELEASED'
  implies result_digest is null

population_digest is null
  implies outcome <> 'RELEASED'
```

Implementation note: PostgreSQL check constraints should use explicit boolean
expressions rather than the word `implies`.

## 7. Indexes

Recommended indexes for repository operations:

```text
pk_market_supply_query_audit_records
  primary key (audit_id)

uq_market_supply_query_audit_record_digest
  unique (record_digest)

ix_market_supply_query_audit_requester_purpose_requested
  (requester_organization_id, access_purpose, requested_at desc)

ix_market_supply_query_audit_beneficiary_purpose_requested
  (beneficiary_organization_id, access_purpose, requested_at desc)

ix_market_supply_query_audit_related_fingerprint
  (requester_organization_id, beneficiary_organization_id, access_purpose,
   policy_context_digest, requested_at desc)

ix_market_supply_query_audit_policy_window
  (policy_id, policy_version, reference_time, knowledge_cutoff)

ix_market_supply_query_audit_candidate_population
  (candidate_population_digest)

ix_market_supply_query_audit_population
  (population_digest)
  where population_digest is not null

ix_market_supply_query_audit_semantic_request
  (requester_organization_id, idempotency_reference, semantic_request_digest)

ix_market_supply_query_audit_correlation
  (correlation_id)

ix_market_supply_query_audit_grant
  (grant_id)
  where grant_id is not null
```

Do not add a global index that optimizes cross-tenant exploration by arbitrary
buyer filters. Repository queries should be purpose-built and scoped.

## 8. Idempotency Constraint Recommendation

Recommendation: do not enforce idempotency conflicts in this table as the
primary mechanism. Keep idempotency authority in the existing Core
`IdempotencyService` and use this table as supporting audit evidence.

Optional supporting unique constraint:

```text
unique (requester_organization_id, idempotency_reference, semantic_request_digest)
```

Do not use:

```text
unique (requester_organization_id, idempotency_reference)
```

as the only database rule here, because conflict semantics belong to the Core
idempotency store: same key + different semantic digest must be an explicit
conflict, not silently hidden by an audit insert failure.

## 9. Append-Only Model

Runtime table permissions should allow:

```text
INSERT
SELECT through approved repository paths
```

Runtime table permissions should not allow:

```text
UPDATE
DELETE
TRUNCATE
```

The migration should enable and force RLS:

```text
ALTER TABLE core_audit.market_supply_query_audit_records
  ENABLE ROW LEVEL SECURITY;

ALTER TABLE core_audit.market_supply_query_audit_records
  FORCE ROW LEVEL SECURITY;
```

Append-only should be enforced by permissions and absence of UPDATE/DELETE RLS
policies, matching existing repository practice.

## 10. RLS Proposal

### Insert

Recommended runtime insert check:

```text
record_owner_organization_id =
  NULLIF(current_setting('titan.organization_id', true), '')::uuid
```

This keeps normal tenant-context writes owned by the active Organization.
Cross-Organization aggregate workflows must not spoof the owner via request
payload.

### Runtime Select

Recommended default runtime select:

```text
record_owner_organization_id =
  NULLIF(current_setting('titan.organization_id', true), '')::uuid
```

This is stricter than `shared_policy_access_log`, which allows both sides of a
policy-sharing grant to inspect the access trail. Market Supply audit can reveal
membership, suppression and differencing risk, so buyer/contributor visibility
must be exposed only through purpose-built audit views after policy approval.

### Security/Audit Role

Internal audit/security inspection should use a dedicated operational role or
repository path, not the public buyer path. This proposal does not define that
role name.

### Rejected RLS Shape

Do not use this as the default policy:

```text
current_organization_id in (
  requester_organization_id,
  beneficiary_organization_id,
  record_owner_organization_id
)
```

Reason: requester/beneficiary visibility into raw audit rows can leak whether a
query was denied for missing grants, privacy suppression, revocation or
differencing risk.

## 11. Retention Alternatives

Retention remains a policy decision. Proposed options:

| Option | Description | Benefit | Risk |
| --- | --- | --- | --- |
| A | Long-lived full audit metadata | Strong forensic and differencing history | Larger privacy/storage burden |
| B | Split retention: keep relationship digests longer, operational metadata shorter | Better minimization with useful differencing memory | More complex retention implementation |
| C | Short uniform retention | Simple and lower storage | Weakens repeated-query/differencing defense |

Recommendation for Product/Security review: **B**, with an explicit field-level
retention matrix before migration.

Fields likely needed longest for differencing:

```text
requester_organization_id
beneficiary_organization_id
access_purpose
policy_id
policy_version
privacy_profile_id
privacy_profile_version
candidate_population_digest
population_digest
query_fingerprint_digest
policy_context_digest
filter_fingerprint
result_subject_count
reference_time
knowledge_cutoff
requested_at
disclosure_state
decision_reason_codes
outcome
external_disposition
revocation_state
semantic_request_digest
record_digest
```

## 12. Expected Repository Queries

F3.2B differencing:

```text
find_related_query_fingerprints(
  requester_organization_id,
  beneficiary_organization_id,
  access_purpose,
  policy_context_digest,
  evaluated_after
)
```

Idempotent replay evidence:

```text
find_by_request_identity(
  requester_organization_id,
  idempotency_reference,
  semantic_request_digest
)
```

Audit inspection:

```text
find_by_correlation_id(correlation_id)
find_by_audit_id(audit_id)
find_by_grant_id(grant_id)
find_by_candidate_population_digest(candidate_population_digest)
```

No repository query should return raw subject IDs, producer IDs, property IDs,
raw Evidence, Dossier, VerificationBundle or animal identifiers.

## 13. Migration Design Checklist

Before generating a migration:

- confirm final schema/table name;
- confirm RLS policy text and operational role model;
- confirm retention option and field-level retention matrix;
- confirm whether `record_digest` uniqueness is required globally or per owner;
- confirm whether `created_at` is database-generated or application-supplied;
- confirm enum representation as text checks versus PostgreSQL enums;
- confirm whether audit/security reads bypass tenant RLS through separate role or
  explicit application service;
- add integration tests for RLS and append-only behavior.

## 14. Required Tests For Future Persistence

- insert succeeds only under matching tenant context;
- insert fails under different tenant context;
- select is isolated by `record_owner_organization_id`;
- requester cannot read raw audit rows unless explicitly approved later;
- no UPDATE/DELETE is possible for runtime role;
- released record requires `result_digest`;
- non-release record rejects `result_digest`;
- pre-population denial allows `population_digest = null`;
- audit append failure blocks public projection;
- related-history query returns only scoped fingerprints;
- idempotency conflict remains controlled by Core idempotency service.

## 15. Open Policy Gates

```text
POLICY_GATE: Market Supply Audit Persistence

Why required:
Schema placement, RLS read visibility, retention and operational audit role have
security/privacy consequences.

Existing evidence:
ADR-0071 accepts a dedicated Market Supply audit concept and allows schema
proposal before migration. Existing protected audit tables use core_audit,
record_owner_organization_id, RLS and FORCE RLS.

Recommended:
Use core_audit.market_supply_query_audit_records; owner-only default runtime RLS;
append-only INSERT/SELECT with no runtime UPDATE/DELETE; split retention option B
after Security approves field-level retention.

Implementation blocked:
Production migration, transactional repository, RLS integration tests and F3.5
API release.

Work that can continue:
In-memory/application-level repository tests, workflow composition, schema review
and contract tests that do not require production persistence.
```

## 16. Decision Table

| Decision | Classification | Recommendation | Human Approval Required |
| --- | --- | --- | --- |
| Schema placement | POLICY_DECISION | `core_audit` | YES |
| Table name | IMPLEMENTATION_DECISION after placement | `market_supply_query_audit_records` | YES as part of schema package |
| Dedicated table instead of `shared_policy_access_log` | Approved architecture | Keep dedicated concept | NO |
| Default runtime RLS | POLICY_DECISION | Owner-only raw audit rows | YES |
| Append-only enforcement | Automated gate | No UPDATE/DELETE policies plus tests | NO after schema approval |
| Retention | POLICY_DECISION | Split retention option B | YES |
| Idempotency authority | Existing architecture | Core `IdempotencyService` remains authoritative | NO |
| F3.5 public API release | EXTERNAL_BEHAVIOR_DECISION | Keep gated | YES |
