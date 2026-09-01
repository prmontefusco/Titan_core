# CUT F3.5E - Market Supply Candidate Population source contract report

**Date:** 2026-09-01  
**Status:** IMPLEMENTED / VERIFIED  
**Scope:** owner-scoped contribution contract for future F3.5 Candidate Population

## Summary

F3.5E implements the application-level contract for composing Candidate
Population snapshots from explicitly supplied owner-scoped contributions.

The resolver accepts only contributions authorized by existing
`AuthorizationGrant` semantics for:

```text
MARKET_SUPPLY_AGGREGATE_ASSESSMENT
MARKET_SUPPLY_AGGREGATE_V1
```

It does not read Animals, databases or global tenant state. It does not create a
cross-tenant query, endpoint, migration or production data adapter.

## Files Changed

- `packages/livestock_application/market_supply_population.py`
- `tests/livestock_application/test_market_supply_population.py`
- `docs/plans/CUT_F3_5_MARKET_SUPPLY_RELEASE_GATE_PACKAGE.md`
- `docs/plans/CUT_F3_MARKET_SUPPLY_AGGREGATE_VISIBILITY_BUILD_PLAN.md`
- `docs/plans/MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_FINAL_REPORT.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

`market_supply_population.py` now defines:

- `AuthorizedCandidatePopulationContribution`;
- `AuthorizedCandidatePopulationRejection`;
- `AuthorizedCandidatePopulationResult`;
- `AuthorizedCandidatePopulationResolver`.

The resolver:

- receives owner-scoped subjects supplied by orchestration;
- assesses the supplied grant using `MarketSupplyAuthorizationService`;
- snapshots only permitted contributions;
- records rejected contributions as internal counts/reasons;
- performs no global Animal lookup.

## Tests Added

`tests/livestock_application/test_market_supply_population.py` now verifies:

- valid aggregate grants produce owner-scoped snapshots;
- missing grants reject the contribution without snapshot;
- revoked grants reject the contribution without snapshot;
- owner mismatch rejects the contribution before snapshot.

## Tests Executed

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_population.py tests/livestock_application/test_market_supply_authorization.py tests/livestock_application/test_market_supply_workflow.py -q
python -m uv run --locked python -m ruff check packages/livestock_application/market_supply_population.py tests/livestock_application/test_market_supply_population.py
python -m uv run --locked python -m ruff format --check packages/livestock_application/market_supply_population.py tests/livestock_application/test_market_supply_population.py
python -m uv run --locked python -m mypy packages/livestock_application/market_supply_population.py tests/livestock_application/test_market_supply_population.py
```

Results:

```text
59 passed
ruff check passed
ruff format --check passed
mypy passed
```

## Impact

- **Security impact:** positive. Contribution authorization precedes snapshot.
- **Tenant isolation impact:** none. No data access path was added.
- **Temporal semantics impact:** positive. Grant assessment uses `resolved_at`
  as the authorization coordinate for contribution inclusion.
- **Migrations:** none.
- **Public API:** no new route.

## Remaining Gates Before F3.5 Release

- Production adapter that obtains owner-scoped subjects without global lookup.
- Concrete deployment approval of privacy profile values.
- Human release gate for the first buyer-facing cross-Organization aggregate
  surface.

## Required Status

Technical status: PASS  
Policy deviation: NONE  
Unresolved security findings: NONE  
New cross-tenant semantics: NONE  
Human decision required: YES, for the remaining F3.5 release gates listed above.
