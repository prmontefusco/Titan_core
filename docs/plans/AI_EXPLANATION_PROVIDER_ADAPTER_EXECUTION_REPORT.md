# AI Explanation Provider Adapter Execution Report

**Date:** 2026-09-08  
**Status:** IMPLEMENTED / PROVIDER DISABLED BY DEFAULT

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
  - Added tests for default-off behavior, minimized body, raw identifier rejection, model mismatch, environment flagging, pipeline fallback and body serialization.

- `tests/unit/test_ai_explanation_pipeline_smoke.py`
  - Existing smoke contract tests continue to cover the body builder through the validation roteiro.

## Security And Privacy

- The adapter is disabled by default.
- The adapter makes no HTTP call when disabled, missing key or model mismatch occurs.
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
python -m uv run --locked ruff check packages/livestock_infrastructure/ai_explanation_provider.py apps/validacao/ai_explanation_pipeline_smoke.py tests/infrastructure/test_ai_explanation_provider_adapter.py tests/unit/test_ai_explanation_pipeline_smoke.py
python -m uv run --locked ruff format --check packages/livestock_infrastructure/ai_explanation_provider.py apps/validacao/ai_explanation_pipeline_smoke.py tests/infrastructure/test_ai_explanation_provider_adapter.py tests/unit/test_ai_explanation_pipeline_smoke.py
python -m uv run --locked python -m mypy packages/livestock_infrastructure/ai_explanation_provider.py apps/validacao/ai_explanation_pipeline_smoke.py tests/infrastructure/test_ai_explanation_provider_adapter.py tests/unit/test_ai_explanation_pipeline_smoke.py
```

Result before global gate: PASS.

## Remaining Gap

The current `MarketOptionExplanationTextProvider` protocol still passes the full
`MarketOptionExplanationPromptPayload` object to the provider adapter. The HTTP body produced by
this adapter does not include `source_reference_aliases`, but removing those aliases from the
provider-facing in-process interface should be handled as a later application contract hardening
cut, because it changes the `TextProvider` boundary rather than the provider implementation.

## Human Decisions Required

No new policy decision is required for this cut. User-visible AI release and any provider contract
with protected production data remain governed by ADR-0075 release gates.
