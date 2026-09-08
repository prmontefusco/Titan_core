# AI Explanation Audit Persistence Execution Report

**Date:** 2026-09-08

**Status:** IMPLEMENTED

## Scope

Implemented durable minimized audit persistence for
`MarketOptionExplanationAuditRecord`, after approval of the
`AI_EXPLANATION_AUDIT_STORAGE_SCHEMA_PROPOSAL.md` persistence gate.

This cut does not implement a production AI provider, API route, UI release, raw
prompt/output retention, buyer-facing aggregate AI explanation or cross-tenant
disclosure.

## Code Changed

- Added migration
  `packages/core_infrastructure/persistence/migrations/versions/20260907_0080_create_ai_explanation_audit_records.py`.
- Added `core_audit.ai_explanation_audit_records` with:
  - `record_owner_organization_id`;
  - minimized DataContract, ProviderProfile, processing authorization, prompt,
    guard and source-reference digests;
  - `reference_time` and `knowledge_cutoff`;
  - `RELEASE_APPROVED` / `NOT_RELEASED` release disposition;
  - JSONB code arrays for opaque audit references, violation codes and
    limitations;
  - `released_output_digest` only for released output;
  - owner-scoped `record_digest` uniqueness;
  - owner-scoped indexes for correlation, idempotency, policy/time, processing
    activity and release disposition.
- Added `TransactionalAIExplanationAuditRepository` in
  `packages/livestock_infrastructure/persistence/ai_explanation_audit_repository.py`.
- Registered the table and repository in
  `packages/livestock_infrastructure/persistence/__init__.py`.

## Security And Privacy

- RLS is enabled and forced.
- Runtime policy is owner-only by `record_owner_organization_id`.
- Runtime role has no UPDATE/DELETE policy.
- Repository queries for correlation/idempotency remain owner-scoped.
- Stored material excludes raw prompt text, raw provider output, raw source
  identifiers, raw Evidence/Fact payloads, provider exception text, credentials
  and secrets.

## Tenant Isolation

The PostgreSQL integration test creates a `NOBYPASSRLS` role, inserts under the
owner Organization context, confirms owner read access and confirms another
Organization cannot read the same audit row through `get`, correlation lookup or
idempotency lookup.

## Temporal Semantics

The table preserves `reference_time`, `knowledge_cutoff`, `requested_at`,
`evaluated_at` and `created_at`. Constraints preserve temporal ordering between
`reference_time`/`knowledge_cutoff` and `requested_at`/`evaluated_at`.

## Tests Added

- `tests/infrastructure/test_ai_explanation_audit_repository.py`
- `tests/infrastructure/test_ai_explanation_audit_persistence_contract.py`
- `tests/integration/test_ai_explanation_audit_postgresql.py`

## Verification

Latest focused verification before final global gates:

```text
python -m uv run --locked python -m alembic upgrade head
python -m uv run --locked python -m pytest tests/infrastructure/test_ai_explanation_audit_repository.py tests/infrastructure/test_ai_explanation_audit_persistence_contract.py tests/integration/test_ai_explanation_audit_postgresql.py -q
python -m uv run --locked ruff check <touched files>
python -m uv run --locked ruff format --check <touched files>
python -m uv run --locked python -m mypy <touched files>
python -m uv run --locked python -m alembic check
```

Focused result:

```text
6 passed
ruff passed
format check passed
mypy passed
alembic check passed, no new upgrade operations detected
```

## Migrations

Created and applied locally:

```text
20260907_0080_create_ai_explanation_audit_records.py
```

## Remaining Gaps

- No production AI provider adapter has been implemented.
- No user-visible API/UI release exists.
- No raw prompt/output retention is authorized.
- No released presentation artifact exists for byte-identical replay.
- ProviderProfile and ProviderProcessingAuthorization remain application-level
  governance concepts for this cut.

## Human Decisions Required

No additional decision is required for this persistence cut. Production provider
selection/contract, user-visible API/UI behavior and any raw output retention
remain separate decisions.
