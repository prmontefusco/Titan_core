# AI Explanation Governance Design Package

**Status:** PROPOSED / DESIGN ONLY
**Date:** 2026-09-04
**Scope:** governance for explanation-only AI over canonical Titan outputs.

## Objective

Allow future AI summaries to improve readability without granting AI authority over Titan's evidence, policy, evaluation, decision, dossier, privacy or tenant boundaries.

## Current Repository State

Market Optionality F7 introduced:

- canonical explanation context over `MarketOptionAssessment`;
- explicit draft assertions;
- deterministic validation of source references, option state, reason codes, missing evidence types and limitations;
- rejection of authoritative or forecast claims.

No provider, prompt execution, API, UI, persistence or migration exists.

## Architecture

```text
Canonical Titan Output
        |
        v
Explanation Context Builder
        |
        v
DataContract / FieldScope / ProcessingActivity
        |
        v
AI Adapter Boundary
        |
        v
Draft Explanation
        |
        v
Deterministic Guard
        |
        v
Non-authoritative Presentation
```

## Semantic Owner

Core owns AI/data-processing invariants. Livestock owns vertical explanation context for Livestock concepts such as Market Optionality.

## Persistence Owner

No persistence is proposed in this package. Future audit persistence should belong to the existing audit/infrastructure boundary, storing minimized envelopes and digests rather than raw prompts by default.

## API Owner

No API is proposed. Future user-visible AI explanation must be introduced through a separate API contract and feature flag.

## Tenant Boundary

Organization remains the boundary. AI context is built only after server-side authorization. Cross-Organization AI context is not authorized by this package.

## Temporal Semantics

Every explanation context must preserve `reference_time` and `knowledge_cutoff`. Re-running an explanation with different temporal coordinates is a distinct semantic operation.

## Authority Boundary

AI output is explanatory text only. It cannot create or alter Facts, Evidence, Rules, Policies, Evaluations, Decisions, Dossiers, VerificationBundles, forecasts, external recognition or Market Option states.

## Data Contract Requirements

A future provider integration needs a versioned DataContract covering:

- allowed context fields;
- prohibited fields;
- purpose;
- provider/model profile;
- region/location constraints;
- training prohibition;
- retention and deletion;
- telemetry/cache constraints;
- classification propagation;
- audit envelope;
- failure behavior.

## Guard Requirements

The deterministic guard must run after provider response and before presentation.

It must reject:

- missing or mismatched canonical references;
- invented reason codes;
- invented missing evidence types;
- invented limitations;
- option state mismatch;
- Decision/Evaluation/forecast/external authority claims;
- Fact/Evidence/Rule creation claims.

## Failure Modes

| Failure | Required behavior |
|---|---|
| Provider unavailable | Do not block canonical workflow; show structured canonical data |
| DataContract missing | Fail closed before prompt creation |
| Prompt contains prohibited field | Fail closed and audit safe reason |
| Draft fails guard | Do not present draft; preserve violation codes |
| Output claims authority | Reject |
| Later knowledge appears | Build new context; do not rewrite historical output |

## Security And Privacy Risks

- prompt leakage;
- provider retention;
- training/memorization;
- hidden prompt injection through source text;
- user over-trust in fluent generated text;
- cross-tenant context mixing;
- output becoming an oracle for protected data;
- logs/telemetry capturing sensitive prompt or output.

## Rejected Alternatives

| Alternative | Reason rejected |
|---|---|
| Direct LLM call from UI | Duplicates authorization in browser and bypasses server DataContract |
| Let LLM infer gaps from text | Violates Fact/Evidence/Policy/Evaluation boundaries |
| Store all prompts/outputs by default | Over-retains protected derived data |
| Use AI to decide optionality state | Creates parallel decision engine |
| Treat generated explanation as Dossier section | Weakens Dossier/VerificationBundle semantics |

## Minimal Future Build Slice

After ADR approval:

1. Add mock AI adapter interface and local deterministic fake.
2. Add DataContract allow-list tests for Market Optionality explanation context.
3. Add application service that returns either accepted draft or canonical fallback.
4. Keep route/UI disabled until external behavior is approved.

No production provider integration should be included in the first build.

## Local Pipeline Completion

Completed on 2026-09-04:

- mock text provider interface constrained to the minimized prompt payload;
- deterministic local fake;
- application service returning accepted draft text or canonical fallback;
- structured allowed claims originated by Titan before provider wording;
- executable synthetic DataContract allow-list that builds a need-to-know prompt payload without raw Organization, subject, Policy, Decision or Evaluation identifiers;
- versioned synthetic prompt template, explanation schema and guard metadata with canonical digests;
- executable synthetic provider profile denying retention, telemetry, abuse logging, secondary use, training use and tool execution;
- minimized local audit envelope with DataContract/provider/model/schema/template/guard references, payload/source/fallback/output digests, violation codes and limitations;
- tests proving a provider draft cannot be released when it invents material or claims forecast/authority;
- tests proving unapproved DataContract id/version fails closed before prompt payload creation;
- tests proving template/guard digest mismatches are rejected and prompt payload identity changes with template version;
- tests proving unapproved provider-side retention, telemetry, secondary use and profile digest mismatch fail closed;
- tests proving audit material does not retain raw prompt/output text or raw source identifiers;
- tests proving provider text with explicit authority/forecast content is rejected before release;
- tests proving provider unavailability returns canonical fallback without retaining provider exception diagnostics;
- tests proving canonical fallback is typed, immutable and still digestable for audit;
- tests proving derived classification and disclosure restrictions are present in fallback and minimized provider payload;
- synthetic Gemini pipeline smoke under `apps/validacao`, using only minimized non-real payload and omitting generated text from output.

Still outside this local/mock build:

- production provider integration;
- persisted/provider DataContract governance;
- persisted audit storage and retention;
- prompt/output retention;
- user-visible API/UI behavior;
- provider/model governance.

## ADR-0074 Acceptance With Changes

ADR-0074 was accepted with changes on 2026-09-04. The design now treats structured allowed claims as the boundary between Titan canonical outputs and AI wording:

```text
Canonical Titan output
    -> CanonicalExplanation
    -> allowed claims
    -> AIExplanationContext
    -> provider wording/paraphrase
    -> deterministic guard
    -> AI explanation or canonical fallback
```

The provider must not originate claims, access repositories or Domain objects, execute tools, follow source-content instructions, stream unvalidated output, declassify source restrictions or rely on unapproved retention/telemetry behavior.
