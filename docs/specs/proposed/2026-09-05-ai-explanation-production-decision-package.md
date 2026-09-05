# SPEC: AI Explanation Production Decision Package

- **Level:** CRITICAL
- **Status:** ACCEPTED WITH CHANGES / DECISION PACKAGE ONLY
- **Owner:** Titan Core + Titan Livestock
- **Date:** 2026-09-05

## Problem

ADR-0074 established the AI Explanation boundary and the local/mock pipeline made its core invariants executable. The remaining blocker is not code mechanics; it is the production decision for provider profile, DataContract and audit storage.

This SPEC closes that decision package without implementing a provider adapter, migration, API or UI.

ADR-0075 was accepted with changes on 2026-09-05. This SPEC reflects the accepted boundaries and remains non-implementation documentation.

## Existing Authority

- `DOMAIN.md`: AI cannot choose result or authority; reading data does not authorize AI, inference or redistribution.
- `ARCHITECTURE.md`: AI providers are consumers governed by DataContract, ProcessingActivity, Authorization and classification propagation.
- ADR-0013: AI artifacts preserve classification, purpose, license and restrictions.
- ADR-0018: DataContract restricts flow and does not grant access.
- ADR-0019: audit for sensitive access must be classified, minimized and authorization-aware.
- ADR-0074: AI Explanation can only summarize canonical outputs selected by server-side authorization and guarded before presentation.

## Scope

Define production decision inputs for:

- ProviderProfile;
- DataContract field allow-list;
- minimized AI Explanation audit storage;
- release/failure invariants;
- processing authorization for external provider invocation;
- idempotency/replay semantics;
- pseudonymous audit references;
- provider-safe vocabulary aliases;
- first allowed production audience;
- explicit remaining policy gates.

## Out Of Scope

- provider SDK integration;
- Gemini or any concrete provider adapter;
- migration generation/application;
- API endpoint;
- UI surface;
- buyer-facing or cross-tenant AI explanation;
- raw prompt/output retention;
- embeddings, vector store, training or fine-tuning.

## Recommended Production Position

### First Audience

Use production AI Explanation first for:

- internal operator review; or
- producer-facing explanation over that producer's own authorized Organization data.

Do not use production AI Explanation for buyer-facing Market Supply aggregates until progressive disclosure and aggregation privacy release decisions are accepted.

### Processing Authorization

Permission to read canonical Titan output is not sufficient to send derived data to an external AI processor.

Provider invocation requires:

- server-side data access authorization;
- approved ProcessingActivity;
- approved DataContract;
- approved ProviderProfile;
- Organization/purpose/provider-compatible processing authorization;
- classification ceiling compatible with the source claims and output.

Recommended first shape: `ProviderProcessingAuthorization` as a versioned application concept. It does not need to be an Aggregate Root unless lifecycle, independent identity or persistence become necessary in the production build.

### ProviderProfile

Required fields:

| Field | Requirement |
|---|---|
| provider_id | stable provider identifier |
| provider_profile_version | integer >= 1 |
| lifecycle_state | `DRAFT`, `APPROVED`, `SUSPENDED`, `REVOKED`, `SUPERSEDED` |
| effective_from/effective_until | temporal validity |
| approved_at/approved_by | approval evidence when approved |
| model_identifier | provider model name/id |
| model_version | provider-exposed version/revision when available |
| data_location_profile | approved region/location profile |
| provider_side_retention | `NONE` preferred; any non-none value requires explicit acceptance |
| telemetry | `NONE` preferred; any non-none value requires explicit acceptance |
| abuse_logging | `NONE` preferred; if mandatory, must be declared as limitation |
| secondary_use | `PROHIBITED` |
| training_use | `PROHIBITED` |
| provider_side_capabilities | tools, browsing, retrieval, grounding, code execution, file search, memory, connectors and agentic actions all `PROHIBITED` for the first cut |
| subprocessors | declared, if applicable |
| contractual_evidence_reference | opaque reference to approved contract/evidence |
| profile_digest | canonical digest |

Only an `APPROVED` and effective profile can be used. ProviderProfile must be rechecked before external release; suspension, revocation or supersession blocks new provider calls and releases.

### DataContract

Initial allowed provider-visible fields:

| Field | Notes |
|---|---|
| audience | category only |
| subject_type | e.g. `animal` |
| market_purpose | approved purpose code/label |
| policy_version | version only |
| reference_time | mandatory UTC |
| knowledge_cutoff | mandatory UTC |
| option_state | canonical Market Optionality state |
| reversibility | canonical reversibility |
| claims | structured allowed claims with non-resolvable provider-safe aliases |
| reason_aliases | provider-safe reason aliases |
| missing_evidence_aliases | provider-safe missing-evidence aliases |
| limitation_aliases | provider-safe limitation aliases |
| context_limitation_aliases | provider-safe AI-context limitation aliases |
| output_classification | derived classification |
| disclosure_restrictions | inherited/strengthened restrictions |
| prompt_template_id/version/digest | prompt identity |
| guard_version/digest | guard identity |
| payload_digest | canonical request payload digest |

Prohibited provider-visible fields:

- raw Organization id;
- raw subject/Animal/property/producer identifiers;
- Decision id;
- Evaluation id;
- Policy id;
- raw Fact or Evidence payload;
- raw external-source content;
- source-reference aliases resolvable outside Titan;
- internal reason/evidence/limitation/market codes when the canonical vocabulary itself reveals information outside scope;
- personal data;
- secrets, tokens or credentials.

Canonical internal vocabulary must be projected to provider-safe aliases whenever the original code is sensitive, unusually specific or outside the approved disclosure scope.

### Structured Draft

The production provider returns a versioned `AIExplanationDraft` schema:

```json
{
  "schema": "AI_EXPLANATION_DRAFT_V1",
  "sections": [
    {
      "claim_refs": ["claim-1"],
      "text": "..."
    }
  ]
}
```

The guard validates section shape, claim refs, allowed claims, prohibited vocabulary and non-authoritative assertions before release. Free-form provider text without schema is not a production release artifact.

### Audit Storage Proposal

Persist a minimized record equivalent to `MarketOptionExplanationAuditEnvelope`.

Recommended logical owner: Livestock Application / AI Explanation application boundary.

Recommended persistence owner: Livestock Infrastructure, with RLS by record owner Organization.

Recommended storage columns:

| Column | Purpose |
|---|---|
| id | stable audit record id |
| record_owner_organization_id | RLS owner derived from canonical explanation context |
| requester_principal_reference | opaque audit reference |
| acting_organization_context | present when distinct from record owner |
| access_purpose | purpose used |
| processing_activity | processing activity |
| processing_authorization_reference | provider processing authorization |
| data_contract_id/version | DataContract identity |
| provider_profile_id/version/digest | provider governance |
| provider_id | provider identifier |
| model_identifier/version | model identity |
| explanation_schema | schema |
| prompt_template_id/version/digest | prompt identity |
| guard_version/digest | guard identity |
| prompt_payload_digest | prompt payload digest |
| source_reference_digest | canonical integrity digest or opaque audit reference according to sensitivity |
| canonical_fallback_digest | fallback digest |
| released_output_digest | nullable; present only on release |
| accepted | guard/release flag |
| violation_codes | stable internal codes |
| output_classification | derived classification |
| disclosure_restrictions | inherited restrictions |
| reference_time | canonical temporal coordinate |
| knowledge_cutoff | knowledge temporal coordinate |
| requested_at | request instant |
| evaluated_at | evaluation instant |
| correlation_id | trace correlation |
| idempotency_reference | replay correlation when applicable |

Must not store raw prompt, raw output, raw source ids, raw Evidence/Facts, provider exception text or secrets.

`record_owner_organization_id` is never supplied by the caller or provider adapter. Identifier-derived audit references must use approved non-reversible keyed derivation, not unkeyed hashes, when enumeration or linkability is material.

### Idempotency And Replay

AI explanation text is nondeterministic presentation. Idempotency correlates the request and prevents duplicate business effects, but does not promise byte-identical replay unless Titan persists a released presentation artifact.

This SPEC does not approve released text persistence. If exact replay becomes required, create a controlled derived artifact distinct from raw provider output.

## Release Invariant

No externally visible AI explanation may be released without:

```text
authorized canonical source
    + DataContract validation
    + ProviderProfile validation
    + processing authorization validation
    + buffered provider output
    + deterministic guard acceptance
    + durable minimized audit persistence
```

If any element is unavailable or fails, return canonical fallback and record a non-release outcome when audit persistence is available. If required audit persistence fails, do not release AI text.

AI audit failure cannot be used to bypass canonical explanation authorization/audit. The AI output is discarded, and fallback presentation follows the ordinary canonical explanation path.

Audit release semantics record `RELEASE_APPROVED` or `NOT_RELEASED`; they do not assert that the requester received or read the output.

## Failure Modes

| Failure | Behavior |
|---|---|
| missing DataContract | no provider call; canonical fallback |
| incompatible ProviderProfile | no provider call; canonical fallback |
| missing processing authorization | no provider call; canonical fallback |
| ProviderProfile revoked before release | no release; canonical fallback |
| provider unavailable | canonical fallback; no raw diagnostics retained |
| provider returns prohibited text | no release; canonical fallback |
| guard unavailable | no release; canonical fallback |
| audit persistence failure | no AI release |
| later knowledge appears | no rewrite of prior Evaluation/Decision/Dossier/VerificationBundle/audit |

## Tests Required For Production Build

- no provider call before DataContract/Profile validation;
- provider receives only allow-listed fields;
- prohibited fields are absent from prompt payload;
- data-access authorization alone cannot invoke external provider;
- provider processing authorization is validated before provider call;
- ProviderProfile state/effective period is validated before call and release;
- provider-safe aliases hide sensitive internal vocabulary;
- untrusted source content is data, never instruction;
- provider output fully buffered before guard;
- structured draft schema requires valid claim refs;
- guard rejection returns fallback;
- provider failure returns fallback without diagnostic leakage;
- audit failure blocks AI release;
- persisted audit omits raw prompt/output/source ids/exception text;
- caller/provider cannot supply record owner Organization;
- identifier-derived audit references use approved keyed derivation where required;
- RLS prevents other Organizations from reading audit records;
- `reference_time` and `knowledge_cutoff` are required and affect digest identity;
- output classification/restrictions propagate to audit and public projection.

## Policy Gates Remaining

### POLICY_GATE: Concrete Provider Contract

**Why required:** actual provider terms determine retention, telemetry, region, subprocessors, abuse logging and secondary use.

**Recommended:** approve only a strict profile with no training, no secondary use, no tool execution and no Titan-side prompt/output cache. If provider abuse logging cannot be disabled, record it as a limitation and restrict the first production use to non-sensitive/synthetic or explicitly approved data classes.

### POLICY_GATE: Provider Processing Authorization

**Why required:** external AI processing is distinct from reading Titan data.

**Recommended:** approve a versioned `ProviderProcessingAuthorization` bounded by Organization, purpose, ProviderProfile, DataContract, classification ceiling and effective period.

### POLICY_GATE: Audit Storage Retention And Visibility

**Why required:** persistent AI audit records are sensitive derived metadata.

**Recommended:** persist minimized audit envelope under owner Organization RLS; deny raw prompt/output retention; define retention with ADR-0014/ADR-0019 before migration.

### POLICY_GATE: User-Visible API/UI Contract

**Why required:** generated text changes external behavior and user trust.

**Recommended:** first expose to internal operator or producer-owned context only; keep buyer-facing aggregate AI explanation blocked.

## Recommended Next Build After Acceptance

1. Implement production-shaped ProviderProfile lifecycle and DataContract value objects without external provider adapter.
2. Add ProviderProcessingAuthorization concept/service if no existing authorization contract covers it.
3. Add provider-safe alias projection and structured draft guard tests.
4. Design audit storage migration/RLS and keyed audit reference strategy.
5. Add provider adapter behind feature flag after concrete provider contract approval.
6. Add API/UI projection only after external behavior approval.
