# ADR-0074 - AI Explanation Governance

**Date:** 2026-09-04
**Status:** ACCEPTED WITH CHANGES
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
- must not originate explanation claims;
- must receive only allow-listed structured claims derived deterministically from canonical Titan outputs;
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
Canonical explanation model
        |
        v
Authorized allowed claims
        |
        v
Need-to-know AI explanation context
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

AI providers MUST NOT receive direct repository access, Domain objects, database handles or tool-execution authority. External or user-supplied source content is untrusted data, never instructions to the provider. Providers MUST NOT execute tools, follow embedded instructions, fetch URLs or perform actions originating from source content under this ADR.

Unvalidated AI output MUST NOT be streamed or partially exposed to the requester before deterministic guard approval.

## Temporal Requirement

Every explanation MUST bind `reference_time` and `knowledge_cutoff`. Later knowledge cannot alter historical Evaluation, Decision, Dossier, VerificationBundle or prior explanation audit.

## Classification And Disclosure

AI-generated explanation MUST inherit or strengthen the classification and disclosure restrictions of every source claim used to produce it. Generation never declassifies information.

The canonical structured explanation remains the source and fallback. If AI is unavailable, provider access is denied, classification is incompatible or guard validation fails, Titan presents canonical explanation material instead of generated text.

## Audit Requirement

Future audit should preserve minimized envelope fields:

- requester and Organization;
- purpose;
- source reference digest;
- DataContract id/version;
- provider profile/version;
- model identifier and model version/revision when exposed by the provider;
- prompt template id/version/digest;
- explanation schema version;
- guard version;
- reference_time and knowledge_cutoff;
- guard result and violation codes;
- output digest when released;
- correlation/idempotency reference when applicable.

Raw prompt/output persistence is denied by default unless a separate retention decision approves it. Provider-side retention, telemetry, abuse logging and secondary use of Titan content are part of the ProviderProfile and DataContract and MUST be explicitly approved.

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
- Structured allowed claims become the boundary between canonical Titan outputs and AI wording/paraphrase.

## Human Decisions Required Before Production Provider

- provider/profile and contractual constraints;
- prompt/output retention;
- DataContract fields and prohibited fields;
- user-visible audiences;
- audit storage model;
- whether any buyer-facing aggregate explanation is allowed.

ADR-0075 proposes the production decision package for provider profile, DataContract and minimized audit storage. Until ADR-0075 and its remaining policy gates are accepted, production provider integration remains blocked.

## Acceptance Criteria

This ADR can be accepted when Product Owner/security agrees that:

- AI remains explanation-only;
- deterministic guard is mandatory before presentation;
- no training/fine-tuning occurs without later ADR;
- prompt/output persistence is deny-by-default;
- provider DataContract and ProcessingActivity are mandatory before production calls.

## Acceptance Note

Accepted with changes by Product Owner on 2026-09-04. Required hardening before production provider/user-visible output:

1. Introduce structured `AIExplanationContext`/allowed claims.
2. Prohibit AI-originated explanation claims.
3. Treat external or user-supplied content as untrusted data, never instructions.
4. Prohibit provider tool execution/actions from source content.
5. Prohibit streaming or partial exposure before deterministic guard approval.
6. Govern provider-side retention, telemetry, abuse logging and secondary use.
7. Preserve provider/model, prompt template, explanation schema and guard versions/digests.
8. Make generated output inherit or strengthen source classifications and disclosure restrictions.
9. Deny direct provider access to repositories, Domain objects or database handles.
10. Keep canonical structured explanation as source and fallback.
