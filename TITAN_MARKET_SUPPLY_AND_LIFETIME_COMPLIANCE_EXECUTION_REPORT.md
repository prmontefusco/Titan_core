# TITAN Market Supply and Lifetime Compliance Execution Report

Date: 2026-08-28

Update after human approval: the Impact Assessment was accepted and CUT A/C were implemented within already approved architectural limits. A later acceptance pass promoted ADR-0069 and ADR-0070 to ACCEPTED and moved the Market Supply / Progressive Disclosure SPECs to `docs/specs/approved/`. CUT F was not started.

## 1. Repository State Discovered

The repository is a Python/FastAPI modular monolith with React frontend, PostgreSQL/PostGIS, Core and Livestock packages, API, worker, migrations, tests, ADRs through ADR-0068, and extensive Livestock design packages. Git state at start was `main...origin/main [ahead 15]`.

## 2. Relevant ADRs

Relevant accepted ADRs: 0042, 0044, 0048, 0050, 0051, 0052, 0053, 0054, 0060, 0061, 0062, 0063, 0064, 0065, 0068.

## 3. Existing Capabilities

- External animal identifiers with validity, evidence reference, issuer source, and temporal event reconstruction.
- Dimensional coverage contributions and coverage assessment.
- FactSnapshot with `reference_time`, `knowledge_cutoff`, knowledge limitations, and canonical hash.
- Imported facts, transfer artifacts, external counterparties, and explicit coverage gaps.
- Market eligibility, governed policies/rules, Evaluation, Decision, Dossier, VerificationBundle.
- MarketReadiness as a derived read model.
- BuyerPolicy Policy sharing and shared Evaluation ownership decision.
- Neutral ERP/Odoo integration contracts and outbox/inbox patterns.

## 4. Duplicate Concepts Avoided

No new identity aggregate, no CommercialDemand persistence, no SupplyForecast, no SupplyDemandAnalysis, no second gap engine, no Animal eligibility fields, no cross-tenant visibility model, no Dossier/VerificationBundle semantic change.

## 5. Architecture Conflicts Found

Market Supply Intelligence introduces unresolved RED decisions: commercial demand ownership, buyer/farmer data boundary, progressive disclosure, aggregate visibility, revocation semantics, forecast persistence, and whether any supply analytics artifact belongs near Dossier or separately.

No code/document conflict was found that required stopping before documentation. The current architecture already blocks production implementation without human approval.

## 6. Code Changed

- `packages/livestock_application/sanitary_test_coverage.py`: CUT A aligned `SANITARY_TEST_A_v1` material selection with the half-open coverage interval `[required_from, required_until)`.
- `packages/livestock_application/market_readiness.py`: CUT C made `MarketReadinessPopulationReader` prefer a divergent Decision/Evaluation pair over an orphan Decision when no exact context match exists.

## 7. Code Intentionally Not Changed

- `Animal` and `AnimalIdentifier`.
- Fact/Evidence/Policy/Evaluation/Decision/Dossier/VerificationBundle semantics.
- MarketReadiness persistence/API: still none.
- Odoo/ERP integration.
- Geodata boundaries.
- APIs, migrations, workers, outbox/inbox.
- CommercialDemand, SupplyForecast, SupplyDemandAnalysis, progressive disclosure and cross-tenant visibility.

## 8. Tests Added

- CUT A tests for treatment exactly at `required_until` in direct, dimensional contribution, and classified-material paths.
- CUT C test proving a divergent Evaluation is surfaced as reassessment instead of being hidden by an orphan Decision.

## 9. Tests Executed

Focused suite passed:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
```

Result: 31 passed.

The direct `python -m uv run --locked pytest ...` form failed locally with `uv trampoline failed to canonicalize script path`; the equivalent `python -m pytest` inside `uv run --locked` was used.

## 10. Migrations

No migrations were created.

## 11. Security Impact

Positive documentation impact: the assessment explicitly blocks broad buyer visibility, improvised consent, cross-tenant access, official integration, and leakage through aggregate analytics until ADR/SPEC approval.

## 12. Tenant Isolation Impact

No tenant boundary changed. The report reinforces Organization isolation and classifies buyer/farmer data sharing as HUMAN GATE.

## 13. Temporal Semantics Impact

CUT A changed temporal boundary handling inside `SANITARY_TEST_A_v1` so selected treatment material now matches the semi-open coverage interval `[required_from, required_until)`. CUT C preserved temporal/context mismatch visibility by surfacing divergent Evaluation context as reassessment. No historical Evaluation, Decision, Dossier or VerificationBundle was rewritten.

## 14. Remaining Gaps

- Complete any remaining source-specific historical reconstruction gaps from ADR-0062/NEXT-01 that require separate approved cuts.
- Decide whether external identity needs richer authority/scheme/source modeling.
- Approve a concrete CUT F/F0 implementation plan before any commercial BUILD.
- Approve concrete persistence/API/security profiles for any production Market Supply implementation.
- Define forecast assumptions/versioning and non-decisional artifact semantics.
- Decide whether supply analytics uses a separate artifact/report.

## 15. Human Decisions Required

| Decision | Classification | Reason | Human Approval Required |
|---|---|---|---|
| Persist `CommercialDemand` | ARCHITECTURAL_DECISION_REQUIRED | New product/domain concept with Organization ownership and API implications | Yes |
| Implement `SupplyForecast` | ARCHITECTURAL_DECISION_REQUIRED | Projection model could be confused with Decision/Evaluation | Yes |
| Implement `SupplyDemandAnalysis` | ARCHITECTURAL_DECISION_REQUIRED | Composes demand, readiness, forecast, and cross-tenant visibility | Yes |
| Buyer aggregate visibility | ARCHITECTURAL_DECISION_REQUIRED | Cross-Organization data access and reidentification risk | Yes |
| Progressive disclosure lifecycle | ARCHITECTURAL_DECISION_REQUIRED | Requires grant/purpose/scope/revocation semantics | Yes |
| Real official identity/source integration | ARCHITECTURAL_DECISION_REQUIRED | External authority contract and source profile required | Yes |
| Change Dossier/VerificationBundle for supply analytics | ARCHITECTURAL_DECISION_REQUIRED | Would alter historical verification semantics | Yes |
| Cut A lifetime coverage completion | SAFE_EXTENSION | Implemented half-open upper-boundary alignment inside approved synthetic Policy | No further approval for this narrow change |
| Cut C MarketReadiness completion | SAFE_EXTENSION | Implemented deterministic fallback inside existing derived read model | No further approval for this narrow change |
| Proposed ADR-0069 | ARCHITECTURAL_DECISION_REQUIRED | Market Supply Intelligence introduces demand/forecast/analytics concepts | Yes |
| Proposed ADR-0070 | ARCHITECTURAL_DECISION_REQUIRED | Progressive disclosure introduces cross-Organization visibility decisions | Yes |

## 16. Recommended Next Cut

Recommended next cut: HUMAN REVIEW of ADR-0069 and ADR-0070 before any commercial BUILD.

Reason: CUT A and CUT C have now been completed within narrow approved limits. CUT D/E remain design-only and contain RED decisions around ownership, authorization, visibility, revocation, forecast semantics and artifact boundaries.

## Capability Table

| Capability | Before | After | Evidence | Remaining Gap |
|---|---|---|---|---|
| External authoritative identities | Partial identifier model and event reconstruction | Documented as partial; no duplicate model added | `AnimalIdentifier`, ADR-0062/0063 | Authority/scheme/source refinement may need approved Cut B |
| Lifetime historical coverage | Partial coverage via transfer artifacts and coverage contributions | CUT A aligned synthetic Policy selection to half-open interval semantics | `sanitary_test_coverage.py`, focused tests | Full source coverage not complete |
| Dimensional coverage | Implemented service | Reuse mandated | `DimensionalCoverageService` | Expand only by Policy need |
| Evidence admissibility | Partial concrete implementation | Separation reinforced | Evidence domain, coverage admissibility | Generic assessment may need future cut |
| Historical reconstruction | Partial source readers | Current-state shortcut rejected | temporal readers, FactSnapshot | Some sources still limitation-only |
| Market readiness | Derived read model exists | CUT C tightened population reader fallback without persistence/API | `market_readiness.py`, focused tests | No supply-demand composition |
| Commercial demand | Not implemented | Classified HUMAN GATE | No production code found | Discovery/SPEC/ADR |
| Supply forecast | Not implemented | Classified HUMAN GATE | No production code found | Assumptions/version/artifact |
| Supply-demand analysis | Not implemented | Classified HUMAN GATE | No production code found | Disclosure and analytics model |
| Producer disclosure | Policy sharing exists only for buyer policy | Classified HUMAN GATE | ADR-0065/0068 | Progressive disclosure model |
| Buyer aggregate visibility | Not implemented | Classified HUMAN GATE | No aggregate API found | Authorization and privacy design |
| Gap analysis | Rule/evaluation/readiness gaps exist | Use derived approach | RuleResult, readiness gap summary | Network aggregation not approved |
| Future readiness projection | Not implemented | Classified HUMAN GATE | No production code found | Forecast semantics |
| Official sources | Simulator/source-neutral capture exists | Real integration blocked | SISBOV simulator, external capture docs | Approved official contract/profile |
| Odoo | Neutral operational contract/design exists | Left unchanged | ERP contract, POST-LIV-02B docs | Real adapter target still gated |
| Geodata | Facts/evidence/captures exist | Boundary reinforced | CAR/territorial capture code | Supply analytics dependency not approved |
| Dossier/VerificationBundle | Historical artifacts exist | Forecast excluded from eligibility dossier | Dossier and VerificationBundle code | Separate supply artifact decision |

## Files Produced

- `docs/architecture-specification/TITAN_MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_IMPACT_ASSESSMENT.md`
- `docs/product/MARKET_SUPPLY_INTELLIGENCE_CONCEPT.md`
- `TITAN_MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_EXECUTION_REPORT.md`
- `docs/specs/approved/MARKET_SUPPLY_INTELLIGENCE_SPEC.md`
- `docs/specs/approved/PROGRESSIVE_DISCLOSURE_SPEC.md`
- `docs/plans/MARKET_SUPPLY_INTELLIGENCE_DESIGN_PACKAGE.md`
- `docs/plans/PROGRESSIVE_DISCLOSURE_DATA_SHARING_DESIGN_PACKAGE.md`
- `docs/plans/PROGRESSIVE_DISCLOSURE_THREAT_MODEL.md`
- `docs/plans/FIRST_MARKET_SUPPLY_VERTICAL_SLICE_PROPOSAL.md`
- `docs/plans/CUT_A_EXECUTION_REPORT.md`
- `docs/plans/CUT_C_EXECUTION_REPORT.md`
- `docs/plans/MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_FINAL_REPORT.md`
- `docs/adr/0069-market-supply-intelligence-analises-nao-regulatorias.md`
- `docs/adr/0070-progressive-disclosure-e-visibilidade-agregada.md`
