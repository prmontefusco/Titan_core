# AI Explanation Provider Adapter Execution Report

**Date:** 2026-09-08  
**Status:** IMPLEMENTED / PROVIDER DISABLED BY DEFAULT / SYNTHETIC END-TO-END VERIFIED

## Scope

This cut adds a production-shaped Gemini text provider adapter for Market Optionality AI
Explanation, while preserving ADR-0074 and ADR-0075 boundaries:

- no API or UI surface;
- no automatic provider invocation in production flows;
- no raw prompt/output persistence;
- no migration;
- no buyer-facing or cross-tenant AI explanation;
- no change to Evaluation, Decision, Dossier or VerificationBundle semantics.

## Code Changed

- `packages/livestock_application/market_optionality.py`
  - Added `MarketOptionExplanationProviderPayload`, a provider-facing value object that
    intentionally excludes Titan-side `source_reference_aliases`.
  - The pipeline now passes `prompt_payload.provider_payload()` to `MarketOptionExplanationTextProvider`.
    The complete `MarketOptionExplanationPromptPayload` remains internal to Titan for audit/guard
    correlation.

- `packages/livestock_infrastructure/ai_explanation_provider.py`
  - Added `GeminiMarketOptionExplanationTextProvider`.
  - Added `UrllibAIProviderHttpTransport` with injectable transport for tests.
  - Added feature flag `TITAN_GOOGLE_AI_EXPLANATION_PROVIDER_ENABLED`.
  - Added environment factory that reads `GOOGLE_AI_API_KEY` without logging it.
  - Added provider body builder that serializes only minimized provider-facing fields.
  - Added fail-closed exceptions for disabled provider, missing key, model mismatch, provider rejection and empty output.

- `apps/validacao/ai_explanation_pipeline_smoke.py`
  - Replaced the local embedded Gemini provider with the infrastructure adapter.
  - Kept the roteiro synthetic-only and manual.

- `tests/infrastructure/test_ai_explanation_provider_adapter.py`
  - Added tests for default-off behavior, minimized body, raw identifier rejection, model mismatch, environment flagging, pipeline fallback, body serialization, provider error redaction (no raw diagnostics leaked), and strict provider payload delivery.

- `tests/unit/test_ai_explanation_pipeline_smoke.py`
  - Existing smoke contract tests continue to cover the body builder through the validation roteiro.

- `tests/integration/test_ai_explanation_pipeline_postgresql.py`
  - Added the synthetic end-to-end pipeline test over the real `core_audit` table under a
    `NOBYPASSRLS` role: release with durable owner-scoped audit, provider-failure fallback and
    durable-audit-failure `NOT_RELEASED`.

## Security And Privacy

- The adapter is disabled by default.
- The adapter makes no HTTP call when disabled, missing key or model mismatch occurs.
- Provider implementations now receive `MarketOptionExplanationProviderPayload`, not the complete
  Titan-side prompt payload with source-reference aliases.
- The adapter does not serialize Organization, subject, Animal, Policy, Decision or Evaluation identifiers.
- Provider-visible vocabulary remains alias-based.
- Provider output is fully buffered before entering the deterministic guard.
- Provider errors are reduced to operational failure and are not persisted as raw diagnostics.

## Tenant Isolation Impact

No new tenant relationship, cross-tenant query, permission or API was introduced. The adapter
receives only the already minimized `MarketOptionExplanationPromptPayload` built by the
application DataContract.

## Temporal Semantics Impact

No temporal semantics changed. `reference_time` and `knowledge_cutoff` remain mandatory fields
inside the minimized prompt payload and participate in the existing pipeline/audit material.

## Migrations

None.

## Tests Executed

Focused verification:

```text
python -m uv run --locked python -m pytest tests/infrastructure/test_ai_explanation_provider_adapter.py tests/unit/test_ai_explanation_pipeline_smoke.py -q
python -m uv run --locked python -m pytest tests/infrastructure/test_ai_explanation_provider_adapter.py tests/unit/test_ai_explanation_pipeline_smoke.py tests/livestock_application/test_market_optionality.py -q
python -m uv run --locked ruff check packages/livestock_infrastructure/ai_explanation_provider.py apps/validacao/ai_explanation_pipeline_smoke.py tests/infrastructure/test_ai_explanation_provider_adapter.py tests/unit/test_ai_explanation_pipeline_smoke.py
python -m uv run --locked ruff format --check packages/livestock_infrastructure/ai_explanation_provider.py apps/validacao/ai_explanation_pipeline_smoke.py tests/infrastructure/test_ai_explanation_provider_adapter.py tests/unit/test_ai_explanation_pipeline_smoke.py
python -m uv run --locked python -m mypy packages/livestock_infrastructure/ai_explanation_provider.py apps/validacao/ai_explanation_pipeline_smoke.py tests/infrastructure/test_ai_explanation_provider_adapter.py tests/unit/test_ai_explanation_pipeline_smoke.py
```

Result before global gate: PASS.

## Manual Synthetic Provider Smoke — 2026-09-08

The manual roteiro was executed once against the real Gemini API with a synthetic
`MarketOptionAssessment` only. The API key came from the Git-ignored `.env.ai.local` and was
never printed, logged or persisted.

```text
python -m uv run --locked python -m apps.validacao.ai_explanation_pipeline_smoke
```

Observed result:

- resolved `generateContent` candidates and selected `models/gemini-3.7-flash`;
- the pipeline sent only the minimized `MarketOptionExplanationProviderPayload`;
- `payload_digest` = `2f6cce77401d42ab83ec8b4601bc5a6088e1ce2e423bcf335b5f0b27f1ad5068`;
- `guard_accepted` = `true`;
- `released_output_digest` = `07a62b682b1f8d5fe7c0e52631334597b12a900dab7608d8c5b2535774294b93`;
- the released text was intentionally omitted by the roteiro; only the contract was validated.

No real Titan, producer, Animal, Organization or Evidence data was sent. The roteiro remains
manual, synthetic and outside any production flow. The roteiro does not persist audit; durable
audit is proven by the end-to-end PostgreSQL test below.

## Synthetic End-To-End Verification With Transactional Audit

`tests/integration/test_ai_explanation_pipeline_postgresql.py` composes the full chain over the
real audit table, with the real Gemini adapter behind a stub transport (no network in tests):

```text
synthetic MarketOptionAssessment
-> MarketOptionExplanationPipelineService
-> GeminiMarketOptionExplanationTextProvider (stub transport)
-> deterministic guard
-> TransactionalAIExplanationAuditRepository
-> audit persisted before release
-> owner-scoped lookup under a NOBYPASSRLS role
```

The three cases prove:

1. **Release path.** Text is released only alongside a durable audit row whose
   `record_owner_organization_id` is derived from the canonical assessment context;
   `MarketOptionExplanationAuditRecordContext` has no Organization field to override it with.
   `reference_time` and `knowledge_cutoff` are preserved from the assessment and remain distinct
   from `requested_at`/`evaluated_at`. The stored row carries no released text, no prompt template
   text and no subject/Decision/Evaluation identifier. The provider boundary received a
   `MarketOptionExplanationProviderPayload` with no `source_reference_aliases` attribute, and the
   serialized provider request carries neither the aliases key nor the Organization id. Under a
   different Organization context the same row is invisible to `get`, `list_for_owner` and
   `find_by_correlation_id`.
2. **Provider failure.** A rejected provider call yields `NOT_RELEASED`, no released text, a
   `PROVIDER_UNAVAILABLE` violation and a preserved canonical fallback with the original temporal
   coordinates. The raw provider error text appears neither in the result nor in the stored row.
3. **Durable audit failure.** An audit `INSERT` that fails on its Policy foreign key yields
   `NOT_RELEASED`, no released text, no audit record and an `AUDIT_PERSISTENCE_FAILED` violation.
   No row survives, which is the ordering proof that release never precedes durable audit.

## Remaining Gap

The provider-facing in-process payload no longer carries Titan-side source-reference aliases, and
the synthetic end-to-end path with persisted audit is verified. Remaining work is release-oriented
and still gated by ADR-0075:

- a concrete Product/Security-approved production `ProviderProfile` and DataContract, replacing the
  synthetic `GEMINI_SYNTHETIC_VALIDATION_ONLY` profile;
- production processing-authorization wiring for external provider invocation;
- a production audit-reference key with real key management, replacing the synthetic HMAC key
  constant;
- the user-visible API/UI release gate;
- buyer-facing or cross-tenant AI explanation, which remains outside ADR-0075.

## Human Decisions Required

No new policy decision is required for this cut. User-visible AI release and any provider contract
with protected production data remain governed by ADR-0075 release gates.
