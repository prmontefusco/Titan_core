# CUT F3.2 - Query Audit Application Contract Report

Date: 2026-08-28

Status: APPLICATION CONTRACT IMPLEMENTED / PRODUCTION PERSISTENCE NOT GENERATED

## Scope

This cut implements the application-level contract for
`MarketSupplyQueryAuditRecord` and an in-memory append-only repository used by
tests and future orchestration.

It does not create a database table, migration, RLS policy, production
repository, endpoint, worker, buyer-facing response or cross-tenant query.

## Architecture Decision Used

ADR-0071 already decides that Market Supply query audit should be its own
concept, initially named `MarketSupplyQueryAuditRecord`, rather than reusing
`shared_policy_access_log`.

This implementation follows that accepted decision and keeps storage policy
open for the production persistence cut.

## Code Changed

- `packages/livestock_application/market_supply_audit.py`
  - Added immutable `MarketSupplyQueryAuditRecord`.
  - Added `MarketSupplyRevocationState`.
- Added `MarketSupplyQueryAuditRepositoryPort`.
- Added `InMemoryMarketSupplyQueryAuditRepository`.
- Added canonical `record_digest()`.
- Added `from_envelope(...)` constructor to bind audit envelope,
  `DisclosureDecision`, candidate population digest and temporal coordinates.
- Added related query fingerprint lookup for F3.2B semantic differencing input.
- Added workflow loading of related query fingerprints from the audit repository
  into privacy input before disclosure assessment.
- Added workflow-level optional audit persistence composition: when
  `MarketSupplyAuditRecordContext` and an audit repository are supplied, the
  workflow builds and appends `MarketSupplyQueryAuditRecord` before mapping the
  public response.
- Added optional `population_digest` preservation in the audit record, distinct
  from Candidate Population snapshot digest.
- Added internal Candidate Population universe summary with authorized source
  digest, selection criteria digest, population digest and counts.

## Invariants Added

- `audit_id` must be typed as `market_supply_query_audit`.
- `policy_id` must be typed as `policy`.
- `correlation_id` must be typed as `correlation`.
- `reference_time`, `knowledge_cutoff`, `requested_at` and `evaluated_at` must
  be UTC.
- Query fingerprint requester, beneficiary and purpose must match the audit
  record.
- `DisclosureDecision.query_fingerprint` must match the audit envelope.
- `DisclosureDecision.candidate_population_digest` must match the audit record.
- Released audit records require `result_digest`.
- Non-released audit records require uniform external disposition.
- In-memory repository is append-only and rejects duplicate `audit_id`.
- Related query lookup uses requester, beneficiary, purpose and Policy context
  digest without exposing subject payloads.
- Related query fingerprint lookup exposes only canonical privacy input material
  to disclosure history assessment.
- Workflow uses audit history for differencing suppression without exposing
  previous payloads or individual membership.
- Candidate Population snapshot exposes an internal universe summary while
  keeping `public_summary()` free of individual subject identifiers.
- Audit context may validate both the snapshot digest and the internal
  population digest.
- Workflow audit composition requires snapshot/fingerprint/context linkage and
  refuses to continue when audit context is supplied without an audit
  repository.
- Workflow rechecks authorization at release time and records
  `REVOKED_OBSERVED` when a grant is revoked between admission and disclosure.

## Proposed Production Schema

Schema name is still a policy/operations decision. Recommended table name:

```text
market_supply_query_audit_records
```

Recommended columns:

```text
audit_id uuid primary key
audit_owner_organization_id uuid not null
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
reference_time timestamptz not null
knowledge_cutoff timestamptz not null
requested_at timestamptz not null
evaluated_at timestamptz not null
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
created_at timestamptz not null
```

Recommended checks:

```text
policy_version >= 1
privacy_profile_version >= 1
access_purpose <> ''
authorization_context_digest <> ''
privacy_profile_id <> ''
candidate_population_digest <> ''
query_fingerprint_digest <> ''
idempotency_reference <> ''
semantic_request_digest <> ''
outcome = 'RELEASED' implies external_disposition = 'RELEASE_AGGREGATE'
outcome = 'RELEASED' implies result_digest is not null
outcome <> 'RELEASED' implies external_disposition = 'UNIFORM_NOT_RELEASED'
```

Recommended indexes:

```text
unique(audit_id)
index(requester_organization_id, access_purpose, requested_at)
index(beneficiary_organization_id, access_purpose, requested_at)
index(requester_organization_id, beneficiary_organization_id, access_purpose, policy_context_digest)
index(candidate_population_digest)
index(semantic_request_digest)
index(correlation_id)
index(grant_id) where grant_id is not null
```

Recommended idempotency constraint remains open:

```text
unique(requester_organization_id, idempotency_reference)
```

or:

```text
unique(requester_organization_id, idempotency_reference, semantic_request_digest)
```

The final choice depends on whether idempotency conflicts are stored in this
table or in the existing Core idempotency store.

## Proposed RLS Model

Production RLS remains a policy decision, but the recommended shape is:

- runtime insert allowed only through trusted application role;
- no runtime update/delete;
- requester Organization can read only records explicitly safe for requester
  audit views;
- producing/contributing Organization visibility must not reveal membership in
  suppressed or denied queries unless a future policy allows it;
- internal audit/security roles can inspect full records;
- public buyer response must never be built by direct table reads.

## Proposed Retention Alternatives

Retention is a policy decision. Options for review:

- **A. Long-lived security audit retention:** strongest differencing and
  forensic value; higher privacy/storage obligations.
- **B. Split retention:** keep query relationship digests longer, operational
  fields shorter; good minimization posture but more complex.
- **C. Short retention:** simpler and lower data footprint; weakens semantic
  differencing and historical investigation.

Recommendation for future approval: B, provided Security approves which fields
remain long-lived.

## Tests Added

- Audit record links envelope, `DisclosureDecision` and candidate population
  digest.
- Audit record rejects divergent disclosure population digest.
- Released record requires `result_digest`.
- In-memory repository is append-only.
- Related history lookup returns only matching requester/beneficiary/purpose
  and Policy context.
- Related fingerprint lookup provides previous query fingerprints for
  differencing/privacy assessment without exposing audit payloads.
- Workflow suppresses a current query when related audit history creates
  differencing risk even if the current query would pass in isolation.
- Workflow persists an audit record before returning a released public response
  when audit context is supplied.
- Auditable workflow rejects a released aggregate when an audit repository is
  configured but no `MarketSupplyAuditRecordContext` is supplied.
- Audit repository append failure blocks public response mapping, preventing
  silent release when durable audit persistence is unavailable.
- Released auditable workflow now materializes an internal
  `MarketSupplyAggregateResult` only after Candidate Population snapshot,
  `DisclosureDecision` and audit record are linked and consistent.
- Workflow rejects audit context without repository.
- Workflow rejects audit context that is not linked to the Candidate Population
  snapshot/fingerprint.
- Candidate Population internal universe summary preserves authorized source
  digest, selection criteria digest, population digest and counts while public
  summary still omits individual IDs.
- Workflow returns uniform `NOT_RELEASED` and persists audit with no result
  digest when a grant valid at admission is revoked before release.
- Auditable workflow now also persists authorization-denied pre-population
  queries, using the query fingerprint digest as the unresolved candidate
  context and leaving `population_digest` empty.

## Tests Executed

Passed:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_request.py tests/livestock_application/test_market_supply_workflow.py
python -m uv run --locked python -m ruff check packages/livestock_application/market_supply_audit.py tests/livestock_application/test_market_supply_audit.py
python -m uv run --locked python -m mypy packages/livestock_application/market_supply_audit.py tests/livestock_application/test_market_supply_audit.py
```

Result: 33 passed for the population/audit/workflow subset after adding the
F3.3 internal universe summary and population digest linkage. Ruff passed. Mypy
passed.

Focused Market Supply verification passed:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_request.py tests/livestock_application/test_market_supply_privacy.py tests/livestock_application/test_market_supply_audit.py tests/livestock_application/test_market_supply_response.py tests/livestock_application/test_market_supply_workflow.py tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply.py tests/unit/test_market_supply_synthetic.py
```

Result: 81 passed after the F3.4 aggregate-result linkage hardening.

Global verification passed:

```text
python -m uv run --locked python -m pytest
python -m uv run --locked python -m ruff check .
python -m uv run --locked python -m ruff format --check .
python -m uv run --locked python -m mypy
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m alembic check
```

Result before auditable non-release hardening: 1267 passed, 284 skipped. Ruff passed. Ruff format check passed. Mypy
passed. Alembic reported `No new upgrade operations detected` and emitted the
known repository PostGIS `geometry` warning for `property_geometries.geom`.

Latest focused workflow check after auditable non-release hardening:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_workflow.py
```

Result: 21 passed.

Latest global verification after auditable non-release hardening:

```text
python -m uv run --locked python -m pytest
python -m uv run --locked python -m ruff check .
python -m uv run --locked python -m ruff format --check .
python -m uv run --locked python -m mypy
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m alembic check
```

Result: 1270 passed, 284 skipped. Ruff passed. Ruff format check passed. Mypy
passed. Alembic reported `No new upgrade operations detected` and emitted the
known repository PostGIS `geometry` warning for `property_geometries.geom`.

## Security Impact

Positive internal impact: audit data is minimized to digests, decision metadata
and temporal coordinates. The implementation creates no new public observable
behavior and no new data access path.

## Tenant Isolation Impact

No tenant boundary changed. The repository is in-memory and test-only. The
future production table must enforce RLS and must not become a public query
surface.

## Temporal Semantics Impact

`reference_time`, `knowledge_cutoff`, `requested_at` and `evaluated_at` are
required UTC fields. Query history can distinguish what was evaluated, when it
was requested and what knowledge cutoff was used.

## Remaining Work

- Approve production schema, RLS and retention.
- Generate migration only after approval.
- Implement transactional repository only after schema approval.
- Connect persisted history to F3.2B semantic differencing.
- Connect durable audit persistence to F3.4 release invariant.

## Human Decisions Required

No human decision was required for this internal application contract.

Human approval is still required before production persistence for:

- schema placement/name;
- retention policy;
- RLS read/write rules;
- idempotency conflict storage location;
- operational access to audit records.
