# Market Optionality and Temporal Readiness

**Status:** PRODUCT/DOMAIN CONCEPT - NOT AUTHORIZED FOR PRODUCTION  
**Date:** 2026-09-03

## Why This Exists

Titan Livestock already answers whether a subject has a market eligibility conclusion under a Policy and version. The next product question is broader:

> Which market options does this animal still preserve under rules currently known to Titan?

This is not a promise of market access. It is a structured explanation of what Titan can and cannot conclude from facts, evidence, coverage and policies available within explicit temporal boundaries.

## Core Distinctions

Eligibility answers whether a subject satisfied a Policy in an Evaluation that may later support a Decision.

Readiness answers whether an existing Decision/Evaluation is usable for a specific operational context.

Market optionality answers whether a market path remains open, at risk, unknown, temporarily blocked or irreversibly closed under current known policy context.

None of these are export authorization, certificate, official recognition or commercial commitment.

## Examples

For the same animal and `knowledge_cutoff`:

| Market | Option State | Meaning |
|---|---|---|
| Brazil | OPEN | Known facts currently preserve the option under the selected Policy. |
| United States | OPEN | Existing Evaluation/Decision can support readiness under the context. |
| China | CONDITIONAL | Animal-side information may be sufficient, but establishment context is required. |
| European Union | AT_RISK | A treatment, movement or coverage gap can affect future compatibility. |
| United Kingdom | UNKNOWN | Policy or required evidence is not sufficiently available. |

State names are conceptual. Final vocabulary requires ADR acceptance.

## Temporal Semantics

Every assessment must bind:

- `reference_time`: what factual world is being evaluated;
- `knowledge_cutoff`: what Titan knew and could use;
- Policy id/version;
- market purpose/profile;
- target window, when future supply readiness is involved.

Changing any of these creates a distinct semantic query.

## Policy Changes

Facts do not change because a Policy changes. A new Policy version may require:

- new Evaluation;
- new Decision;
- new Dossier;
- impact assessment over old conclusions;
- recalculation of readiness or supply aggregates.

It must never rewrite historical Evaluation, Decision, Dossier or VerificationBundle records.

## Producers

For producers, optionality should help identify which market paths are preserved and which evidence gaps deserve attention. It must not suggest hiding treatments, avoiding welfare actions or gaming documentation. Clinical and animal welfare decisions remain outside Titan's commercial objectives.

## Buyers And Frigorificos

For buyers, optionality may later feed Market Supply Intelligence by estimating aggregate current readiness and potential future capacity under current knowledge. This must remain aggregate-first and identity-last unless explicit disclosure authorization exists.

## Relationship With Market Supply

Market Supply already has:

```text
authorization
-> candidate population snapshot
-> market readiness
-> disclosure
-> aggregation
-> audit
-> public response
```

Optionality can become an additional input to future supply readiness, but not a replacement for Evaluation, Decision or DisclosureDecision.

## Non-Goals

- no eligibility score;
- no ML prediction of future regulatory eligibility;
- no country-specific service;
- no global Animal lookup;
- no new official source integration;
- no change to Decision semantics;
- no forecast inside eligibility Dossier;
- no cross-tenant disclosure without ADR-0070/0071 controls.

## Principle

Titan does not predict future regulation. It preserves facts and evidence so future policy-versioned reassessment can explain what happened, what was known, which Policy changed and which options remain demonstrable.

