# Market Optionality F4 Execution Report

**Status:** COMPLETED  
**Date:** 2026-09-03  
**Scope:** transient option-preservation warnings for supplied before/after assessments.

## Summary

F4 introduces an explanatory application-only warning that compares supplied optionality assessments before and after a proposed or recorded event. It supports synthetic treatment, movement and documentary examples without reading operational repositories or changing clinical/compliance workflows.

The warning never recommends omitting, delaying or hiding facts. Animal welfare and legal duties are explicitly stated as overriding market optionality.

## Files Changed

- `packages/livestock_application/market_optionality.py`
- `tests/livestock_application/test_market_optionality.py`
- `docs/adr/0073-temporal-market-optionality-and-policy-versioned-readiness.md`
- `docs/specs/approved/2026-09-03-market-optionality-temporal-readiness.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

Added:

- `MarketOptionEventKind`;
- `MarketOptionPreservationWarningState`;
- `MarketOptionEventContext`;
- `MarketOptionPreservationWarning`;
- `MarketOptionPreservationWarningService`.

The service classifies supplied before/after optionality material as:

- `NO_KNOWN_OPTION_IMPACT`;
- `OPTION_AT_RISK`;
- `OPTION_LOSS_INDICATED`;
- `IMPACT_UNKNOWN`;
- `INSUFFICIENT_MATERIAL`.

## Invariants Preserved

- F4 does not execute Rules.
- F4 does not emit Evaluation or Decision.
- F4 does not block treatment, movement, document recording or any operational workflow.
- F4 does not provide clinical advice.
- F4 does not recommend omitting or delaying facts.
- F4 does not mutate historical Evaluation/Decision records.
- F4 does not read Animal, Treatment, Movement or Documentary repositories.

## Tests Added

`tests/livestock_application/test_market_optionality.py` now also covers:

- welfare/legal-duty boundary is always stated;
- reversible option risk remains distinct from irreversible loss;
- missing material remains insufficient, without advice to omit facts.

## Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_optionality.py -q` - 18 passed.
- `python -m uv run --locked ruff check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked ruff format --check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked python -m mypy packages/livestock_application/market_optionality.py` - passed.

## Migrations

None.

## Security Impact

No new API, route, permission, grant, sharing path, notification, worker or cross-tenant query was introduced.

## Tenant Isolation Impact

No infrastructure access was introduced. The warning validates Organization, subject and purpose consistency between the event context and supplied assessments.

## Temporal Semantics Impact

Positive. The event context requires UTC event time and `knowledge_cutoff`; supplied assessments cannot use knowledge later than the warning context.

## Remaining Gaps

- F5 supply readiness aggregation remains future work.
- Any UI or operational timing integration requires separate approval because it could affect workflow semantics.
- Public wording for end users remains unapproved.

## Human Decisions Required

No additional decision is required for F4. UI integration, workflow timing changes, clinical decision support, operational blocking, persistence or public API require separate approval.
