# Market Optionality F7 Execution Report

**Status:** COMPLETED  
**Date:** 2026-09-04  
**Scope:** deterministic guardrails for future AI explanations over canonical Market Optionality outputs.

## Summary

F7 adds an application-only explanation guard for Market Optionality. It prepares a canonical explanation context from an existing `MarketOptionAssessment` and validates explanation drafts against the canonical Decision, Evaluation, Policy/version, option state, reason codes, missing evidence types and limitations already present in that assessment.

No LLM provider, prompt execution, API, UI, persistence, worker or production AI governance was introduced. The guard exists so a future approved AI adapter can be constrained to summarize canonical material only.

## Files Changed

- `packages/livestock_application/market_optionality.py`
- `tests/livestock_application/test_market_optionality.py`
- `docs/adr/0073-temporal-market-optionality-and-policy-versioned-readiness.md`
- `docs/specs/approved/2026-09-03-market-optionality-temporal-readiness.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

Added:

- `MarketOptionExplanationAudience`;
- `MarketOptionExplanationAssertion`;
- `MarketOptionExplanationViolation`;
- `MarketOptionExplanationContext`;
- `MarketOptionExplanationDraft`;
- `MarketOptionExplanationValidation`;
- `MarketOptionExplanationGuardService`.

The guard:

- preserves canonical source references;
- rejects Decision/Evaluation/Policy/state mismatches;
- rejects invented reason codes, missing evidence types and limitations;
- rejects assertions that an explanation is a Decision, Evaluation, forecast, external authority recognition, new Fact, new Evidence, new Rule or option-state classifier.

## Invariants Preserved

- F7 does not create Facts, Evidence, Rules, Evaluations, Decisions, forecasts or option states.
- F7 does not call an LLM or integrate an AI provider.
- F7 does not create persistence, API, UI, worker or migration.
- F7 does not alter historical Evaluation, Decision, Dossier or VerificationBundle records.
- F7 does not add fields to Animal.
- F7 does not introduce cross-tenant query or disclosure semantics.
- F7 keeps explanation as non-authoritative text over canonical references.

## Tests Added

`tests/livestock_application/test_market_optionality.py` now covers:

- canonical source-reference preservation in explanation context;
- acceptance of a draft that only summarizes canonical references;
- rejection of invented gap/reason material;
- rejection of authoritative or forecast claims.

## Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_optionality.py -q` - 22 passed.
- `python -m uv run --locked ruff check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked ruff format --check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked python -m mypy packages/livestock_application/market_optionality.py` - passed.

## Migrations

None.

## Security Impact

Positive. F7 creates a machine-checkable guard before any future AI adapter can present Market Optionality explanations. No external surface or model integration was added.

## Tenant Isolation Impact

No infrastructure access was introduced. The guard works only on supplied `MarketOptionAssessment` material and preserves the assessment Organization reference.

## Temporal Semantics Impact

Positive. Explanation context preserves `reference_time`, `knowledge_cutoff` and optional target window from the canonical assessment.

## Remaining Gaps

- Real LLM integration remains blocked until AI governance/provider/prompt lifecycle is approved.
- User-visible AI explanation remains future work and requires an approved external behavior contract.

## Human Decisions Required

No additional decision is required for F7 as implemented. Future LLM provider integration, prompt storage, user-visible AI output, AI audit retention, model/version policy or AI-assisted gap generation require separate approval.
