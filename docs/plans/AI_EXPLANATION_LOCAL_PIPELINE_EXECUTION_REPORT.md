# AI Explanation Local Pipeline Execution Report

**Status:** COMPLETED
**Date:** 2026-09-04
**Scope:** application-only local/mock explanation pipeline over canonical Market Optionality output.

## Summary

This increment turns the F7 guard into a complete local application pipeline:

```text
MarketOptionAssessment
    -> MarketOptionExplanationContext
    -> deterministic local draft provider
    -> MarketOptionExplanationGuardService
    -> released text or canonical fallback
```

The pipeline does not call Gemini or any external provider. It exists to make the future AI boundary executable in tests while production provider governance remains blocked.

On 2026-09-04, the local pipeline added an executable DataContract allow-list for Market Optionality AI Explanation. The provider-facing prompt payload is now built from approved fields only and excludes raw Organization, subject, Policy, Decision and Evaluation identifiers.

## Files Changed

- `packages/livestock_application/market_optionality.py`
- `tests/livestock_application/test_market_optionality.py`
- `docs/specs/proposed/2026-09-04-ai-explanation-governance.md`
- `docs/plans/AI_EXPLANATION_GOVERNANCE_DESIGN_PACKAGE.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

Added:

- `MarketOptionExplanationRunContext`;
- `MarketOptionExplanationResult`;
- `MarketOptionExplanationDraftProvider`;
- `DeterministicMarketOptionExplanationDraftProvider`;
- `MarketOptionExplanationPipelineService`;
- `MarketOptionExplanationClaimType`;
- `MarketOptionExplanationClaim`;
- `MarketOptionExplanationDataContractService`;
- `MarketOptionExplanationPromptPayload`.

The service requires synthetic governance references (`data_contract_id`, version, processing activity, provider profile and model name), prepares canonical context, requests a draft from a supplied provider, validates it with the deterministic guard and releases text only when validation passes.

When validation fails, `released_text` is `None` and callers retain a canonical fallback containing only structured Market Optionality state, reversibility, Policy/version and temporal coordinates.

After ADR-0074 was accepted with changes, the pipeline was hardened with structured allowed claims. `MarketOptionExplanationContext` now carries claims originated by Titan before draft generation, and the guard rejects provider-originated claims that are not present in that allow-list.

The DataContract step runs before draft generation and fails closed for unapproved contract id/version. It preserves audience, subject type, market purpose, Policy version, `reference_time`, `knowledge_cutoff`, option state, reversibility, allowed claims and limitations, while keeping raw canonical identifiers out of provider-visible fields. Canonical source references remain internally available through aliases for guard/audit composition.

## Invariants Preserved

- No external AI provider is called by production/application code.
- No prompt or output is persisted.
- No API, UI, worker or migration was introduced.
- No Fact, Evidence, Rule, Policy, Evaluation, Decision, Dossier, VerificationBundle, forecast or option state is created by AI.
- Provider draft output cannot be released without passing the deterministic guard.
- AI/provider draft output cannot originate externally presented explanation claims.
- Provider-facing prompt payloads are built from an executable allow-list and exclude raw canonical identifiers.
- Later provider behavior cannot rewrite historical canonical records.
- No cross-tenant context or disclosure semantics were introduced.

## Tests Added

`tests/livestock_application/test_market_optionality.py` now covers:

- guarded local deterministic summary release;
- fallback with no released text when a provider invents material;
- rejection of provider-originated structured claims outside the Titan allow-list;
- provider-facing prompt payload minimization without raw Organization/subject/Policy/Decision/Evaluation ids;
- fail-closed behavior for unapproved AI Explanation DataContract id/version;
- mandatory governance references in the run context.

## Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_optionality.py -q` - 28 passed.
- `python -m uv run --locked ruff check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked ruff format --check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked python -m mypy packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.

## Migrations

None.

## Security Impact

Positive. The future provider boundary now has an executable local pipeline that fails closed before releasing generated text.

## Tenant Isolation Impact

No infrastructure access was introduced. The pipeline works only over a supplied canonical `MarketOptionAssessment`.

## Temporal Semantics Impact

Positive. The canonical fallback and explanation context preserve `reference_time` and `knowledge_cutoff`.

## Human Decisions Required

No additional decision is required for this local/mock pipeline. Production provider integration, persisted DataContract governance, prompt/output retention, user-visible AI output and provider/model selection remain outside this build.
