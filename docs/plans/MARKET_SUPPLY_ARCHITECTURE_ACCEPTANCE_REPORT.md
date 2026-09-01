# Market Supply Architecture Acceptance Report

Date: 2026-08-28

## A. Decisions Accepted

- CUT A is accepted as implemented: half-open coverage intervals, explicit coverage, no inference from missing evidence, `reference_time`, `knowledge_cutoff`, Organization isolation and historical immutability are preserved.
- CUT C is accepted as implemented: `MarketReadiness` remains a derived read model, is not persisted on `Animal`, emits no new Decision, preserves `REASSESSMENT_REQUIRED` for context divergence and keeps Organization isolation.
- Market Supply Intelligence is a non-regulatory analytical layer.
- `CommercialDemand` belongs initially to Titan Livestock and is owned by the buyer/frigorifico Organization.
- `CommercialDemand` is commercial intent only and grants no supplier access.
- Candidate Population is not a standalone Aggregate Root in the first implementation.
- Candidate Population direction is `CandidatePopulationCriteria -> PopulationResolver -> CandidatePopulationSnapshot`.
- `SupplyForecast` is computed on demand by default.
- `SupplyForecastSnapshot` is immutable and preserved only for reproducibility, shared report, historical audit or explicit analytical artifact.
- Initial forecast is deterministic, explainable, assumption-aware and has no ML/AI.
- Hypothetical corrective actions are assumptions/scenarios only.
- `GapAnalysis` derives from canonical material and does not create a parallel gap engine.
- `SupplyIntelligenceReport` is the accepted name for the separate analytical artifact.
- `SupplyIntelligenceReport` may be hashable in the future but is not Dossier or VerificationBundle.
- No real MAPA/IAGRO/SISBOV official source integration is authorized.
- Progressive disclosure follows aggregate-first, identity-last.
- Absence of a valid grant denies access.
- Commercial relationship, shared Policy, known identifier, contract, CommercialDemand or shared network participation does not imply access.
- Initial purposes are `MARKET_SUPPLY_AGGREGATE_ASSESSMENT` and `MARKET_SUPPLY_CANDIDATE_DISCLOSURE`.
- Producer participation in cross-Organization Market Supply visibility is opt-in by default.
- Existing Core Authorization concepts must be reused/composed before any Livestock-only consent model.
- `AggregationPrivacyPolicy` or equivalent is accepted as an architectural concept.
- No arbitrary global aggregation threshold is accepted.
- Reidentification and differencing protection is required before production cross-Organization aggregate API.
- External behavior must not reveal nonexistent versus invisible versus excluded data.
- Revocation is prospective.
- Export and redistribution are deny-by-default.
- Cross-Organization Market Supply access must be auditable.

## B. ADR Status

| ADR | Final Status | Conflicts Found |
|---|---|---|
| ADR-0069 - Market Supply Intelligence como analise nao regulatoria | ACCEPTED | None found against `DOMAIN.md`, `ARCHITECTURE.md` or accepted ADRs inspected |
| ADR-0070 - Progressive disclosure e visibilidade agregada | ACCEPTED | None found against `DOMAIN.md`, `ARCHITECTURE.md` or accepted ADRs inspected |

Acceptance of ADR-0069/0070 does not authorize CUT F implementation.

## C. Files Changed

Architecture acceptance pass:

- `docs/adr/0069-market-supply-intelligence-analises-nao-regulatorias.md`
- `docs/adr/0070-progressive-disclosure-e-visibilidade-agregada.md`
- `docs/specs/approved/MARKET_SUPPLY_INTELLIGENCE_SPEC.md`
- `docs/specs/approved/PROGRESSIVE_DISCLOSURE_SPEC.md`
- `docs/product/MARKET_SUPPLY_INTELLIGENCE_CONCEPT.md`
- `docs/plans/MARKET_SUPPLY_INTELLIGENCE_DESIGN_PACKAGE.md`
- `docs/plans/PROGRESSIVE_DISCLOSURE_DATA_SHARING_DESIGN_PACKAGE.md`
- `docs/plans/PROGRESSIVE_DISCLOSURE_THREAT_MODEL.md`
- `docs/plans/FIRST_MARKET_SUPPLY_VERTICAL_SLICE_PROPOSAL.md`
- `docs/plans/MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_FINAL_REPORT.md`
- `TITAN_MARKET_SUPPLY_AND_LIFETIME_COMPLIANCE_EXECUTION_REPORT.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`
- `docs/plans/MARKET_SUPPLY_ARCHITECTURE_ACCEPTANCE_REPORT.md`

Files already changed by the previously accepted CUT A/C execution remain in the working tree:

- `packages/livestock_application/sanitary_test_coverage.py`
- `packages/livestock_application/market_readiness.py`
- `tests/livestock_application/test_sanitary_test_coverage.py`
- `tests/livestock_application/test_dimensional_coverage.py`
- `tests/livestock_application/test_market_readiness.py`

## D. Production Code Changed

NONE in this architecture acceptance pass.

The working tree still contains accepted CUT A/C production code changes from the prior build pass. This pass did not add new runtime behavior, endpoints, migrations, workers, grants, forecast code or cross-tenant queries.

## E. Migrations

NONE.

No migration file was created by this acceptance pass.

## F. Tests/Checks Executed

Commands inherited from the accepted CUT A/C verification:

```text
python -m uv run --locked python -m pytest tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
```

Result: 31 passed.

```text
python -m uv run --locked python -m pytest
```

Result: 1177 passed, 284 skipped.

```text
python -m uv run --locked python -m alembic check
```

Result with `TITAN_MIGRATION_DATABASE_URL` configured: `No new upgrade operations detected`, with the known PostGIS `geometry` warning.

Documentation/acceptance checks executed in this pass:

```text
git diff --check
rg search for stale Market Supply spec paths and old CUT D/E review status
python -m uv run --locked python -m pytest tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
python -m uv run --locked python -m ruff check packages/livestock_application/sanitary_test_coverage.py packages/livestock_application/market_readiness.py tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
python -m uv run --locked python -m ruff format --check packages/livestock_application/sanitary_test_coverage.py packages/livestock_application/market_readiness.py tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m alembic check
```

Result: no whitespace errors except the existing CRLF-to-LF warning for `docs/CHECKLIST_DE_IMPLEMENTACAO.md`; stale Market Supply references were removed or updated; focused tests passed with 31 passed; focused Ruff check passed; focused Ruff format check passed; Alembic reported `No new upgrade operations detected`.

Known preexisting failures outside this architecture pass remain unrelated:

- repository-wide Ruff check fails in BuyerPolicy realistic integration tests and one migration import block;
- repository-wide Ruff format reports formatting needed in preexisting BuyerPolicy/migration files;
- repository-wide Mypy reports existing BuyerPolicy protocol/type errors;
- these do not block accepting ADR-0069/0070, but must be handled in a dedicated technical-debt cut if they block future CUT F CI.

## G. Resolved HUMAN GATES

- ADR-0069 acceptance: resolved, accepted.
- ADR-0070 acceptance: resolved, accepted.
- `CommercialDemand` owner: resolved, Titan Livestock and buyer/frigorifico Organization.
- Candidate Population representation direction: resolved for first implementation, no standalone Aggregate Root.
- SupplyForecast persistence direction: resolved, computed on demand by default with immutable snapshot only when needed.
- Forecast ML/AI: resolved, not allowed in CUT F.
- Hypothetical corrective actions: resolved, assumptions/scenarios only.
- GapAnalysis mechanism: resolved, derive from canonical results.
- Supply analytics artifact name/boundary: resolved, `SupplyIntelligenceReport`, separate from Dossier/VerificationBundle.
- Progressive disclosure principle: resolved, aggregate-first and identity-last.
- Initial purposes: resolved, aggregate assessment and candidate disclosure are separate.
- Producer participation default: resolved, explicit opt-in.
- Revocation semantics: resolved, prospective.
- Export/redistribution: resolved, deny-by-default.
- Official source integration: resolved, none authorized.

## H. Remaining HUMAN GATES

- Authorize a specific CUT F/F0 implementation.
- Approve concrete production persistence/API contracts before writing code.
- Approve concrete `CandidatePopulationSnapshot` canonical digest model.
- Approve concrete production `AggregationPrivacyPolicy` profile, including floors, dynamic risk factors and suppression/generalization behavior.
- Approve query audit persistence, retention and operational differencing/rate-limit controls.
- Approve concrete `GrantScope`, `FieldScope`, `AccessPurpose` operation mapping and audit tier for any runtime access.
- Approve producer opt-in/revocation UX and authority model.
- Approve `SupplyIntelligenceReport` storage, hashability, verification and export behavior.
- Decide whether BuyerPolicy technical-debt failures must be fixed before any production CUT F CI gate.

## I. CUT F Readiness

Classification: `READY_ONLY_AFTER_PREREQUISITE_CUT`.

Reason: ADR-0069/0070 are accepted, CUT F0 validated the synthetic report shape, CUT F1 introduced internal single-Organization producer-side aggregation, CUT F2 prepared purpose/scope authorization guards, CUT F2B added an in-memory aggregation privacy runtime, CUT F2C added an audit-envelope planner, CUT F2D added an application-level uniform public response mapper, CUT F2E hardened revocation effective-time handling, CUT F2F composed the aggregate gates into one in-memory workflow, CUT F2G added the CandidatePopulation criteria/resolver/snapshot shape with canonical digests, and CUT F2H bound an optional supplied population snapshot to the aggregate gate workflow. Production cross-Organization Market Supply still requires approved production privacy profile values, persistent query audit/differencing controls, production CandidatePopulation data-source resolution, opt-in/revocation workflow and public HTTP/timing/cache semantics.

## J. Recommended CUT F Decomposition

| Cut | Goal | Business Value | Domain Concepts Touched | Persistence Impact | API Impact | Tenant/Cross-Tenant Impact | Authorization Impact | Privacy/Security Risks | Temporal Semantics | Tests Required | Non-goals | Rollback/Containment |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F0 | Synthetic/in-memory analytical prototype | Validate vocabulary and report shape cheaply | none in production; mock mirrors approved concepts | none | none | none | none | low; synthetic data only | include generated_at/reference_time/knowledge_cutoff in mock | fixture/schema checks if scripted; stakeholder review | no production package, endpoint, migration, real grants or forecast | delete prototype artifacts |
| F1 | Single-Organization producer-side analysis | Producer sees own capacity/gaps before sharing | MarketReadiness, canonical gaps, optional report shape | preferably none; report persistence needs SPEC | optional producer-only API/validation script if approved | no cross-tenant | same-Organization permissions | low/moderate; avoid partial-as-complete | strict reference_time/knowledge_cutoff and explicit limitations | unit, temporal, tenant isolation, authorization, gap derivation | no buyer access, no cross-tenant, no export | isolated read behavior |
| F2 | Authorization/profile preparation | Enables safe future opt-in and buyer aggregate access | AccessPurpose, GrantScope, FieldScope, AccessRestriction, DataAccessRecord, AggregationPrivacyPolicy profile | possible, requires SPEC/migration review | possible grant/profile endpoints if approved | prepares but does not expose cross-tenant analytics | high | high | valid_from/valid_until/revocation/context version | authorization, purpose mismatch, FieldScope, revocation, uniform denial, audit | no buyer aggregate analytics yet | feature/profile disabled until attached |
| F2B | Aggregation privacy runtime prerequisite | Provides pre-release suppression assessment before buyer access exists | AggregationPrivacyPolicy, AggregationQueryFingerprint, aggregate release assessment | none; production audit persistence still requires approval | none | none; receives counts/fingerprints only | complementary to F2 | high but reduced for future release path | UTC requested_at and explicit repeated-query window | cohort, geography, rare attributes, filter combinations, differencing, repetition | no production threshold, no endpoint, no persistence, no buyer result | isolated module; unused until approved F3 composition |
| F2C | Audit envelope prerequisite | Defines internal audit material before any public aggregate response | authorization assessment, privacy assessment, query fingerprint, audit envelope | none; storage model remains gated | none | none | high; preserves denial reason internally | high but reduced for future release path | UTC recorded_at and query requested_at | denial, suppression, release, fingerprint consistency, UTC | no persistent audit, no endpoint, no public HTTP contract | isolated module; unused until approved F3/audit storage composition |
| F2D | Uniform public response prerequisite | Prevents denial/suppression reason leaks at application response boundary | public aggregate response mapper, audit external disposition | none | none; HTTP semantics remain gated | none | positive; reasons stay internal | high but reduced for future release path | none changed | denied/suppressed same shape, released payload required | no endpoint, no status code, no cache/timing behavior | isolated mapper; unused until approved F3 composition |
| F2E | Revocation effective-time hardening | Prevents stale active grants from authorizing access after revoked_at | authorization grant assessment, revocation effective time | none | none | none | positive; revoked_at denies at/after requested_at | moderate reduction | requested_at compared to revoked_at | before/at/after revoked_at | no revocation workflow, no audit storage, no historical material mutation | localized authorization check |
| F2F | Aggregate gate workflow | Fixes safe order for future aggregate release gates | authorization, privacy, audit envelope, public response | none | none | none | positive; authorization first | high but reduced for future release path | preserves component times | denial before privacy, release, suppression, privacy required, fingerprint consistency | no population resolver, no endpoint, no persistence | isolated workflow; unused until approved F3 composition |
| F2G | CandidatePopulation snapshot | Fixes criteria/resolver/snapshot/digest shape without data-source coupling | CandidatePopulationCriteria, Resolver, Snapshot, canonical digests | none | none | none; supplied subjects only | preparatory; inaccessible excluded explicitly | moderate reduction; public summary omits IDs | reference_time, knowledge_cutoff, known_at, commercial window | deterministic digest, exclusions, cutoff, org mismatch, public summary, tamper | no aggregate root, no endpoint, no persistence, no real Animal/property lookup | isolated module; unused until approved F3 composition |
| F2H | CandidatePopulation gate composition | Prevents supplied population snapshots from drifting from authorization and privacy/audit fingerprints | aggregate gate request, CandidatePopulationSnapshot, authorization request, query fingerprint | none; snapshot storage remains gated | none | none; supplied inputs only | positive; snapshot must match purpose, owner Organization and Policy | moderate reduction; mismatch fails before public response | snapshot digest carries reference_time/knowledge_cutoff criteria | matching release, digest mismatch, count mismatch, Organization/Policy/purpose mismatch | no resolver, no endpoint, no persistence, no buyer result | optional field and localized validation |
| F3 | Cross-Organization aggregate visibility | Buyer sees authorized aggregate capacity | CommercialDemand context, Candidate Population, MarketReadiness aggregate, GapAnalysis, AggregationPrivacyPolicy | likely demand/audit/report records | aggregate endpoint only | first real cross-tenant aggregate surface | critical | critical: differencing, geography, rare attributes, timing | generated_at/reference_time/knowledge_cutoff/Policy/version/grant state | integration, tenant isolation, privacy controls, differencing, audit, revocation, temporal | no identities, treatments, Evidence, Dossier, export | feature switch; disable endpoint, preserve audit |
| F4 | Detailed candidate disclosure | Supports diligence after aggregate fit | candidate selection, FieldScope detail, artifact sharing paths | likely disclosure records/audit | detail endpoints | high | critical | critical identity/sanitary exposure | disclosure validity, revocation, artifact freshness | authorization, FieldScope, purpose separation, revocation, audit, uniform denial | no automatic Evidence/Dossier sharing, no export by default | disable detail path, preserve delivered audit |

## K. Recommended First Implementation

CUT F0 has been implemented as a synthetic/in-memory validation artifact after Product Owner authorization. CUT F1 has been implemented as internal producer-side single-Organization aggregation over existing MarketReadiness. CUT F2 has been implemented as preparation-only authorization/profile guards over existing `AuthorizationGrant`. CUT F2B has been implemented as an in-memory aggregation privacy runtime over explicit policy inputs and query fingerprints. CUT F2C has been implemented as an in-memory audit-envelope planner. CUT F2D has been implemented as an application-level uniform public response mapper. CUT F2E has been implemented as revocation effective-time hardening. CUT F2F has been implemented as in-memory aggregate gate orchestration. CUT F2G has been implemented as in-memory CandidatePopulation snapshot/digest support. CUT F2H has been implemented as optional population snapshot binding inside the aggregate gate workflow.

Recommended next step: execute F3.0 design closure from the concrete F3 SPEC/PLAN created in `docs/specs/approved/2026-08-28-market-supply-f3-cross-organization-aggregate-visibility.md` and `docs/plans/CUT_F3_MARKET_SUPPLY_AGGREGATE_VISIBILITY_BUILD_PLAN.md`. No buyer-facing cross-Organization aggregate API should exist until privacy profile values, persistent audit storage, retention/rate-limit/idempotency behavior, revocation enforcement, production Candidate Population resolver sources and public HTTP/timing/cache semantics are approved, implemented and tested. F3.5 also requires a HUMAN RELEASE GATE after F3.1-F3.4 pass technical acceptance.
