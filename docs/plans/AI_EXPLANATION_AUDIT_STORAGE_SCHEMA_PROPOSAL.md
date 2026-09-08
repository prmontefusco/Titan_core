# AI Explanation Audit Storage Schema Proposal

**Status:** APPROVED AND IMPLEMENTED AS MIGRATION 20260907_0080

**Date:** 2026-09-07

This document proposed the production persistence shape for
`MarketOptionExplanationAuditRecord`, following ADR-0074 and ADR-0075. After
human approval, the schema was implemented as migration
`packages/core_infrastructure/persistence/migrations/versions/20260907_0080_create_ai_explanation_audit_records.py`.
It still does not authorize a provider adapter, API route, UI behavior, raw
prompt/output retention, buyer-facing aggregate explanation or cross-tenant
disclosure.

## 1. Scope

The application contract already exists:

```text
MarketOptionExplanationPipelineService
  -> AIExplanationContext / allowed claims
  -> provider-safe prompt payload
  -> buffered provider wording
  -> deterministic guard
  -> MarketOptionExplanationAuditEnvelope
  -> MarketOptionExplanationAuditRecord
  -> append before AI text release, when auditable
```

This proposal covers only durable minimized audit storage for that record. The
table exists to preserve governance evidence for provider processing,
authorization, DataContract, ProviderProfile, prompt/guard versions, release
disposition, failure reasons and temporal reconstruction. It must not become a
prompt store, provider output store, analytics source or public disclosure
surface.

## 2. Repository Evidence

- `docs/adr/0074-ai-explanation-governance.md` accepts AI only as presentation
  over canonical Titan outputs and requires structured allowed claims,
  minimized context, no provider-originated claims, no unvalidated streaming and
  classification inheritance.
- `docs/adr/0075-ai-explanation-production-provider-datacontract-and-audit.md`
  accepts production ProviderProfile/DataContract/audit boundaries and requires
  durable minimized audit persistence before externally visible AI explanation
  release.
- `docs/specs/proposed/2026-09-05-ai-explanation-production-decision-package.md`
  proposes owner-scoped AI Explanation audit storage and keeps retention,
  visibility and production provider contract as policy gates.
- `packages/livestock_application/market_optionality.py` defines
  `MarketOptionExplanationAuditRecord`, `MarketOptionExplanationAuditRepositoryPort`
  and `InMemoryMarketOptionExplanationAuditRepository`.
- `MarketOptionExplanationPipelineService` now releases generated AI text only
  after audit append succeeds when an audit repository is configured.
- `MarketOptionExplanationAuditRecordContext` lets internal callers provide
  audit id, requested/evaluated timestamps and correlation id without providing
  or overriding `record_owner_organization_id`.
- In auditable mode, `MarketOptionExplanationPipelineService` requires an
  explicit `MarketOptionExplanationAuditRecordContext`; it does not silently
  mint audit correlation metadata for a repository-backed release path.
- The application-level repository contract now includes owner-scoped
  `find_by_correlation_id(...)` and `find_by_idempotency_reference(...)`
  operations for future transactional parity.
- Existing protected audit tables use `core_audit`,
  `record_owner_organization_id`, RLS and `FORCE ROW LEVEL SECURITY`.

## 3. Recommended Placement

Recommended schema:

```text
core_audit
```

Recommended table:

```text
ai_explanation_audit_records
```

Rationale: this is protected audit metadata about derived AI presentation, not
Livestock operational state. `core_audit` already contains protected audit and
evidence-adjacent records and has established RLS conventions.

Alternative rejected for now: `livestock_audit.ai_explanation_audit_records`.
That would make the first use case ownership more vertical-specific, but the
record governs provider processing and audit semantics that are likely to remain
cross-cutting.

## 4. Proposed Columns

```text
audit_id uuid not null primary key
record_owner_organization_id uuid not null

policy_id uuid not null
policy_version integer not null

reference_time timestamptz not null
knowledge_cutoff timestamptz not null
requested_at timestamptz not null
evaluated_at timestamptz not null
created_at timestamptz not null

processing_activity text not null
processing_authorization_reference text not null
processing_authorization_version integer not null
processing_authorization_digest text not null

data_contract_id text not null
data_contract_version integer not null

provider_profile text not null
provider_profile_version integer not null
provider_profile_digest text not null
model_name text not null

explanation_schema text not null
prompt_template_id text not null
prompt_template_version integer not null
prompt_template_digest text not null
guard_version integer not null
guard_digest text not null

prompt_payload_digest text not null
source_reference_digest text not null
source_reference_audit_references jsonb not null
canonical_fallback_digest text not null
idempotency_reference text null
released_output_digest text null

release_disposition text not null
accepted boolean not null
violation_codes jsonb not null
limitations jsonb not null

correlation_id uuid not null
record_digest text not null
```

Notes:

- `record_owner_organization_id` is always derived from the authorized canonical
  explanation context. It is never accepted from an HTTP request, UI, provider
  adapter or external provider.
- `released_output_digest` is present only when `release_disposition =
  RELEASE_APPROVED`.
- `source_reference_audit_references` stores only alias, key version and opaque
  keyed references; it must not store raw Decision, Evaluation, subject, Animal,
  Evidence or Fact identifiers.
- `violation_codes` and `limitations` are stable code lists, not raw exception
  text or provider diagnostics.
- `record_digest` is the canonical digest of the minimized audit record.

## 5. Foreign Keys

Recommended:

```text
record_owner_organization_id -> core_identity.organizations.organization_id
policy_id -> core_audit.policies.policy_id
```

No FK is proposed for `correlation_id`, `idempotency_reference`,
`processing_authorization_reference` or provider profile fields in the first
storage cut. They are audit/governance references; if future persisted
ProviderProfile or ProcessingAuthorization tables are approved, foreign keys can
be added in a later migration without changing the application-level invariant.

## 6. Check Constraints

Recommended:

```text
policy_version >= 1
processing_authorization_version >= 1
data_contract_version >= 1
provider_profile_version >= 1
prompt_template_version >= 1
guard_version >= 1

knowledge_cutoff >= reference_time
evaluated_at >= requested_at

release_disposition in ('RELEASE_APPROVED', 'NOT_RELEASED')

accepted = true implies release_disposition = 'RELEASE_APPROVED'
accepted = false implies release_disposition = 'NOT_RELEASED'

release_disposition = 'RELEASE_APPROVED'
  implies released_output_digest is not null

release_disposition = 'NOT_RELEASED'
  implies released_output_digest is null

length(processing_authorization_digest) = 64
length(provider_profile_digest) = 64
length(prompt_template_digest) = 64
length(guard_digest) = 64
length(prompt_payload_digest) = 64
length(source_reference_digest) = 64
length(canonical_fallback_digest) = 64
length(record_digest) = 64
idempotency_reference is null or length(idempotency_reference) = 64
released_output_digest is null or length(released_output_digest) = 64
```

JSONB shape checks should remain application-level at first. PostgreSQL checks
can assert `jsonb_typeof(...) = 'array'` for `source_reference_audit_references`,
`violation_codes` and `limitations`.

## 7. Indexes

Recommended:

```text
primary key (audit_id)
index (record_owner_organization_id, created_at)
index (record_owner_organization_id, policy_id, policy_version, reference_time, knowledge_cutoff)
index (record_owner_organization_id, correlation_id)
index (record_owner_organization_id, idempotency_reference)
index (record_owner_organization_id, processing_activity, created_at)
index (record_owner_organization_id, release_disposition, created_at)
unique (record_owner_organization_id, record_digest)
```

The unique `record_digest` is scoped by owner to avoid accidental duplicate
append for the same minimized record without turning the digest into a global
cross-tenant correlation surface.

## 8. RLS Model

Default runtime policy:

```text
record_owner_organization_id =
  nullif(current_setting('app.current_organization_id', true), '')::uuid
```

Apply:

```text
ALTER TABLE core_audit.ai_explanation_audit_records
  ENABLE ROW LEVEL SECURITY;

ALTER TABLE core_audit.ai_explanation_audit_records
  FORCE ROW LEVEL SECURITY;
```

Recommended policies:

```text
SELECT by owner Organization only
INSERT by owner Organization only
no UPDATE policy
no DELETE policy
REVOKE ALL from PUBLIC
```

Buyer, provider adapter, UI caller and requester principals must not receive raw
audit-row visibility by default. Any service/role that reads AI Explanation
audit outside owner-scoped RLS requires a separate ADR/security approval.

## 9. Append-Only Semantics

Runtime application code may insert and read owner-scoped records. It must not
update or delete records.

The table should not claim `USER_RECEIVED_OUTPUT`. Audit semantics are limited
to `RELEASE_APPROVED` or `NOT_RELEASED`; HTTP delivery observation is separate
operational telemetry.

Rollback or feature disablement must not erase historical audit rows or disable
authorized audit/history read capability.

## 10. Retention Alternatives

Retention remains a policy decision.

| Option | Description | Benefit | Risk |
| --- | --- | --- | --- |
| A | Long-lived full minimized audit metadata | Strong forensic and governance reconstruction | Larger sensitive metadata footprint |
| B | Split retention: keep relationship/integrity digests longer, operational metadata shorter | Better minimization while preserving audit correlation | More complex retention implementation |
| C | Short uniform retention | Simple and smaller footprint | Weakens incident response and replay evidence |

Recommendation for Product/Security review: **B**, with a field-level retention
matrix before migration.

Fields likely needed longest:

```text
record_owner_organization_id
policy_id
policy_version
reference_time
knowledge_cutoff
processing_activity
processing_authorization_digest
data_contract_id/version
provider_profile/version/digest
model_name
prompt_template_id/version/digest
guard_version/digest
prompt_payload_digest
source_reference_digest
canonical_fallback_digest
idempotency_reference
release_disposition
accepted
violation_codes
correlation_id
record_digest
created_at
```

Fields likely eligible for shorter retention or stricter access:

```text
source_reference_audit_references
limitations
processing_authorization_reference
```

Raw prompt text, raw provider output, provider exception text, raw source
identifiers, credentials and secrets remain out of scope for this table.

## 11. Expected Repository Operations

Append:

```text
append(record: MarketOptionExplanationAuditRecord)
```

Owner-scoped reads:

```text
get(audit_id)
list_for_owner(record_owner_organization_id)
find_by_correlation_id(correlation_id)
find_by_idempotency_reference(idempotency_reference)
```

The application-level in-memory repository already implements these operations
as owner-scoped queries. The future transactional repository must preserve that
shape and must not expose global correlation or idempotency lookup across
Organizations.

No query should return raw prompt, released text, raw provider output, source
identifiers, Evidence, Facts, Dossiers, VerificationBundles, Animal identifiers
or producer/property identifiers.

## 12. Migration Design Checklist

Before generating a migration:

- confirm final schema/table name;
- confirm RLS policy text and runtime role grants;
- confirm retention option and field-level retention matrix;
- confirm the transactional workflow passes explicit audit context from the
  authorized application boundary before repository append;
- confirm whether `record_digest` uniqueness remains per-owner;
- confirm whether `created_at` is database-generated or application-supplied;
- confirm whether provider/processing authorization tables exist or remain
  digest/reference-only;
- confirm JSONB shape checks for code arrays and audit reference arrays;
- confirm no operational read role bypasses owner-scoped RLS under this ADR.

## 13. Required Tests For Future Persistence

- migration creates `core_audit.ai_explanation_audit_records`;
- insert succeeds only when tenant context matches `record_owner_organization_id`;
- insert fails or is invisible under another tenant context;
- select is isolated by `record_owner_organization_id`;
- runtime role cannot UPDATE or DELETE records;
- caller/provider cannot supply or override record owner through repository API;
- released record requires `released_output_digest`;
- non-release record rejects `released_output_digest`;
- audit append failure blocks AI release;
- persisted record omits raw prompt, raw output, provider exception text and raw
  source identifiers;
- idempotency reference is digest-only and raw idempotency key is absent;
- opaque audit references are keyed references, not unkeyed identifier hashes;
- `reference_time` and `knowledge_cutoff` are UTC and included in digest identity;
- output classification/disclosure restrictions remain available through the
  canonical envelope or a future approved column set before any public projection.

## 14. Open Policy Gate

```text
POLICY_GATE: AI Explanation Audit Persistence

Why required:
Persistent AI audit records are sensitive metadata about provider processing,
source-derived claims, failures, idempotency and release decisions. Schema
placement is conventional, but retention, raw audit visibility and operational
role access have privacy/security consequences.

Existing evidence:
ADR-0075 requires durable minimized audit persistence before externally visible
AI explanation release. Existing protected audit tables use core_audit,
record_owner_organization_id, RLS and FORCE RLS. The application-level audit
record and audit-before-release pipeline are already executable.

Recommended:
Use core_audit.ai_explanation_audit_records; owner-only default runtime RLS;
append-only INSERT/SELECT with no runtime UPDATE/DELETE; no raw prompt/output or
raw source identifiers; split retention option B after Security approves a
field-level retention matrix.

Implementation blocked:
Production migration, transactional repository, PostgreSQL/RLS integration
tests, and any user-visible AI Explanation release that depends on durable
audit.

Work that can continue:
Application-level tests, mock provider pipeline, schema review, contract tests
that do not require production persistence, and non-production synthetic smoke
validation.
```

## 15. Decision Table

| Decision | Classification | Recommendation | Human Approval Required |
| --- | --- | --- | --- |
| Dedicated audit record concept | Accepted architecture | Keep `MarketOptionExplanationAuditRecord` | NO |
| Schema placement | Approved persistence gate | `core_audit` | APPROVED |
| Table name | Approved persistence gate | `ai_explanation_audit_records` | APPROVED |
| Default raw audit visibility | Approved persistence gate | Owner-only RLS | APPROVED |
| Append-only enforcement | Automated gate after schema approval | No UPDATE/DELETE policies plus tests | NO after schema approval |
| Raw prompt/output storage | Existing ADR-0075 policy | Denied by default | NO |
| Retention | Approved persistence gate | Split retention option B | APPROVED |
| Provider adapter/API/UI release | External behavior decision | Keep separate from storage | YES before production release |
