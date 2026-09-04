# ADR-0073 - Temporal Market Optionality and Policy-Versioned Market Readiness

**Date:** 2026-09-03  
**Status:** ACCEPTED
**Scope:** Titan Livestock; future interaction with Market Supply

## Context

ADR-0041 defines market eligibility as a relationship between a subject, a market purpose and a versioned Policy. ADR-0044 keeps the market matrix as a derived read. ADR-0052 separates `reference_time` from `knowledge_cutoff`. ADR-0061 requires temporal normative basis selection before Market Eligibility. NEXT-06 implements `MarketReadiness` as a derived read model over existing Evaluation/Decision records. NEXT-07 implements transient market change impact analysis without rewriting history. ADR-0069 to ADR-0072 define Market Supply as non-regulatory aggregate analytics with progressive disclosure, audit and privacy gates.

The next product question is whether an animal preserves market options under currently known policies and what could put those options at risk.

## Problem

The existing system can say whether a specific Evaluation/Decision exists and whether it is usable for readiness. It does not yet name the higher-level concept of preserving a market option over time, distinguish reversible from irreversible loss of optionality, or define how future target windows relate to known policies without becoming a forecast of regulatory approval.

## Decision Proposed

Introduce **Market Optionality** as a Livestock-owned derived assessment, initially named `MarketOptionAssessment`.

`MarketOptionAssessment`:

- is not `Evaluation`;
- is not `Decision`;
- is not `MarketReadiness`;
- is not a certificate;
- is not export authorization;
- is not official recognition;
- is not future eligibility.

It composes existing canonical material: Policy/version, RuleResult, Evaluation, Decision, FactSnapshot, NormativeBasisSnapshot, dimensional coverage and explicit limitations.

The first implementation, if approved, must be application-only and transient. It must not create a new aggregate root, table, migration, endpoint, worker, frontend surface or cross-tenant query.

## Domain Semantics

Market optionality answers:

> Under the selected Policy/version and temporal context, does the available canonical material preserve, limit, suspend, close or leave unknown this market option?

It must distinguish:

- open option;
- option at risk;
- missing evidence;
- unknown due to insufficient knowledge;
- policy unavailable or ambiguous;
- re-assessment required due to context/policy mismatch;
- temporary incompatibility;
- irreversible incompatibility;
- not evaluated.

Final names are intentionally not accepted by this ADR until F1 proves the mapping against existing RuleResult/Evaluation/Decision semantics.

## Temporal Model

Every optionality assessment MUST bind:

- Organization;
- subject reference;
- market purpose/profile;
- Policy id;
- Policy version;
- `reference_time`;
- `knowledge_cutoff`;
- target window when evaluating future readiness under current knowledge;
- evaluation time if the assessment is materialized.

Re-execution with different temporal coordinates is a distinct semantic query.

## Policy Versioning And Re-Evaluation

Policy changes do not mutate facts or historical conclusions. A new Policy version may produce:

- a new optionality assessment;
- a new Evaluation/Decision through an approved re-evaluation process;
- a transient impact assessment;
- an approved NormativeReevaluationPlan in a future cut.

Historical Evaluation, Decision, Dossier and VerificationBundle records remain immutable.

## Market Supply Integration

Market Supply may later aggregate optionality/readiness under current knowledge, but only through the ADR-0069/0070/0071/0072 pipeline:

```text
authorization
-> CandidatePopulationSnapshot
-> MarketReadiness / optional MarketOptionAssessment
-> GapAnalysis
-> DisclosureDecision
-> durable audit
-> public aggregate response
```

Unknown, inaccessible, excluded and not evaluated counts must remain explicit internally. Denominator manipulation is prohibited.

## Dossier And VerificationBundle

A future Dossier section may include optionality only as a derived, non-certifying explanation linked to canonical Evaluation/Decision inputs. Forecast or future readiness cannot be inserted into an eligibility Dossier as if it were a Decision.

VerificationBundle should be reused if a material optionality artifact is approved; no parallel verifier is authorized.

## Audit Requirements

Stored, shared or externally visible optionality assessments require audit sufficient to reconstruct actor, Organization, purpose, market, Policy/version, canonical input references, temporal coordinates, unknowns, exclusions, option state and limitations.

Audit payload minimization applies.

## Security And Privacy

No optionality feature may introduce global Animal lookup, cross-tenant visibility, buyer access to producer data, or disclosure outside ADR-0070/0071 controls. Aggregate optionality remains a disclosure surface, not simple `GROUP BY`.

## AI Boundary

LLMs may summarize canonical outputs in a future approved layer. They must not create Rules, infer Facts, decide eligibility, classify optionality, fill gaps or convert missing evidence into positive or negative conclusions.

## Alternatives Considered

1. Reuse `MarketReadiness` only. Rejected because readiness tells whether an existing conclusion is usable, not whether a market option is preserved, at risk or irreversibly closed.
2. Add new `DecisionResult` values. Rejected because option states are projections, not Decisions.
3. Create country-specific services. Rejected because ADR-0041 requires market/policy generality and avoids EU-specific architecture.
4. Persist `MarketOption` as an aggregate immediately. Rejected as premature without lifecycle, state transitions or production retention requirements.
5. Use an eligibility score. Rejected because it is opaque and can collapse unknown, missing evidence and incompatibility.

## Risks

- option state mistaken for authorization;
- future readiness mistaken for prediction;
- over-modeling before F1 proves mappings;
- policy-change impact triggering uncontrolled re-evaluation;
- aggregate optionality leaking membership;
- clinical decisions being distorted by commercial optionality warnings.

## Migration Strategy

No migration in F1. If persistence becomes necessary, create a separate accepted ADR or design package defining ownership, RLS, append-only rules, retention, canonical digest and historical verification.

## Acceptance Criteria

This ADR can be accepted when:

- optionality remains distinct from Evaluation, Decision and Readiness;
- `reference_time` and `knowledge_cutoff` are mandatory;
- UNKNOWN, MISSING_EVIDENCE and INCOMPATIBLE remain distinct;
- Policy changes create new assessments/re-evaluations, never historical rewrites;
- first BUILD is application-only, synthetic and non-persistent;
- Market Supply integration remains behind disclosure/audit/privacy gates;
- AI is limited to explanation over canonical results.

## Acceptance Note

Accepted by Product Owner on 2026-09-03 for F1 only. This acceptance authorizes a pure, transient, application-only `MarketOptionAssessment` projection over existing canonical material. It does not authorize persistence, API, UI, worker, forecast, CommercialDemand persistence, official integrations, cross-tenant disclosure, new Dossier semantics or changes to Evaluation/Decision.

F2 was accepted by Product Owner on 2026-09-03 under the same application-only boundary. This authorizes a transient `MultiMarketOptionReport` over explicit market purposes supplied by the caller. It does not authorize a real market catalog, country-specific services, global Animal lookup, persistence, API, UI, worker, forecast, CommercialDemand persistence, official integrations, cross-tenant disclosure, Dossier changes or changes to Evaluation/Decision.

F3 was accepted by Product Owner on 2026-09-03 under the same application-only boundary. This authorizes a transient `MarketOptionChangeImpactReport` that composes NEXT-07 `MarketChangeImpactAssessment` with existing optionality assessments. It does not authorize a persisted `NormativeReevaluationPlan`, worker execution, notification, API, UI, forecast, automatic re-evaluation, Dossier changes or changes to Evaluation/Decision.

F4 was accepted by Product Owner on 2026-09-03 under the same application-only boundary. This authorizes transient option-preservation warnings over supplied before/after optionality assessments and synthetic event contexts. It does not authorize clinical advice, operational blocking, UI workflow timing, persistence, API, worker, notification, forecast, Dossier changes or changes to Evaluation/Decision.

F5 was accepted by Product Owner on 2026-09-03 within the already approved Market Supply application boundary. This authorizes an internal aggregation that composes authorized `CandidatePopulationSnapshot`, canonical `MarketReadinessReport` and supplied `MarketOptionAssessment` material. It does not authorize new privacy thresholds, public release, forecast, CommercialDemand persistence, detailed disclosure, API changes, Dossier changes or changes to Evaluation/Decision.

F6 was accepted by Product Owner on 2026-09-04 within the existing Dossier/VerificationBundle boundary. This authorizes an optional Livestock vertical section for `market_optionality` linked to canonical Decision/Evaluation/Policy inputs and reuse of the existing VerificationBundle interpreter. It does not authorize a new Dossier type, forecast inside an eligibility Dossier, public certification claim, persistence changes, API changes, sharing/publication changes or changes to Evaluation/Decision.
