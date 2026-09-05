# SPEC: AI Explanation Production Decision Package

- **Level:** CRITICAL
- **Status:** PROPOSED / DECISION PACKAGE ONLY
- **Owner:** Titan Core + Titan Livestock
- **Date:** 2026-09-05

## Problem

ADR-0074 established the AI Explanation boundary and the local/mock pipeline made its core invariants executable. The remaining blocker is not code mechanics; it is the production decision for provider profile, DataContract and audit storage.

This SPEC closes that decision package without implementing a provider adapter, migration, API or UI.

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

### ProviderProfile

Required fields:

| Field | Requirement |
|---|---|
| provider_id | stable provider identifier |
| provider_profile_version | integer >= 1 |
| model_identifier | provider model name/id |
| model_version | provider-exposed version/revision when available |
| data_location_profile | approved region/location profile |
| provider_side_retention | `NONE` preferred; any non-none value requires explicit acceptance |
| telemetry | `NONE` preferred; any non-none value requires explicit acceptance |
| abuse_logging | `NONE` preferred; if mandatory, must be declared as limitation |
| secondary_use | `PROHIBITED` |
| training_use | `PROHIBITED` |
| tool_execution | `PROHIBITED` |
| subprocessors | declared, if applicable |
| contractual_evidence_reference | opaque reference to approved contract/evidence |
| profile_digest | canonical digest |

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
| claims | structured allowed claims with non-resolvable aliases |
| reason_codes | canonical codes only |
| missing_evidence_types | canonical codes only |
| limitations | canonical limitations only |
| context_limitations | AI-context limitations |
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
- personal data;
- secrets, tokens or credentials.

### Audit Storage Proposal

Persist a minimized record equivalent to `MarketOptionExplanationAuditEnvelope`.

Recommended logical owner: Livestock Application / AI Explanation application boundary.

Recommended persistence owner: Livestock Infrastructure, with RLS by record owner Organization.

Recommended storage columns:

| Column | Purpose |
|---|---|
| id | stable audit record id |
| record_owner_organization_id | RLS owner |
| requester_principal_digest | minimized requester reference |
| access_purpose | purpose used |
| processing_activity | processing activity |
| data_contract_id/version | DataContract identity |
| provider_profile_id/version/digest | provider governance |
| provider_id | provider identifier |
| model_identifier/version | model identity |
| explanation_schema | schema |
| prompt_template_id/version/digest | prompt identity |
| guard_version/digest | guard identity |
| prompt_payload_digest | prompt payload digest |
| source_reference_digest | canonical source-reference digest |
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

## Release Invariant

No externally visible AI explanation may be released without:

```text
authorized canonical source
    + DataContract validation
    + ProviderProfile validation
    + buffered provider output
    + deterministic guard acceptance
    + durable minimized audit persistence
```

If any element is unavailable or fails, return canonical fallback and record a non-release outcome when audit persistence is available. If required audit persistence fails, do not release AI text.

## Failure Modes

| Failure | Behavior |
|---|---|
| missing DataContract | no provider call; canonical fallback |
| incompatible ProviderProfile | no provider call; canonical fallback |
| provider unavailable | canonical fallback; no raw diagnostics retained |
| provider returns prohibited text | no release; canonical fallback |
| guard unavailable | no release; canonical fallback |
| audit persistence failure | no AI release |
| later knowledge appears | no rewrite of prior Evaluation/Decision/Dossier/VerificationBundle/audit |

## Tests Required For Production Build

- no provider call before DataContract/Profile validation;
- provider receives only allow-listed fields;
- prohibited fields are absent from prompt payload;
- untrusted source content is data, never instruction;
- provider output fully buffered before guard;
- guard rejection returns fallback;
- provider failure returns fallback without diagnostic leakage;
- audit failure blocks AI release;
- persisted audit omits raw prompt/output/source ids/exception text;
- RLS prevents other Organizations from reading audit records;
- `reference_time` and `knowledge_cutoff` are required and affect digest identity;
- output classification/restrictions propagate to audit and public projection.

## Policy Gates Remaining

### POLICY_GATE: Concrete Provider Contract

**Why required:** actual provider terms determine retention, telemetry, region, subprocessors, abuse logging and secondary use.

**Recommended:** approve only a strict profile with no training, no secondary use, no tool execution and no Titan-side prompt/output cache. If provider abuse logging cannot be disabled, record it as a limitation and restrict the first production use to non-sensitive/synthetic or explicitly approved data classes.

### POLICY_GATE: Audit Storage Retention And Visibility

**Why required:** persistent AI audit records are sensitive derived metadata.

**Recommended:** persist minimized audit envelope under owner Organization RLS; deny raw prompt/output retention; define retention with ADR-0014/ADR-0019 before migration.

### POLICY_GATE: User-Visible API/UI Contract

**Why required:** generated text changes external behavior and user trust.

**Recommended:** first expose to internal operator or producer-owned context only; keep buyer-facing aggregate AI explanation blocked.

## Recommended Next Build After Acceptance

1. Implement production-shaped ProviderProfile and DataContract value objects/repositories without external provider adapter.
2. Add audit storage migration/RLS for minimized records after retention/visibility approval.
3. Add provider adapter behind feature flag after concrete provider contract approval.
4. Add API/UI projection only after external behavior approval.

