# CUT F3.5A - Disabled route contract report

**Date:** 2026-09-01  
**Status:** IMPLEMENTED / VERIFIED  
**Scope:** Market Supply F3.5 release guard before buyer-facing API

## Summary

ADR-0072 was accepted with changes and now formalizes owner-only raw audit plus
application-mediated owner/contributor-scoped differencing for F3.5. It also
turns required query-history completeness and multi-owner audit/disclosure
correlation into explicit release invariants.

F3.5A did not create the buyer-facing endpoint. It strengthened the disabled
route contract by proving both:

- `POST /v1/livestock/market-supply/aggregate-assessments` is absent from the
  OpenAPI public surface;
- an HTTP call to that path receives the same uniform route-not-found problem
  response as any non-existent route.

## Files Changed

- `docs/adr/0072-market-supply-audit-history-visibility-for-differencing.md`
- `docs/plans/CUT_F3_5_MARKET_SUPPLY_RELEASE_GATE_PACKAGE.md`
- `docs/plans/MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_FINAL_REPORT.md`
- `docs/plans/CUT_F3_5A_DISABLED_ROUTE_CONTRACT_REPORT.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`
- `tests/api/test_core_public_surface.py`

## Code Changed

`tests/api/test_core_public_surface.py` now includes
`test_market_supply_f3_5_chamada_http_recebe_404_uniforme_antes_do_release_gate`.

The test sends a synthetic request to the future F3.5 path and asserts:

- status `404`;
- `application/problem+json`;
- stable `ROTA_NAO_ENCONTRADA` response shape;
- no Market Supply-specific denial, suppression or authorization reason.

No production route, API handler, feature flag, permission seed, migration,
repository, resolver, cross-tenant query, forecast, persisted CommercialDemand
or buyer-facing aggregate visibility was created.

## ADR-0072 Acceptance With Changes

Accepted changes:

1. Alternative B is accepted for F3.5.
2. ADR-0072 does not authorize any broad audit/security role.
3. Query-history completeness required by the active privacy profile is a
   release invariant.
4. Multi-owner audit/disclosure correlation must be explicit and testable.
5. Missing, unreadable or incomplete required history must fail closed or return
   `NOT_RELEASED`, never `RELEASED`.

## Tests Executed

```text
python -m uv run --locked python -m pytest tests/api/test_core_public_surface.py -q
```

Result:

```text
11 passed
```

## Impact

- **Security impact:** positive. The future buyer-facing route remains absent
  and produces no endpoint-specific oracle.
- **Tenant isolation impact:** none. No cross-Organization data access was
  introduced.
- **Temporal semantics impact:** positive at design level. ADR-0072 now requires
  complete query-history coverage for the active privacy profile before release.
- **Migrations:** none.
- **Public API:** no new route.

## Remaining Gates Before F3.5 Release

- HTTP behavior, cache and external response contract.
- Production permission and seeding for `MARKET_SUPPLY.AGGREGATE_ASSESS`.
- Production source for Candidate Population.
- Initial production privacy profile.
- Human release gate for the first buyer-facing cross-Organization aggregate
  surface.

## Required Status

Technical status: PASS  
Policy deviation: NONE  
Unresolved security findings: NONE  
New cross-tenant semantics: NONE  
Human decision required: YES, for the remaining F3.5 release gates listed above.
