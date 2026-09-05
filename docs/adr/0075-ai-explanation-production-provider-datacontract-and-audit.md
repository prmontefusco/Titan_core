# ADR-0075 - AI Explanation Production Provider, DataContract And Audit

**Date:** 2026-09-05
**Status:** PROPOSED
**Scope:** Titan Core + Titan Livestock

## Context

ADR-0074 accepted AI Explanation only as presentation over canonical Titan outputs. The local/mock Market Optionality pipeline now proves the guard, allowed claims, minimized prompt payload, provider boundary, synthetic ProviderProfile, audit envelope, canonical fallback, provider-unavailable fallback and classification inheritance.

Production provider integration remains blocked by explicit policy decisions about provider contract, DataContract fields, retention, audit storage and user-visible behavior.

## Problem

Titan needs a production decision package that can unlock a provider adapter without weakening:

- Fact/Evidence/Policy/Evaluation/Decision separation;
- historical immutability;
- Organization isolation;
- DataContract and ProcessingActivity boundaries;
- classification inheritance;
- prompt/output minimization;
- auditability without retaining sensitive raw payloads.

## Decision Proposed

Adopt a production AI Explanation profile only for server-side, explanation-only summaries of canonical Titan outputs.

The first production use case is limited to internal/operator or producer-owned Livestock Market Optionality explanation. Buyer-facing aggregate AI explanation remains outside this ADR and requires Market Supply progressive-disclosure approval.

### Provider Profile

The approved production ProviderProfile MUST declare:

- provider identifier;
- provider profile version;
- model identifier and exposed model version/revision when available;
- allowed processing region or data-location profile;
- provider-side retention;
- telemetry;
- abuse logging;
- secondary use;
- training/fine-tuning use;
- tool execution capability;
- subprocessors, if applicable;
- contractual evidence reference;
- profile digest.

Initial recommendation:

- allow external provider only when contractually configured for no training/fine-tuning on Titan content;
- deny secondary use;
- deny provider tool execution;
- deny prompt/output caching by Titan;
- prefer provider-side retention disabled when available;
- when provider-side abuse logging cannot be fully disabled, treat it as an explicit contractual limitation in the ProviderProfile and block protected production data unless Product/Security approves that limitation.

No provider receives repositories, Domain objects, database handles, raw source payloads, secret values or source-reference aliases.

### DataContract

The production DataContract MUST be versioned and allow-list fields by use case, audience, purpose and classification.

For the initial Market Optionality explanation, allowed provider-visible fields are limited to:

- audience category;
- subject type;
- market purpose label or code approved for disclosure;
- Policy version, without raw Policy id unless separately authorized;
- reference_time;
- knowledge_cutoff;
- option state;
- reversibility;
- structured allowed claims with aliases only;
- reason codes;
- missing evidence type codes;
- limitations;
- context limitations;
- output classification;
- disclosure restrictions;
- prompt template id/version/digest;
- guard version/digest;
- payload digest.

Prohibited provider-visible fields include:

- raw Organization id;
- producer, property, animal or subject identifiers;
- Decision id;
- Evaluation id;
- Policy id;
- raw Evidence;
- raw Facts;
- raw external-source payloads;
- source-reference aliases that can be resolved outside Titan;
- personal data, credentials, tokens or secrets;
- data outside the active Authorization, FieldScope, DataContract or ProcessingActivity.

DataContract validation MUST occur before provider invocation. Missing, unknown or incompatible DataContract fails closed and returns canonical fallback.

### Audit Storage

Production storage MUST persist a minimized AI Explanation audit record, not raw prompt/output by default.

Stored audit material MUST include:

- record owner Organization;
- requester/principal reference or digest as allowed by existing audit policy;
- AccessPurpose / ProcessingActivity;
- DataContract id/version;
- ProviderProfile id/version/digest;
- provider id;
- model identifier and version/revision when exposed;
- prompt template id/version/digest;
- explanation schema version;
- guard version/digest;
- prompt payload digest;
- source-reference digest;
- canonical fallback digest;
- released output digest only when output is released;
- validation accepted flag;
- violation codes;
- output classification;
- disclosure restrictions;
- reference_time;
- knowledge_cutoff;
- requested_at / evaluated_at;
- correlation id;
- idempotency reference when applicable.

Audit storage MUST NOT persist by default:

- raw prompt text;
- raw provider output;
- raw source identifiers;
- raw Evidence or Fact payloads;
- provider exception text;
- credentials, tokens or secrets.

If future troubleshooting requires raw prompt/output capture, it requires a separate retention decision, privileged access profile and non-production or incident-specific scope. This ADR does not approve it.

### Release Behavior

No externally visible AI explanation may be released unless:

- canonical source material was authorized server-side;
- DataContract validation passed;
- ProviderProfile validation passed;
- provider output was fully buffered;
- deterministic guard accepted the complete draft;
- durable minimized audit persistence succeeded.

If any step fails, Titan returns canonical explanation fallback. Provider unavailability, guard rejection and audit persistence failure must not alter canonical Evaluation, Decision, Dossier, VerificationBundle or Market Optionality state.

Unvalidated provider output MUST NOT be streamed.

## Alternatives Considered

### A. Keep local/mock only

Safest and already implemented, but prevents validating real provider behavior for approved audiences.

### B. External provider with strict profile, minimized DataContract and minimized audit

Recommended. It preserves ADR-0074 while allowing a production adapter after concrete provider contract approval.

### C. External provider with raw prompt/output retention

Rejected for the first production cut. It increases privacy and retention risk and requires a separate privileged retention decision.

### D. Direct browser-to-provider integration

Rejected. It bypasses server-side Authorization, DataContract, guard and audit.

### E. Buyer-facing Market Supply AI explanation in the first provider cut

Rejected. Buyer-facing aggregate explanation depends on progressive disclosure, aggregation privacy and cross-tenant semantics outside ADR-0075.

## Consequences

- Production provider work can be split into adapter, persisted audit and API/UI release cuts.
- Concrete provider approval remains a policy decision, not an implementation detail.
- Audit storage gets a concrete minimal schema proposal before migration generation.
- Canonical fallback remains mandatory and usable without AI.
- AI explanation output remains derived, non-regulatory and non-decisional.

## Implementation Gates

Allowed after this ADR is accepted:

- provider profile value object/repository if needed;
- production DataContract validation code;
- minimized audit persistence schema/migration with RLS;
- provider adapter that receives only minimized prompt payload;
- tests for provider unavailable, guard rejection, audit failure and raw payload non-retention.

Still requires separate approval:

- concrete provider contract if retention/telemetry/abuse logging cannot meet the strict profile;
- user-visible API/UI behavior;
- buyer-facing aggregate or cross-tenant AI explanation;
- raw prompt/output retention;
- training, fine-tuning, embeddings or vector store.

## Acceptance Criteria

- Product/Security accepts a concrete ProviderProfile.
- Product/Security accepts the production DataContract field allow-list.
- Architecture accepts minimized audit storage and RLS ownership.
- Tests prove no provider call occurs before DataContract/Profile validation.
- Tests prove no release occurs before guard acceptance and durable audit.
- Tests prove no raw prompt/output/source id/exception text is persisted.
- Tests prove fallback is returned on provider, guard, DataContract, profile or audit failure.

