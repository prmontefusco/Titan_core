# TITAN Market Supply and Lifetime Compliance Impact Assessment

STATUS: DISCOVERY / IMPACT ASSESSMENT ONLY

Date: 2026-08-28

This assessment consolidates product and architecture ideas derived from August/2026 market signals against the real repository state. It does not authorize production implementation, persistence changes, cross-tenant access, official integrations, forecast models, or new aggregate roots.

## Repository State

Authority documents read: `VISION.md`, `DOMAIN.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`.

Relevant accepted ADRs found:

- ADR-0042: external counterparty, custody transfer, imported facts, continuity by artifact, and explicit coverage gaps.
- ADR-0044: market eligibility matrix driven by governed rules.
- ADR-0048: explainable decisions, strict Fact/Evidence/Policy/Evaluation/Decision separation.
- ADR-0050: deterministic and isolated Policy/Rule execution.
- ADR-0051: canonical snapshot identity, hashes, and provenance.
- ADR-0052: valid time versus knowledge time, `reference_time` and `knowledge_cutoff`.
- ADR-0053: Decision authority and competence.
- ADR-0054: DecisionProposal, review, approval, and override.
- ADR-0060: vertical extensions for VerificationBundle.
- ADR-0061: temporal normative selection before market eligibility.
- ADR-0062: historical Livestock reconstruction by source.
- ADR-0063: canonical event content reader for temporal identifier reconstruction.
- ADR-0064: buyer-specific internal Policies.
- ADR-0065: contractual Policy sharing.
- ADR-0068: shared Evaluation ownership belongs to the supplier/beneficiary.

Relevant design packages found:

- `LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md`, `LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md`, `LIV-C08_DESIGN_PACKAGE.md`, `LIV-C09_OPERATIONAL_INTEGRATION_VALIDATION_DESIGN_PACKAGE.md`.
- `NEXT-01_COVERAGE_ADMISSIBILITY_DESIGN_PACKAGE.md`, `NEXT-05_MARKET_ELIGIBILITY_DOSSIER_DESIGN_PACKAGE.md`, `NEXT-06_MARKET_READINESS_DESIGN_PACKAGE.md`.
- `POST_LIV_01_OPERATIONAL_HARDENING_DESIGN_PACKAGE.md`, `POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE.md`, `POST_LIV_02B_ODOO_COMMUNITY_ADAPTER_DESIGN_PACKAGE.md`.
- BuyerPolicy Fase 1/2/3 documents in `docs/plans/` and `docs/specs/`.

Existing implementation evidence:

- `Animal` has internal Titan identity and `AnimalIdentifier` with type, value, state, issuer source, evidence reference, verification status, validity, attach/deactivation time.
- `animal_identifiers` persistence exists and is Organization-scoped; migrations include audit/validity fields.
- Temporal identifier reconstruction exists through ADR-0062/0063 and `TemporalAnimalIdentifierReader`, consumed by `LivestockFactProvider`.
- `Fact` and `FactSnapshot` preserve `reference_time`, `knowledge_cutoff`, knowledge limitations, source references, and canonical snapshot hash.
- `CoverageContribution`, `StoredCoverageContribution`, `DimensionalCoverageService`, and `ReceivedTransferArtifactCoverageAdapter` implement dimensional coverage contribution and assessment.
- `ReceivedTransferArtifact`, `HistoryCoverage`, `TransferArtifactGap`, `ImportedLivestockFact`, and `ExternalCounterparty` implement cross-Organization continuity by proof/imported assertion, not shared history.
- `MarketReadinessService` and `MarketReadinessPopulationReader` implement contextual readiness as a derived read model from `Decision`, `Evaluation`, and `Policy`.
- `MarketEligibilityDossierSectionBuilder`, `LivestockDossierTemplate`, `DossierService`, and `VerificationBundleService` preserve Dossier/VerificationBundle as historical, verifiable artifacts.
- ERP/Odoo is represented by neutral outbound operational intent and Odoo design packages that preserve Odoo as operational system, not sanitary authority.

## Capability Classification Matrix

| Capability | Classification | Existing Code | Existing Documents | Recommended Action |
|---|---|---|---|---|
| 1. External authoritative animal identities | PARTIALLY_IMPLEMENTED | `AnimalIdentifier`, `animal_identifiers`, temporal identifier reader, event-based reconstruction | ADR-0040, ADR-0062, ADR-0063 | Do not create a new aggregate. Add authority/scheme/source semantics only through an approved cut if current `issuer_source`/type/evidence is insufficient. |
| 2. Lifetime historical coverage | PARTIALLY_IMPLEMENTED | `HistoryCoverage`, `CoverageContribution`, dimensional service, coverage facts | ADR-0042, ADR-0052, NEXT-01, LIV-C02 | Continue Cut A to close documented coverage gaps; no boolean completeness. |
| 3. Dimensional coverage | ALREADY_IMPLEMENTED | `DimensionalCoverageService`, `CoverageContribution` | NEXT-01, ADR-0058, ADR-0059 | Reuse. Expand dimensions through Policy-driven need, not enum-first modeling. |
| 4. Evidence admissibility | PARTIALLY_IMPLEMENTED | coverage contribution validation/admissibility, evidence domain, snapshot limitations | ADR-0015, ADR-0048, NEXT-01 | Preserve separation. Any generic admissibility model expansion requires approved design. |
| 5. Historical reconstruction | PARTIALLY_IMPLEMENTED | FactSnapshot, temporal identifier/treatment/withdrawal/campaign/territorial readers | ADR-0052, ADR-0062, ADR-0063 | Continue source-by-source reconstruction; do not use current projections as past. |
| 6. Market readiness | ALREADY_IMPLEMENTED | `MarketReadinessService`, `MarketReadinessPopulationReader` | NEXT-06 | Reuse as read model. No `Animal.market_ready`. |
| 7. Commercial demand | ARCHITECTURAL_DECISION_REQUIRED | None found as production domain | none as accepted production model | HUMAN GATE. Needs Discovery/SPEC/ADR before persistence or API. |
| 8. Supply forecast | ARCHITECTURAL_DECISION_REQUIRED | None found | only implied by product hypothesis | HUMAN GATE. Forecast is projection, not Evaluation/Decision. |
| 9. Supply-demand analysis | ARCHITECTURAL_DECISION_REQUIRED | readiness can count current statuses; no demand/forecast composition | none as accepted production model | DESIGN ONLY until demand and disclosure are approved. |
| 10. Producer-controlled disclosure | ARCHITECTURAL_DECISION_REQUIRED | AuthorizationGrant and Policy sharing exist; no herd-level progressive disclosure model | ADR-0018, ADR-0065, ADR-0068 | HUMAN GATE. Must not improvise consent or cross-tenant visibility. |
| 11. Aggregated buyer visibility | ARCHITECTURAL_DECISION_REQUIRED | no aggregate buyer visibility API found | ADR-0065 blocks indirect fact access | HUMAN GATE. Requires FieldScope, grant scope, purpose, aggregation/redaction decision. |
| 12. Gap analysis | SAFE_EXTENSION | `RuleResult.missing_evidence_types`, reasons, MarketReadiness gap summary | ADR-0048, NEXT-06 | Safe only as derived explanation from Evaluation/RuleResult/readiness; no parallel taxonomy. |
| 13. Future readiness projection | ARCHITECTURAL_DECISION_REQUIRED | None found | no approved production model | HUMAN GATE. Must be explicitly non-decisional with assumptions/versioning. |
| 14. Integration with official sources | ARCHITECTURAL_DECISION_REQUIRED | SISBOV simulator/capture artifacts only; no real official integration | ADR-0058, POST-LIV-03 | HUMAN GATE for real MAPA/IAGRO/SISBOV profiles/contracts. |
| 15. Integration with Odoo | PARTIALLY_IMPLEMENTED | neutral ERP intent, inbox/outbox, simulator tests | POST-LIV-02A/02B, LIV-C08 | Do not change POST-LIV-02B for supply intelligence. Odoo remains operational source. |
| 16. Geodata dependency | PARTIALLY_IMPLEMENTED | CAR client, territorial captures/readers, protected area facts | ADR-0026, T-05D, ADR-0067 | Reuse as facts/evidence/provenance/coverage provider; no normative decisions in Geodata. |
| 17. Dossier/VerificationBundle impact | PARTIALLY_IMPLEMENTED | Dossier, Livestock sections, VerificationBundle interpreter | NEXT-05, ADR-0055, ADR-0060 | Keep eligibility dossier historical/regulatory. Future supply analytics needs separate artifact or clearly non-regulatory section. |

## Detailed Impact Items

### 1. External authoritative animal identities

- Semantic owner: Livestock domain for animal identifiers; Core owns generic Identity/Identifier language.
- Persistence owner: Livestock infrastructure `animal_identifiers`.
- API owner: Livestock API.
- Tenant boundary: `record_owner_organization_id`/`organization_id`; identifiers do not create cross-tenant identity.
- Temporal semantics: current identifiers have valid/attach/deactivate times; event readers reconstruct by `occurred_at` and `recorded_at <= knowledge_cutoff`.
- Authority boundary: `OFFICIAL_SISBOV` and `issuer_source` are assertions/evidence, not Titan official recognition.
- Missing pieces: explicit authority/scheme vocabulary beyond current `IdentifierType`/`issuer_source`; richer provenance than single evidence reference; `known_at` semantics for identifier lifecycle remain event-recorded, not globally known.
- Risks: treating equal official identifiers as automatic identity merge; overwriting identifier history; creating a rival official identity.
- Recommended action: Cut B only if a SPEC proves current fields cannot represent the next approved use case. Otherwise document mapping from authority/scheme/source to current fields and event reconstruction.

### 2. Lifetime historical coverage

- Semantic owner: Livestock application for source-specific coverage composition; Policy decides sufficiency.
- Persistence owner: `coverage_contributions` in Livestock infrastructure plus transfer artifacts.
- API owner: existing coverage contribution API where exposed.
- Tenant boundary: Organization-scoped subject and contribution repositories.
- Temporal semantics: `covered_from`, `covered_until`, `known_at`, `reference_time`, and `knowledge_cutoff` are distinct.
- Authority boundary: coverage states describe known material, not compliance.
- Missing pieces: policy-required coverage profile across all dimensions is not complete for every market; current historical readers still declare limitations for current-state-only sources.
- Risks: collapsing coverage into a percentage/boolean; treating missing treatment records as non-use.
- Recommended action: Cut A, focused on closing specific documented historical reader gaps and tests T0/T1/T2.

### 3. Dimensional coverage

- Semantic owner: Livestock application.
- Persistence owner: `coverage_contributions`.
- API owner: coverage contribution API.
- Tenant boundary: subject and contribution Organization.
- Temporal semantics: intervals are explicit and assessed against required interval.
- Authority boundary: validation/admissibility are input dimensions; they do not emit Decision.
- Missing pieces: no global enum should be introduced; dimension names remain string-based and Policy-driven.
- Risks: taxonomy drift if commercial gaps create a second dimension list.
- Recommended action: reuse existing `DimensionalCoverageService`.

### 4. Evidence admissibility

- Semantic owner: Core for Evidence concepts; Livestock for current coverage contribution admissibility.
- Persistence owner: Core evidence tables and Livestock coverage contributions.
- API owner: Core/Livestock application services depending on resource.
- Tenant boundary: evidence references include Organization and must match owner where required.
- Temporal semantics: admitted material must be selected by valid time and knowledge cutoff when used in historical Evaluation.
- Authority boundary: admissibility allows use in Evaluation; it does not assert truth.
- Missing pieces: generic `EvidenceAdmissibilityAssessment` may still be broader in architecture than current concrete code.
- Risks: accepting source, signature, or capture as truth.
- Recommended action: extend only under NEXT-01-compatible cut.

### 5. Historical reconstruction

- Semantic owner: Core temporal snapshot plus Livestock temporal readers.
- Persistence owner: event log and source-specific repositories.
- API owner: application services that build FactSnapshots.
- Tenant boundary: Organization context filters every source.
- Temporal semantics: `reference_time` asks what period/state; `knowledge_cutoff` limits what could be known.
- Authority boundary: reconstruction produces facts/limitations, not Decision.
- Missing pieces: some sources still expose limitations rather than reconstructable facts.
- Risks: using current projections (`animal_identifiers`, `PropertyStay`) as past.
- Recommended action: continue source-by-source readers per ADR-0062.

### 6. Market readiness

- Semantic owner: Livestock application read model.
- Persistence owner: none for readiness itself in current code.
- API owner: if exposed, Livestock reads; currently service-level evidence exists.
- Tenant boundary: same Organization for context, Decision, and Evaluation.
- Temporal semantics: context includes `reference_time` and `knowledge_cutoff`; mismatches require reassessment.
- Authority boundary: readiness status is operational utility, not DecisionResult or export authorization.
- Missing pieces: supply-demand and buyer visibility are not implemented.
- Risks: persisting readiness on Animal or creating a second decision engine.
- Recommended action: Cut C can complete NEXT-06 only by deriving from existing Decisions/Evaluations.

### 7. Commercial demand

- Semantic owner: not approved.
- Persistence owner: none.
- API owner: none.
- Tenant boundary: unresolved; likely buyer Organization plus explicit relationship/grants.
- Temporal semantics: would need request time, commercial window, policy version, and candidate population cutoff.
- Authority boundary: demand is commercial intent, not Policy.
- Missing pieces: canonical domain name, invariants, persistence/API, authorization, disclosure.
- Risks: mixing market criteria with buyer quantity intent; exposing supplier herd data.
- Recommended action: Cut D DESIGN ONLY, then HUMAN GATE.

### 8. Supply forecast

- Semantic owner: not approved.
- Persistence owner: none.
- API owner: none.
- Tenant boundary: unresolved.
- Temporal semantics: must include generated_at, reference_time, horizon/window, knowledge_cutoff, assumptions/version.
- Authority boundary: projection, not Evaluation, Decision, certificate, or future eligibility.
- Missing pieces: assumptions model, source population, uncertainty/limitations, artifact type.
- Risks: creating `FutureEligibilityDecision` or mutating historical decisions.
- Recommended action: DESIGN ONLY after CommercialDemand/disclosure decisions.

### 9. Supply-demand analysis

- Semantic owner: not approved; likely Livestock product/application analytics.
- Persistence owner: none.
- API owner: none.
- Tenant boundary: unresolved and blocked by buyer/farmer data boundary.
- Temporal semantics: must preserve demand version, policy version, readiness reference, forecast horizon, generated_at.
- Authority boundary: analytical summary, not regulatory conclusion.
- Missing pieces: aggregate query authorization, explainability, redaction, revocation behavior.
- Risks: aggregate leakage and reidentification; silent reinterpretation of RuleResults.
- Recommended action: DESIGN ONLY.

### 10. Producer-controlled disclosure

- Semantic owner: Core authorization/sharing plus Livestock product workflow; not approved for this use case.
- Persistence owner: existing AuthorizationGrant for Policy sharing, but not herd disclosure.
- API owner: none for progressive disclosure.
- Tenant boundary: must be explicit grant/scope/purpose; absence denies.
- Temporal semantics: grant validity, revocation, snapshot mode, and historical access after revocation must be decided.
- Authority boundary: consent/data sharing does not become Policy/Decision.
- Missing pieces: progressive disclosure lifecycle and FieldScope profiles.
- Risks: improvised consent model; broad buyer visibility.
- Recommended action: Cut E ADR/DESIGN ONLY.

### 11. Aggregated buyer visibility

- Semantic owner: not approved.
- Persistence owner: none.
- API owner: none.
- Tenant boundary: cross-Organization by design; RED until ADR.
- Temporal semantics: aggregation must declare data cutoff and membership/population criteria.
- Authority boundary: aggregate operational visibility, not Recognition.
- Missing pieces: query authorization, k-anonymity/minimum counts if desired, redaction, audit.
- Risks: revealing existence/identifiers of animals or producers through counts, filters, or timing.
- Recommended action: HUMAN GATE.

### 12. Gap analysis

- Semantic owner: existing Evaluation/RuleResult and readiness read model.
- Persistence owner: Evaluation persistence; readiness currently derived.
- API owner: existing evaluation/readiness surface if exposed.
- Tenant boundary: same as Evaluation/Decision.
- Temporal semantics: gap is valid only for the Evaluation context and snapshot.
- Authority boundary: reason/gap explains result; it is not separate commercial fact.
- Missing pieces: supply network rollups are not approved.
- Risks: parallel commercial gap taxonomy drifting from RuleResults.
- Recommended action: derive from `RuleResult.reason`, `missing_evidence_types`, evaluation limitations, and MarketReadiness gap summary.

### 13. Future readiness projection

- Semantic owner: not approved.
- Persistence owner: none.
- API owner: none.
- Tenant boundary: unresolved.
- Temporal semantics: forecast window and assumptions are mandatory.
- Authority boundary: non-decisional projection only.
- Missing pieces: assumption/version model, population filters, auditability.
- Risks: contaminating historical Evaluation/Decision.
- Recommended action: HUMAN GATE.

### 14. Integration with official sources

- Semantic owner: source-specific integration profile, not current generic Livestock domain.
- Persistence owner: current external capture artifacts for simulator/source-neutral captures.
- API owner: capture/ingestion APIs where present.
- Tenant boundary: captured material belongs to receiving Organization; official source does not grant cross-tenant access.
- Temporal semantics: captured_at, known_at, validity from source profile.
- Authority boundary: official source is external authoritative source only under approved contract; Titan records evidence and limitations.
- Missing pieces: real MAPA/IAGRO/SISBOV contracts, source profiles, semantics, failure modes.
- Risks: treating simulator or capture as official recognition.
- Recommended action: no real official integration in this cut.

### 15. Integration with Odoo

- Semantic owner: Livestock application neutral ERP contract; Odoo adapter remains infrastructure/integration.
- Persistence owner: outbox/inbox and adapter-owned external receipt records.
- API owner: internal/application adapter, not market supply API.
- Tenant boundary: one integration scope per Organization in first design.
- Temporal semantics: operation identity, delivery attempts, unknown outcome, reconciliation.
- Authority boundary: Odoo is operational, not sanitary or decisional authority.
- Missing pieces: real Odoo target remains design-gated.
- Risks: reading stock movement as medication application proof.
- Recommended action: leave POST-LIV-02B untouched.

### 16. Geodata dependency

- Semantic owner: Livestock/geodata boundary for facts/evidence/provenance/coverage.
- Persistence owner: territorial capture/assertion repositories.
- API owner: territorial capture/read APIs.
- Tenant boundary: Organization-scoped captures and properties.
- Temporal semantics: captured_at/known_at and historical territorial readers.
- Authority boundary: Geodata provides facts/evidence/provenance/coverage; Policy/Evaluation decide compliance.
- Missing pieces: supply analytics dependency contract not approved.
- Risks: introducing `EUDR_COMPLIANT` or `EU_ELIGIBLE` in Geodata.
- Recommended action: consume only through existing facts/Evaluations.

### 17. Dossier/VerificationBundle impact

- Semantic owner: Core Dossier/VerificationBundle; Livestock owns vertical sections.
- Persistence owner: Core dossier persistence.
- API owner: Core verification and Dossier services.
- Tenant boundary: Dossier belongs to issuing Organization and is shared/published only by explicit mechanism.
- Temporal semantics: Dossier freezes Decision/Evaluation snapshot and declared gaps.
- Authority boundary: Dossier explains historical conclusion; forecast is not Decision.
- Missing pieces: supply analytics artifact, if any, is not approved.
- Risks: placing forecast inside eligibility Dossier as if it were regulatory proof.
- Recommended action: do not change Dossier/VerificationBundle semantics. Future supply report should be separate or explicitly non-regulatory.

## Overlaps and Duplicates Avoided

- Did not introduce `Animal.eligible`, `Animal.export_allowed`, `Animal.eu_eligible`, or `Animal.market_ready`.
- Did not create a parallel identity aggregate; current `AnimalIdentifier` plus event reconstruction already covers the first layer.
- Did not create a second gap engine; `RuleResult`, evaluation limitations, coverage assessments, and readiness gap summary already exist.
- Did not create CommercialDemand as Policy; Policy remains criteria, demand remains unapproved commercial intent.
- Did not create forecast as Evaluation or Decision.
- Did not move normative logic into Geodata or Odoo.

## Architecture Conflicts / Human Gates

The following require human approval before implementation:

- Persisted `CommercialDemand`.
- Persisted `SupplyForecast`.
- `SupplyDemandAnalysis` API or persistence.
- Cross-Organization buyer visibility into aggregate or individual supplier data.
- Progressive disclosure lifecycle, consent/data-sharing contract, revocation semantics, and historical access after revocation.
- Real official MAPA/IAGRO/SISBOV integration profile.
- Any change to Dossier, VerificationBundle, Evaluation, Decision, Fact/Evidence, or `knowledge_cutoff` semantics.

## Proposed Incremental Cuts

### CUT A - Lifetime Coverage Completion

Goal: close source-specific coverage and historical reader gaps already identified by NEXT-01/LIV-C02.

Allowed: coverage facts, source-specific historical readers, tests T0/T1/T2, tenant isolation, explicit gaps.

Blocked: commercial demand, forecast, buyer visibility, new aggregate roots.

### CUT B - External Identity Semantics

Goal: only if a SPEC proves `IdentifierType`, `issuer_source`, `evidence_reference`, validity, and event reconstruction are insufficient.

Allowed: narrow authority/scheme/source refinement within Livestock identity model.

Blocked: global animal identity, automatic cross-tenant merge, official integration without contract.

### CUT C - Market Readiness Completion

Goal: complete NEXT-06 as derived read model from existing Evaluation/Decision/Policy.

Allowed: service/API/tests for derived readiness if already approved.

Blocked: readiness persisted on Animal, new decision engine, future projection.

### CUT D - Market Supply Intelligence Design

Goal: design-only concept for CommercialDemand, SupplyForecast, SupplyDemandAnalysis, and GapAnalysis.

Allowed: Discovery/SPEC/ADR material.

Blocked: production code, migrations, API.

### CUT E - Data Sharing / Progressive Disclosure

Goal: ADR/design-only for aggregated buyer visibility and producer-controlled disclosure.

Allowed: alternatives, threat model, FieldScope/GrantScope/Purpose proposal.

Blocked: cross-tenant access implementation.

### CUT F - First Commercial Vertical Slice

Goal: only after Cut D/E approval.

Allowed: smallest end-to-end slice under explicit authorization and disclosure decisions.

Blocked until human approval.
