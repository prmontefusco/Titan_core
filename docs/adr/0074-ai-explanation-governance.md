# ADR-0074 - AI Explanation Governance

**Date:** 2026-09-04  
**Status:** PROPOSED  
**Scope:** Titan Core + Titan Livestock

## Context

Titan's architecture permits AI to produce derived Claims or explanations, but never authority. `DOMAIN.md` states that AI cannot choose result or authority and that reading data does not authorize AI, inference or redistribution. `ARCHITECTURE.md` requires AI providers to be consumers subject to DataContract, ProcessingActivity, Authorization and ClassificationPropagation. ADR-0013 requires prompt, output, embedding, dataset, cache and model artifacts to preserve classification and restrictions.

Market Optionality F7 implemented a deterministic guard for future AI explanations, but it intentionally did not integrate an LLM provider, prompt lifecycle, user-visible output or persistence.

## Problem

Without an explicit governance decision, a future implementation could call an AI provider with protected context, retain prompts, present generated text as authoritative, or bypass deterministic guards.

## Decision Proposed

Adopt AI explanation as an application/infrastructure capability constrained by canonical Titan outputs.

AI explanation:

- may summarize canonical outputs selected by server-side authorization;
- must preserve source references and temporal coordinates;
- must pass deterministic output guards before presentation;
- must be governed by versioned DataContract, ProcessingActivity and provider profile;
- must fail closed when classification, authorization, provider eligibility or guard validation is unavailable.

AI explanation must not:

- create Facts, Evidence, Rules, Policies, Evaluations, Decisions, Dossiers, VerificationBundles, forecasts or option states;
- fill gaps or infer absence;
- decide eligibility or market readiness;
- claim certification, export authorization or official recognition;
- train or fine-tune models with Titan data unless a later ADR explicitly approves it.

## Required Pipeline

```text
Authorized canonical source
        |
        v
Minimized explanation context
        |
        v
DataContract / ProcessingActivity validation
        |
        v
Provider adapter
        |
        v
Draft output
        |
        v
Deterministic guard
        |
        v
Non-authoritative presentation or canonical fallback
```

## Temporal Requirement

Every explanation MUST bind `reference_time` and `knowledge_cutoff`. Later knowledge cannot alter historical Evaluation, Decision, Dossier, VerificationBundle or prior explanation audit.

## Audit Requirement

Future audit should preserve minimized envelope fields:

- requester and Organization;
- purpose;
- source reference digest;
- DataContract id/version;
- provider profile/version;
- model/version when applicable;
- reference_time and knowledge_cutoff;
- guard result and violation codes;
- output digest when released;
- correlation/idempotency reference when applicable.

Raw prompt/output persistence is denied by default unless a separate retention decision approves it.

## Alternatives Considered

1. No AI support. Safe, but loses readability benefits once canonical outputs become complex.
2. Direct provider calls from UI. Rejected because it bypasses server-side authorization, DataContract and audit.
3. Store prompts/outputs by default. Rejected because prompts and outputs can contain protected derived data.
4. Let AI generate explanations without deterministic guard. Rejected because fluent text can invent gaps, authority or conclusions.
5. Use local/mock AI only. Accepted for tests and development, insufficient as production governance.

## Consequences

- F7 guard becomes a mandatory application gate for future Market Optionality AI summaries.
- Provider integration remains blocked until DataContract/provider/retention decisions are approved.
- User-visible output remains blocked until API/UI external behavior is approved.
- Canonical structured explanation remains the fallback when AI is unavailable or rejected.

## Human Decisions Required Before Production Provider

- provider/profile and contractual constraints;
- prompt/output retention;
- DataContract fields and prohibited fields;
- user-visible audiences;
- audit storage model;
- whether any buyer-facing aggregate explanation is allowed.

## Acceptance Criteria

This ADR can be accepted when Product Owner/security agrees that:

- AI remains explanation-only;
- deterministic guard is mandatory before presentation;
- no training/fine-tuning occurs without later ADR;
- prompt/output persistence is deny-by-default;
- provider DataContract and ProcessingActivity are mandatory before production calls.
