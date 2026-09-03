# Market Optionality Temporal Readiness - Phased Plan

**Status:** PROPOSED / NO BUILD AUTHORIZED  
**Date:** 2026-09-03  
**Input documents:** ADR-0041, ADR-0044, ADR-0052, ADR-0061, ADR-0069, ADR-0070, ADR-0071, ADR-0072, NEXT-05, NEXT-06, NEXT-07.

## F0 - Discovery And Semantic Validation

**Goal:** establish whether Market Optionality is a distinct derived concept or a duplicate of MarketReadiness.

**Scope:** architecture analysis, concept document, impact assessment, ADR-0073 proposed, this plan.

**Out of scope:** code, persistence, API, UI, worker, migration.

**Acceptance criteria:** Product Owner can answer whether to accept ADR-0073 and authorize F1.

**Stop condition:** conflict with `DOMAIN.md` or accepted ADRs.

## F1 - Pure MarketOptionAssessment Projection

**Goal:** produce a transient application-only assessment from existing canonical inputs.

**Scope:** value objects and pure service accepting explicit Evaluation/Decision/RuleResult/Coverage material; synthetic policies only; no repository.

**Domain changes:** none to Core. Livestock may define projection states if ADR-0073 is accepted.

**Application changes:** new small module under `packages/livestock_application`, or extension of `market_readiness.py` if that proves simpler.

**Infrastructure changes:** none.

**Migration:** none.

**Tests:** same facts/different policy, different facts/same policy, missing evidence, policy unavailable, policy mismatch, immutable historical Evaluation/Decision, no Animal booleans.

**Risks:** duplicate taxonomy with MarketReadiness; state names overclaiming.

**Acceptance criteria:** optionality states remain derived, explainable and distinct from Evaluation/Decision.

**Stop condition:** implementation requires persisted lifecycle or new regulatory semantics.

## F2 - Multi-Market Optionality Report

**Goal:** assess one subject across multiple market purposes using existing policy/readiness contracts.

**Scope:** transient report listing market purposes, option states, reasons and limitations.

**Out of scope:** country-specific services, real external policy ingestion, global market registry.

**Tests:** EU/US/China synthetic profiles, unsupported market, ambiguous Policy, one market policy version changes without changing others.

**Stop condition:** need to formalize `Market`/`Jurisdiction` beyond existing purpose strings.

## F3 - Policy Change Impact Integration

**Goal:** connect optionality to NEXT-07 impact analysis without re-executing rules automatically.

**Scope:** classify potential optionality impact from Policy V1 -> V2 over existing conclusions.

**Out of scope:** persistent NormativeReevaluationPlan, worker execution, notification.

**Tests:** V1 open -> V2 unknown; V1 open -> V3 incompatible; unrelated market unchanged.

**Stop condition:** operational re-evaluation needs lifecycle, approval, retention or async processing.

## F4 - Market Option Preservation Warnings

**Goal:** explain known compliance consequences of proposed or recorded events.

**Scope:** deterministic explanation tied to Policy/Rule; treatment/movement/documentary examples with synthetic data.

**Out of scope:** clinical recommendations, blocking veterinary care, optimization advice, LLM-generated checklists.

**Tests:** welfare boundary statement, reversible vs irreversible categories, no recommendation to omit facts.

**Stop condition:** UI/operational timing changes clinical or compliance workflow semantics.

## F5 - Supply Readiness Aggregation

**Goal:** aggregate optionality/readiness under current knowledge for authorized populations.

**Scope:** compose with CandidatePopulationSnapshot and MarketReadiness; keep unknown/inaccessible/excluded/evaluated counts explicit.

**Out of scope:** forecast, CommercialDemand persistence, detailed candidate disclosure.

**Tests:** no denominator manipulation, no global Animal lookup, privacy suppression, tenant isolation.

**Stop condition:** privacy profile or grant scope needs new policy.

## F6 - Dossier And VerificationBundle Integration

**Goal:** materialize optionality explanation only when linked to canonical inputs.

**Scope:** optional Livestock section in existing Dossier or separate analytical artifact, to be decided.

**Out of scope:** new Dossier type, forecast-as-Decision, public certification claim.

**Tests:** offline verification, no historical rewrite, no forecast inside eligibility Dossier.

**Stop condition:** artifact semantics diverge from Dossier/VerificationBundle invariants.

## F7 - AI Explanation Layer

**Goal:** allow AI to summarize canonical optionality outputs.

**Scope:** explanation-only layer over structured Titan results.

**Out of scope:** AI-created Facts, Rules, Evaluations, Decisions, option states, forecasts or evidence.

**Tests:** output guards, source-reference preservation, no invented gap.

**Stop condition:** AI output becomes authoritative or user-visible without canonical backing.

## Recommended Next Cut

After ADR-0073 review, authorize **F1 only**:

```text
MarketOptionAssessment as a pure transient projection
over synthetic Evaluation/Decision/RuleResult/Coverage inputs.
```

No persistence, API, UI, Market Supply forecast or cross-tenant behavior should enter F1.

