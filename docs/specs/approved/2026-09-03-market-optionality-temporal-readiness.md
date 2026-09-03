# SPEC: Market Optionality, Temporal Compliance and Future Market Readiness

- **Level:** CRITICAL
- **Status:** F1 ACCEPTED AND IMPLEMENTED
- **Decision:** PROCEED WITH CHANGES
- **Owner:** Titan Livestock
- **Date:** 2026-09-03

## Problem

Titan needs to answer not only whether a subject is eligible now under a selected Policy, but which market options remain preserved, at risk, unknown or closed under policies currently known to Titan and explicit temporal coordinates.

## Existing Capabilities To Reuse

- `Evaluation`, `Decision`, `RuleResult`, `FactSnapshot` and `NormativeBasisSnapshot`;
- ADR-0041/0044 market purpose and derived matrix semantics;
- ADR-0052 valid time vs knowledge time;
- ADR-0061 temporal normative basis selection;
- NEXT-05 Dossier extension by vertical section;
- NEXT-06 `MarketReadiness`;
- NEXT-07 transient market change impact;
- ADR-0069/0070/0071/0072 Market Supply analytics, disclosure and audit boundaries.

## Proposed Minimal Domain Model

`MarketOptionAssessment` is a Livestock application/domain projection. It is not an aggregate root in the first cut and has no persistence by default.

Conceptual fields:

- Organization;
- subject reference;
- market purpose/profile;
- Policy id/version;
- `reference_time`;
- `knowledge_cutoff`;
- optional target window;
- source Evaluation/Decision references;
- option state;
- reason codes;
- missing evidence types;
- coverage limitations;
- reversibility classification;
- result boundary;
- canonical digest when materialized.

Initial conceptual states:

- `OPTION_OPEN`;
- `OPTION_AT_RISK`;
- `MISSING_EVIDENCE`;
- `UNKNOWN`;
- `POLICY_UNAVAILABLE`;
- `REASSESSMENT_REQUIRED`;
- `TEMPORARILY_INCOMPATIBLE`;
- `IRREVERSIBLY_INCOMPATIBLE`;
- `NOT_EVALUATED`.

Final state names require ADR acceptance. They must remain distinct from `DecisionResult`, `EvaluationOutcome`, `MarketEligibilityStatus` and `MarketReadinessStatus`.

## Invariants

- Market optionality is not a Decision.
- Market optionality is not future eligibility.
- UNKNOWN is not INELIGIBLE.
- MISSING_EVIDENCE is not FAILED.
- POLICY_UNAVAILABLE is not NON_COMPLIANT.
- `reference_time` and `knowledge_cutoff` are mandatory.
- Policy/version changes create new assessments or re-evaluations; they do not alter historical records.
- No field is added to Animal.
- No country-specific service is created.
- No LLM can create Rule, Evaluation, Decision or option state.

## Phased Execution Plan

| Phase | Goal | Scope | Out of Scope | Tests | Stop Condition |
|---|---|---|---|---|---|
| F0 | Discovery and semantic validation | ADR, concept, impact assessment, synthetic scenario | Code | Document review | ADR rejected or concept conflicts with DOMAIN.md |
| F1 | Pure optionality projection | Application-only value objects/service over provided Evaluation/Decision/coverage | Persistence, API, UI, Market Supply | Same facts/different policy, missing evidence, unknown, immutable history | Need new persisted lifecycle |
| F2 | Multi-market optionality report | Evaluate one subject across multiple market purposes using existing policy readers | Global lookup, country branches | EU/US/CN synthetic policies, unsupported market | Need real policy catalog semantics |
| F3 | Policy change impact integration | Extend NEXT-07 outputs with optionality impact categories | Worker/re-evaluation execution | V1/V2/V3 preserved | Need persistent plan approval |
| F4 | Option preservation warnings | Pre/post event impact explanation for treatments/movements | Clinical recommendation or blocking veterinary action | Treatment risk, welfare non-overridable statement | Need UX/policy for intervention timing |
| F5 | Supply readiness aggregation | Compose optionality with Candidate Population and MarketReadiness | Forecast, CommercialDemand persistence | Aggregate unknown/inaccessible/excluded counts | Need privacy profile changes |
| F6 | Dossier/VerificationBundle section | Optionality section referencing canonical Evaluation/Decision inputs | New dossier type | Offline verification | Need external sharing semantics |
| F7 | AI explanation layer | LLM summarizes canonical results only | LLM decisions/rules | Prompt/output guards | Need approved AI governance |

## Canonical Synthetic Scenario

Use fully synthetic data:

- Animal A, born 2026-01-10;
- Farm A -> Farm B -> Farm C;
- treatments T1/T2;
- movement evidence complete;
- origin evidence complete;
- feed evidence partial;
- evaluate against `EU_POLICY_V1`, `US_POLICY_V4`, `CHINA_POLICY_V2`;
- later introduce `EU_POLICY_V2`.

Expected proof:

- EU v1 can be `OPTION_OPEN`;
- EU v2 can become `UNKNOWN_DUE_TO_NEW_EVIDENCE_REQUIREMENT`;
- US and China remain unchanged;
- facts and prior Evaluations/Decisions are not rewritten.

## Migration Considerations

No migration for F1. Future persistence requires ADR or accepted plan covering RLS, append-only semantics, retention, digest, idempotency and historical reconstruction.

## API Considerations

No API for F1. A future endpoint requires:

- Organization-scoped authorization;
- mandatory temporal coordinates;
- contract tests;
- no-store if sensitive;
- uniform non-visibility semantics where applicable;
- no global Animal lookup.

## Testing Strategy

Plan tests for:

- same facts + different policy;
- different facts + same policy;
- different `knowledge_cutoff`;
- different `reference_time`;
- target window;
- missing/inaccessible/contradictory evidence;
- policy unavailable/expired/ambiguous;
- Organization isolation;
- historical reproducibility;
- no mutation of old Evaluation/Decision/Dossier/VerificationBundle;
- no opaque score.

## Recommendation

**PROCEED WITH CHANGES.**

ADR-0073 was accepted for F1 only. The first BUILD is limited to pure optionality projection over existing canonical objects and synthetic policies, no persistence, no API, no UI and no Market Supply forecast.
