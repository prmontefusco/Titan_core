# ADR-0075 - AI Explanation Production Provider, DataContract And Audit

**Date:** 2026-09-05
**Status:** ACCEPTED WITH CHANGES
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

Authorization to access canonical Titan outputs does not by itself authorize processing by an external AI provider. External provider invocation requires an approved ProcessingActivity plus Organization/purpose/provider-compatible processing authorization.

### Provider Profile

The approved production ProviderProfile MUST declare:

- provider identifier;
- provider profile version;
- lifecycle state;
- effective_from / effective_until;
- approved_at / approved_by when approved;
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

ProviderProfile lifecycle states are:

- `DRAFT`;
- `APPROVED`;
- `SUSPENDED`;
- `REVOKED`;
- `SUPERSEDED`.

Only `APPROVED` profiles effective at the provider invocation and release recheck instants may be used. Profile suspension, revocation or supersession blocks new provider calls and new releases without rewriting previous audit records.

Initial recommendation:

- allow external provider only when contractually configured for no training/fine-tuning on Titan content;
- deny secondary use;
- deny provider-managed tools, browsing, retrieval, grounding, code execution, file search, persistent memory, connectors, agentic actions and any external side-effect capability;
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
- provider-safe reason aliases;
- provider-safe missing-evidence aliases;
- provider-safe limitation aliases;
- provider-safe context-limitation aliases;
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
- internal reason, evidence, limitation or market vocabulary when the canonical code reveals information outside the approved disclosure scope;
- personal data, credentials, tokens or secrets;
- data outside the active Authorization, FieldScope, DataContract or ProcessingActivity.

Canonical internal vocabulary MUST be projected into provider-safe aliases when the original code reveals information outside the approved disclosure scope. The provider receives the alias projection, not the privileged vocabulary.

DataContract validation MUST occur before provider invocation. Missing, unknown or incompatible DataContract fails closed and returns canonical fallback.

### Structured Draft Schema

Production providers MUST return a versioned structured `AIExplanationDraft` shape, not unconstrained free text. The initial schema includes sections with allowed `claim_refs` and text. The deterministic guard validates that every claim reference exists in the allowed claims context, that no section introduces unsupported material and that the full draft passes text and assertion checks before release.

### Audit Storage

Production storage MUST persist a minimized AI Explanation audit record, not raw prompt/output by default.

Stored audit material MUST include:

- record owner Organization derived from the authorized canonical explanation context;
- requester/principal opaque audit reference as allowed by existing audit policy;
- acting Organization/context when distinct from record owner;
- AccessPurpose / ProcessingActivity;
- processing authorization reference or digest;
- DataContract id/version;
- ProviderProfile id/version/digest;
- provider id;
- model identifier and version/revision when exposed;
- prompt template id/version/digest;
- explanation schema version;
- guard version/digest;
- prompt payload digest;
- source-reference digest or opaque audit reference according to sensitivity;
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

`record_owner_organization_id` MUST be derived from the authorized canonical explanation context. It MUST NOT be supplied or overridden by the caller, UI, provider adapter or external provider.

Digests used for canonical integrity and tokens used for pseudonymous audit correlation are distinct concepts. Identifier-derived audit references MUST use an approved non-reversible keyed derivation, such as a domain-separated HMAC with key version, rather than an unkeyed hash when linkability or enumeration is material.

Audit storage MUST NOT persist by default:

- raw prompt text;
- raw provider output;
- raw source identifiers;
- raw Evidence or Fact payloads;
- provider exception text;
- credentials, tokens or secrets.

If future troubleshooting requires raw prompt/output capture, it requires a separate retention decision, privileged access profile and non-production or incident-specific scope. This ADR does not approve it.

### Idempotency And Replay

AI explanation generation is nondeterministic presentation. Idempotency prevents duplicate business effects and correlates audit, but it does not guarantee byte-identical replay unless a released presentation artifact is persisted.

This ADR does not require persisting released explanation text. If exact textual replay becomes required, Titan must introduce a separate controlled derived artifact for the released presentation, distinct from raw provider output, with its own classification, retention, access and audit rules.

### Release Behavior

No externally visible AI explanation may be released unless:

- canonical source material was authorized server-side;
- DataContract validation passed;
- ProviderProfile validation passed;
- provider processing authorization passed;
- provider output was fully buffered;
- deterministic guard accepted the complete draft;
- durable minimized audit persistence succeeded.

If any step fails, Titan returns canonical explanation fallback. Provider unavailability, guard rejection and audit persistence failure must not alter canonical Evaluation, Decision, Dossier, VerificationBundle or Market Optionality state.

AI audit failure discards AI output. Canonical fallback presentation must still pass the normal authorization and audit requirements of the canonical explanation path; AI fallback cannot be used to bypass those gates.

Audit records describe `RELEASE_APPROVED` or `NOT_RELEASED`, not guaranteed delivery to the requester. HTTP/network delivery is a separate operational observation and must not be represented as user receipt unless independently evidenced.

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
- ProviderProfile, DataContract and processing authorization become separate gates before provider invocation.
- Exact textual replay remains a separate decision unless released presentation artifact storage is approved.

## Implementation Gates

Allowed after this ADR is accepted:

- provider profile value object/repository if needed;
- production DataContract validation code;
- processing authorization value object/service if needed;
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
- Product/Security accepts the processing authorization semantics for external provider invocation.
- Architecture accepts minimized audit storage and RLS ownership.
- Tests prove no provider call occurs before DataContract/Profile validation.
- Tests prove record owner is derived and cannot be caller/provider supplied.
- Tests prove provider-safe aliases hide privileged internal vocabulary.
- Tests prove pseudonymous audit references do not use unkeyed identifier hashes where enumeration/linkability is material.
- Tests prove no release occurs before guard acceptance and durable audit.
- Tests prove no raw prompt/output/source id/exception text is persisted.
- Tests prove fallback is returned on provider, guard, DataContract, profile or audit failure.

## Acceptance Note

Accepted with changes by Product Owner on 2026-09-05. Required changes incorporated:

1. Idempotency/replay semantics explicitly state that byte-identical replay requires a persisted released presentation artifact.
2. `record_owner_organization_id` is derived from canonical explanation context and cannot be caller/provider supplied.
3. External provider invocation requires processing authorization distinct from data access authorization.
4. Canonical integrity digests are distinct from pseudonymous audit references, which require approved keyed derivation when enumeration/linkability is material.
5. Provider-visible reason, evidence, limitation and market vocabulary use provider-safe aliases when canonical codes reveal information outside scope.

Additional hardening incorporated:

- ProviderProfile lifecycle and revocation/supersession semantics.
- Provider-managed tools, browsing, retrieval, grounding, code execution, file search, memory, connectors and agentic actions denied in the first production profile.
- Structured `AIExplanationDraft` schema with claim references.
- Audit release disposition is `RELEASE_APPROVED`, not evidence of delivery.
- Canonical fallback cannot bypass its own authorization or audit gates.
