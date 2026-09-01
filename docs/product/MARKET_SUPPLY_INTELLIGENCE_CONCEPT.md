# Market Supply Intelligence Concept

STATUS: PRODUCT HYPOTHESIS / ARCHITECTURE BASELINE ACCEPTED / NOT AUTHORIZED FOR PRODUCTION

Date: 2026-08-28

Principle:

> Titan does not promise future availability or future eligibility. It provides evidence-based capacity intelligence under explicit context, assumptions, authorization and temporal boundaries.

## 1. Problem Statement

Buyers and frigorificos may need to understand whether a supplier network can potentially satisfy a market, volume, and commercial window before individual transactions are finalized. Producers may need to understand which animals are ready, which are not ready, and which gaps could be resolved without exposing unnecessary private herd data.

Titan is well positioned to support this because it already separates Evidence, Facts, Coverage, Policy, Evaluation, Decision, Readiness, Dossier, and Verification. This concept must not turn market signals into normative rules or commercial interest into regulatory eligibility.

## 2. Actors

- Producer or supplier Organization.
- Buyer, frigorifico, or commercial counterparty Organization.
- Operator/compliance user acting inside an Organization.
- Integration service, such as ERP/Odoo, as operational source or destination.
- External official source, only when a specific approved source profile and contract exist.
- Auditor or verifier, only under explicit publication/sharing/verification scope.

## 3. Producer Value

- See which animals satisfy a specific approved Policy context.
- See explicit gaps without pretending missing records mean negative facts.
- Decide what to disclose progressively.
- Prepare documentation before a commercial window.
- Avoid sending individual animal data before commercial intent and authorization justify it.

## 4. Buyer/Frigorifico Value

- Estimate current capacity under an explicit Policy and context.
- Understand shortages and main gap categories.
- Start commercial conversations with aggregate visibility first.
- Request detailed disclosure only for selected candidates under explicit authorization.
- Avoid confusing Titan internal decisions with official external recognition.

## 5. CommercialDemand

CommercialDemand is a product hypothesis for commercial intent in Titan Livestock.

It is not Policy. Policy answers "which criteria must be satisfied?" CommercialDemand answers "how many subjects are needed, for which purpose, in which window, and under which disclosure constraints?"

It is owned by the buyer/frigorifico Organization. Its existence grants no implicit supplier access.

Possible future fields, not authorized for implementation:

- buyer/context;
- purpose;
- Policy reference and version;
- requested quantity;
- commercial window;
- candidate population constraints;
- disclosure constraints;
- created_at and requested_by;
- Organization and authorization context.

## 6. MarketReadiness

MarketReadiness already exists as a derived read model in Livestock application code. It maps existing Evaluation/Decision/Policy context into operational statuses such as `READY`, `NOT_READY`, `CONDITIONED`, `INDETERMINATE`, `REASSESSMENT_REQUIRED`, and `NOT_EVALUATED`.

It must remain derived. It must not become a permanent Animal attribute.

## 7. SupplyForecast

SupplyForecast is a future projection hypothesis. It is computed on demand by default; immutable snapshots are preserved only when required for reproducibility, shared report, audit history, or explicit analytical artifact.

It is not Decision, Evaluation, certificate, official recognition, or guarantee of future eligibility.

If ever approved, every forecast must preserve:

- generated_at;
- reference_time;
- horizon/window;
- knowledge_cutoff;
- assumptions and assumption version;
- source population;
- Policy/version;
- uncertainty and limitations;
- provenance sufficient to explain the calculation.

No forecast may alter historical Evaluation, Decision, Dossier, or VerificationBundle. Hypothetical corrective actions may appear only as explicit assumptions/scenarios and never as facts or decisions.

## 8. SupplyDemandAnalysis

SupplyDemandAnalysis is a future analytical composition:

```text
CommercialDemand
  + MarketReadiness
  + SupplyForecast
  -> SupplyDemandAnalysis
```

Example analytical outputs could include ready now, potential in window, resolvable gap, indeterminate, estimated capacity, and estimated shortage. These values would be analytical summaries, not regulatory conclusions.

## 9. GapAnalysis

GapAnalysis should be derived from existing RuleResults, missing evidence types, coverage assessments, evaluation limitations, and MarketReadiness gap summary.

It must not reinterpret RuleResult silently or create a parallel commercial truth. A gap is always scoped to a Policy, Evaluation context, population, time, source coverage, and authorization boundary.

## 10. Progressive Disclosure

Progressive disclosure should start with aggregate visibility when authorized. The governing principle is aggregate-first, identity-last.

- number of participating properties;
- number of animals considered;
- readiness counts by status;
- high-level gap categories.

It should not automatically reveal:

- producer identity;
- property identity;
- Animal ID;
- individual sanitary data;
- raw evidence;
- Dossier content.

Detailed candidate disclosure should require explicit commercial intent, candidate selection, authorization, FieldScope, purpose, audit, and revocation semantics. `MARKET_SUPPLY_AGGREGATE_ASSESSMENT` and `MARKET_SUPPLY_CANDIDATE_DISCLOSURE` are distinct purposes and the first never escalates silently into the second.

## 11. Privacy

Buyer access to a supplier network is not implied by commercial relationship, identifier coincidence, Policy sharing, or aggregate curiosity. Organization isolation remains the default.

Accepted architecture:

- producer participation is explicit opt-in by default;
- absence of a valid grant denies access;
- aggregation privacy requires configurable floors and dynamic risk assessment;
- repeated-query and differencing protection is required before production cross-Organization aggregate API;
- revocation blocks future access but does not rewrite history;
- export and redistribution are denied by default.

## 12. Authority Boundaries

Titan is not MAPA, IAGRO, SISBOV, a certifier, a sanitary authority, an export authority, a bank, an insurer, or a marketplace authority.

Official identities and source responses are external evidence or authoritative assertions only under approved contract and source profile. Titan may evaluate evidence under Policy and issue internal Decisions where it has authority, but it does not promise external recognition.

Geodata provides facts/evidence/provenance/coverage. Odoo provides operational context. Sensors provide observations. None of them decide compliance.

## 13. Temporal Semantics

All analysis must preserve:

- `reference_time`: the reality/time period being asked about;
- `knowledge_cutoff`: what could be known for the analysis;
- generated_at: when the analysis was produced;
- Policy/version;
- source population criteria;
- explicit gaps, limitations, inaccessible data, and unknown external results.

Later knowledge must not contaminate historical Evaluation or Decision.

## 14. Non-goals

- No marketplace.
- No payments.
- No credit, insurance, or financial scoring.
- No blockchain.
- No mobile app.
- No real MAPA/IAGRO/SISBOV integration without approved contract.
- No new commodity/generalized agriculture vertical.
- No ML prediction engine in this phase.
- No universal compliance score.
- No eligibility booleans on Animal.
- No invented EU/Corea/Japan normative rules.

## 15. Risks

- Aggregate buyer visibility can leak producer or herd information.
- Forecast can be misread as future eligibility.
- Commercial demand can be confused with Policy.
- Gap analysis can drift from governed RuleResults.
- ERP or sensor data can be overtrusted as sanitary truth.
- Official source captures can be overpresented as official recognition.
- Revocation and historical disclosure may be underdefined.

## 16. Open Questions

- What is the first user and transaction where aggregate readiness creates enough value to justify CUT F?
- Which FieldScope/GrantScope profiles are acceptable for aggregate buyer visibility?
- What concrete AggregationPrivacyPolicy profile is acceptable before production cross-Organization API?
- What audit tier and retention profile are required for aggregate queries?
- Which technical representation should persist `CommercialDemand`, `CandidatePopulationSnapshot`, and `SupplyIntelligenceReport` in the first production cut?
- What is the first approved official source profile, if any?

## 17. Proposed Validation Experiments

- Interview buyers/frigorificos using static mock reports, with no production data.
- Ask producers which aggregate disclosure levels feel acceptable before commercial intent.
- Prototype a non-production spreadsheet/report from synthetic data to validate vocabulary.
- Test whether existing MarketReadiness statuses answer the first buyer question without forecast.
- Validate whether gaps derived from RuleResults are understandable without exposing individual facts.
- Run a legal/privacy review of progressive disclosure before any API or persistence design.
