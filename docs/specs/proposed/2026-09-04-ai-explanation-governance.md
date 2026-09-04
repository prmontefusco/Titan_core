# SPEC: AI Explanation Governance For Canonical Titan Outputs

- **Level:** CRITICAL
- **Status:** PROPOSED / POLICY DECISION REQUIRED BEFORE LLM INTEGRATION
- **Owner:** Titan Core + Titan Livestock
- **Date:** 2026-09-04

## Problem

Titan now has deterministic guardrails for future Market Optionality explanations, but no approved governance for sending prompts/context to an AI provider or presenting AI-generated text to users.

The next decision is not how to call a model. The next decision is which protected data, purpose, provider contract, retention, audit and output constraints make AI explanation acceptable without weakening Titan's evidence, privacy and historical semantics.

## Existing Authority

- `DOMAIN.md`: AI may produce Claim or derived result, not authority; reading data does not authorize AI, inference or redistribution.
- `ARCHITECTURE.md`: AI providers are consumers subject to DataContract, ProcessingActivity, Authorization and ClassificationPropagation.
- ADR-0013: prompt, output, embedding, vector, dataset, cache and model artifact preserve classification, purpose, license and restrictions.
- ADR-0070: aggregate analytics inside Titan do not authorize ingestion into external AI systems.
- ADR-0073: LLMs may summarize canonical Market Optionality outputs, but must not create Rules, Facts, Evaluations, Decisions, option states, gaps or forecasts.
- F7 implementation: `MarketOptionExplanationGuardService` validates canonical references and rejects invented or authoritative draft content.

## Scope

Define governance for explanation-only AI over canonical Titan outputs.

Initial candidate use case:

```text
MarketOptionAssessment
    -> canonical explanation context
    -> AI summary draft
    -> deterministic output guard
    -> non-authoritative explanation
```

## Out Of Scope

- AI-created Facts, Evidence, Rules, Evaluations, Decisions, Policies or option states.
- Forecasting, ML prediction or eligibility scoring.
- Embeddings/vector store.
- Training or fine-tuning with Titan data.
- Public/buyer-facing AI output.
- Cross-tenant AI context.
- Provider SDK integration.
- Persistence or migration.

## Required Invariants

- AI explanation is not Decision, Evaluation, Policy, Evidence, Fact, Dossier, VerificationBundle, certificate, forecast or external authority recognition.
- Every AI explanation input must be derived from canonical Titan outputs selected by server-side authorization.
- `reference_time` and `knowledge_cutoff` must be preserved in the prompt context and output metadata.
- Prompt context must be minimized by DataContract and FieldScope.
- Output must pass deterministic guard before any user-visible presentation.
- Output rejection must fail closed; the system may show canonical structured data instead.
- AI output cannot fill missing evidence, reinterpret absence, or create new gap categories.
- Provider response cannot alter historical Evaluation, Decision, Dossier or VerificationBundle.
- Prompt, output, cache, telemetry and provider metadata preserve classification and retention rules.

## Proposed Lifecycle

1. Server resolves authorized canonical source material.
2. Application builds a minimized explanation context.
3. DataContract validates fields, purpose, classification and provider eligibility.
4. AI adapter sends minimized prompt under approved provider profile.
5. Adapter receives draft and provider metadata.
6. Deterministic guard validates source references, allowed codes, state and assertions.
7. Accepted draft is presented as non-authoritative explanation.
8. Rejected draft is not presented; canonical structured explanation remains available.
9. Audit records purpose, source references, provider profile/version, model/version, result, violations and correlation without storing unnecessary sensitive payload.

## Acceptance Criteria

- Approved ADR defines provider boundary, DataContract, retention, audit and failure behavior.
- Contract tests prove AI output cannot be released without passing deterministic guards.
- Tests prove prompt context does not include fields outside the allow-list.
- Tests prove AI output rejection does not alter canonical records.
- Tests prove later knowledge cannot contaminate historical explanation context.

## Policy Gates

### POLICY_GATE: AI Provider And DataContract

**Why required:** selecting a provider and deciding what protected data can leave Titan changes data-processing, retention and security posture.

**Options:**

- A. No external provider; local/mock only until governance is complete.
- B. External provider with no training, no retention where contractually available, region/profile constraints and strict payload minimization.
- C. External provider with richer telemetry/cache.

**Recommended:** B for production after legal/security review; A for automated tests and local development.

### POLICY_GATE: User-Visible AI Output

**Why required:** presenting generated text can change external behavior and user trust.

**Options:**

- A. Internal operator-only explanation.
- B. Producer-facing explanation for own Organization data.
- C. Buyer-facing aggregate explanation after progressive disclosure review.

**Recommended:** A first, then B. C requires separate Market Supply disclosure review.

### POLICY_GATE: Prompt And Output Retention

**Why required:** prompts and outputs can contain protected derived data.

**Options:**

- A. Store only minimal audit envelope and digests.
- B. Store prompt/output payloads for troubleshooting under privileged retention.
- C. Store no AI-specific audit beyond general access logs.

**Recommended:** A; B only for controlled non-production debugging with explicit approval.

## Recommended Next Cut

Create ADR-0074 and design package for AI explanation governance. Do not implement provider integration until ADR-0074 is accepted.
