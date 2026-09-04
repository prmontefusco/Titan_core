# Market Optionality F6 Execution Report

**Status:** COMPLETED  
**Date:** 2026-09-04  
**Scope:** optional Livestock Dossier section and existing VerificationBundle interpretation for Market Optionality.

## Summary

F6 adds a safe, additive Livestock vertical section for Market Optionality inside the existing Dossier contract. The section is explanatory and derived, linked to canonical Decision, Evaluation, Policy and FactSnapshot hashes.

The existing VerificationBundle path is reused through the Livestock interpreter. No new Dossier type, VerificationBundle format, persistence model, public claim, forecast, API or migration was introduced.

## Files Changed

- `packages/livestock_application/dossier_template.py`
- `packages/livestock_application/verification_bundle_interpreter.py`
- `tests/livestock_application/test_market_eligibility_dossier_section.py`
- `docs/adr/0073-temporal-market-optionality-and-policy-versioned-readiness.md`
- `docs/specs/approved/2026-09-03-market-optionality-temporal-readiness.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

Added:

- `MarketOptionalityDossierSectionBuilder`;
- VerificationBundle interpreter support for `market_optionality` section scopes and declared gaps.

The section records:

- option state and reversibility;
- canonical Decision/Evaluation/Policy/FactSnapshot references and hashes;
- `reference_time`, `knowledge_cutoff` and optional target window;
- authority boundary statement;
- reason codes, missing evidence types and limitations;
- explicit non-goals, including not a Decision, not an Evaluation and not a forecast.

## Invariants Preserved

- F6 does not create a new Dossier type.
- F6 does not change Dossier or VerificationBundle identity semantics.
- F6 does not place forecast inside an eligibility Dossier.
- F6 does not assert export authorization or external authority recognition.
- F6 does not execute Rules.
- F6 does not emit Evaluation or Decision.
- F6 does not rewrite historical Dossier or VerificationBundle records.
- F6 requires the optionality assessment to match the canonical Decision/Evaluation/Policy context.

## Tests Added

`tests/livestock_application/test_market_eligibility_dossier_section.py` now also covers:

- optionality section links to canonical Decision, Evaluation, Policy and FactSnapshot hashes;
- optionality section refuses an assessment from another Decision;
- optionality section travels inside the existing VerificationBundle path and declares offline scopes/gaps.

## Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_eligibility_dossier_section.py tests/application/test_verification_bundle.py tests/livestock_application/test_market_optionality.py -q` - 49 passed.
- `python -m uv run --locked ruff check packages/livestock_application/dossier_template.py packages/livestock_application/verification_bundle_interpreter.py tests/livestock_application/test_market_eligibility_dossier_section.py` - passed.
- `python -m uv run --locked ruff format --check packages/livestock_application/dossier_template.py packages/livestock_application/verification_bundle_interpreter.py tests/livestock_application/test_market_eligibility_dossier_section.py` - passed.
- `python -m uv run --locked python -m mypy packages/livestock_application/dossier_template.py packages/livestock_application/verification_bundle_interpreter.py` - passed.

## Migrations

None.

## Security Impact

No new API, route, permission, grant, sharing path, notification, worker or cross-tenant query was introduced.

## Tenant Isolation Impact

No infrastructure access was introduced. Section coherence is validated against the canonical same-Organization Dossier material.

## Temporal Semantics Impact

Positive. The optionality section preserves `reference_time`, `knowledge_cutoff` and optional target window from the supplied `MarketOptionAssessment`.

## Remaining Gaps

- Public disclosure and external sharing semantics remain governed by existing Dossier/VerificationBundle controls.
- Forecast remains outside the Dossier.
- F7 AI explanation layer remains future work.

## Human Decisions Required

No additional decision is required for F6. New Dossier type, persisted analytical artifact, forecast section, public certification claim, or new sharing/publication semantics require separate approval.
