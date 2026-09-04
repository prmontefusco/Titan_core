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

The pipeline does not call Gemini or any external provider. It exists to make the future AI boundary executable in tests while ADR-0074 remains proposed and provider governance is not yet accepted.

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
- `MarketOptionExplanationPipelineService`.

The service requires synthetic governance references (`data_contract_id`, version, processing activity, provider profile and model name), prepares canonical context, requests a draft from a supplied provider, validates it with the deterministic guard and releases text only when validation passes.

When validation fails, `released_text` is `None` and callers retain a canonical fallback containing only structured Market Optionality state, reversibility, Policy/version and temporal coordinates.

## Invariants Preserved

- No external AI provider is called by production/application code.
- No prompt or output is persisted.
- No API, UI, worker or migration was introduced.
- No Fact, Evidence, Rule, Policy, Evaluation, Decision, Dossier, VerificationBundle, forecast or option state is created by AI.
- Provider draft output cannot be released without passing the deterministic guard.
- Later provider behavior cannot rewrite historical canonical records.
- No cross-tenant context or disclosure semantics were introduced.

## Tests Added

`tests/livestock_application/test_market_optionality.py` now covers:

- guarded local deterministic summary release;
- fallback with no released text when a provider invents material;
- mandatory governance references in the run context.

## Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_optionality.py -q` - 25 passed.
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

No additional decision is required for this local/mock pipeline. Production provider integration, real DataContract fields, prompt/output retention, user-visible AI output and provider/model selection remain pending ADR-0074 acceptance.
