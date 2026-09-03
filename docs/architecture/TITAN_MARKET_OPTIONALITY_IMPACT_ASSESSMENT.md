# Titan Market Optionality Impact Assessment

**Status:** DISCOVERY / ARCHITECTURAL ANALYSIS  
**Date:** 2026-09-03  
**Scope:** Titan Livestock; no production implementation authorized by this document.

## Current Architecture

Titan already represents market eligibility as a contextual relationship between a subject, a market purpose and a versioned Policy. ADR-0041 and ADR-0044 explicitly reject eligibility as an Animal attribute and keep the market matrix as a derived read. ADR-0052, ADR-0061, NEXT-05, NEXT-06 and NEXT-07 already establish the temporal and historical foundation needed for policy-versioned evaluation and re-evaluation without rewriting history.

Market Supply F3.5 is implemented as an audited, feature-flagged aggregate path over authorized Candidate Population, MarketReadiness, DisclosureDecision and durable owner-scoped audit. It is non-regulatory and does not introduce forecast, CommercialDemand persistence or multi-owner public release beyond the approved pipeline boundaries.

## Capability Matrix

| Capability | Current Status | Existing Component | Gap | Reuse | Extend | New Concept Required | Do Not Implement |
|---|---|---|---|---|---|---|---|
| Policy versioning | ALREADY_IMPLEMENTED | `Policy`, `Rule`, `RuleAdoption`, `NormativeBasisSnapshot` | Impact workflows remain mostly transient | Yes | Add optionality-specific projections only | No | Do not create market-specific policy stores |
| `knowledge_cutoff` | ALREADY_IMPLEMENTED | `FactSnapshot`, `Evaluation`, ADR-0052, MarketReadiness, Market Supply | Some legacy paths still carry limitations | Yes | Require in optionality context | No | Do not default to current time silently |
| `reference_time` | ALREADY_IMPLEMENTED | ADR-0052, `MarketReadinessContext`, Candidate Population | Target-window semantics need modeling | Yes | Add explicit target window for optionality/supply | Maybe as value object | Do not collapse into `as_of` |
| Multi-market evaluation | PARTIALLY_IMPLEMENTED | `MarketEligibilityPurpose`, `MarketEligibilityStatus`, matrix | Current market catalog is fixed to BR/CN/US/EU-style first cut | Yes | Generalize in Livestock, not Core | Possibly `MarketProfileRef` | Do not create `EuEligibilityService` |
| Lifetime compliance | PARTIALLY_IMPLEMENTED | dimensional coverage, temporal readers, FactSnapshot | Option preservation needs reversible/irreversible classification | Yes | Coverage dimensions and RuleResult reasons | Maybe value objects | Do not create boolean lifetime complete |
| Market eligibility | ALREADY_IMPLEMENTED | `MarketEligibilityService`, Evaluation/Decision | Optionality states are not the same as eligibility matrix states | Yes | Read-only mapping layer | Yes, `MarketOptionAssessment` | Do not alter DecisionResult |
| Market readiness | ALREADY_IMPLEMENTED | `MarketReadinessService` | Future readiness under current knowledge is not modeled | Yes | Add optional target-window interpretation | Maybe `SupplyReadinessAssessment` | Do not persist on Animal |
| Candidate population | ALREADY_IMPLEMENTED FOR F3.5 | `CandidatePopulationCriteria`, resolver, snapshot | Multi-owner release history completeness remains constrained | Yes | Future supply readiness can reuse it | No new aggregate now | No global animal lookup |
| Market supply aggregation | PARTIALLY_IMPLEMENTED | F3.5 single-owner audited route | No forecast or optionality aggregate | Yes | Future F6 after optionality semantics | Maybe analytical result | Do not add ML/probability |
| Dossier | ALREADY_IMPLEMENTED | `Dossier`, Livestock vertical section | Optionality dossier semantics not defined | Yes | Add section only after ADR acceptance | Maybe section, not new Core dossier | Do not put forecast as eligibility Decision |
| VerificationBundle | ALREADY_IMPLEMENTED | `VerificationBundleService` | Optionality artifact packaging not decided | Yes | Use existing bundle if material result exists | No Core change expected | Do not create parallel verifier |
| AuditEnvelope | ALREADY_IMPLEMENTED/PARTIAL | Core audit, MarketSupplyQueryAuditRecord | Optionality assessment audit envelope not specified | Yes | Use Core audit/application audit pattern | Maybe record if persisted | Do not log sensitive payloads |
| Progressive disclosure | ALREADY_IMPLEMENTED FOR MARKET SUPPLY | ADR-0070/0071/0072, F3.5 | Optionality individual vs aggregate disclosure needs policy | Yes | Use aggregate-first/identity-last | No new consent model now | No buyer global visibility |
| Cross-tenant authorization | ALREADY_IMPLEMENTED FOR F3.5 | AuthorizationGrant, GrantScope, FieldScope | Which grants authorize optionality aggregate remains policy | Yes | Use existing grants | No until insufficiency shown | Do not infer access from demand |
| Unknown handling | ALREADY_IMPLEMENTED/PARTIAL | RuleResultStatus, EvaluationOutcome, MarketReadinessStatus | Optionality needs richer reasons without new truth model | Yes | Derived state taxonomy | Yes as projection states | Do not treat UNKNOWN as failed |
| Evidence coverage | PARTIALLY_IMPLEMENTED | coverage contributions, dimensional coverage | Reversibility/remediation semantics absent | Yes | Derive gaps from coverage/rules | Maybe `GapResolutionHint` | No LLM-generated checklist |

## Domain Impact

The proposed capability is material because it introduces a new product question: not only "is this subject eligible now under Policy X?" but "which market options remain open, at risk, unknown or closed under currently known policies?" This should be modeled in Titan Livestock first. It should not move market vocabulary into Core and should not change `Animal`, `Evaluation`, `Decision`, `Dossier` or `VerificationBundle` semantics.

The smallest domain addition is a derived concept, `MarketOptionAssessment`, not an aggregate root. It reads existing `Evaluation`, `Decision`, `RuleResult`, coverage and Policy metadata and produces a contextual state. It is not a new Decision.

## Application Impact

New application services may be needed for:

- resolving optionality context across market purposes;
- mapping existing Evaluation/Decision/RuleResult/Coverage to option states;
- comparing optionality across Policy versions;
- producing policy-change impact reports;
- aggregating supply readiness under current knowledge.

These services should be pure/read-oriented first. No worker, persistence, API or UI should be introduced before F0/F1 acceptance.

## Database Impact

No database change is recommended for the first cut. Future persistence may be justified only for:

- immutable optionality assessment artifacts;
- policy-change impact plans;
- supply readiness reports;
- audit records for externally visible or cross-tenant operations.

Any new table requires RLS, append-only behavior when historical, retention policy and migration tests.

## API Impact

No API should be implemented in the discovery phase. Future APIs must preserve:

- no global Animal lookup;
- Organization-scoped reads;
- explicit `reference_time` and `knowledge_cutoff`;
- Policy/version in every request;
- no eligibility booleans;
- uniform behavior for invisible/nonexistent/protected material where needed.

## Audit Impact

Material optionality assessments need an audit envelope if stored, shared, used for notifications or used to drive re-evaluation. The envelope should preserve actor, Organization, purpose, market profile, Policy/version, FactSnapshot/Evaluation/Decision references, temporal coordinates, unknowns, exclusions and outcome. Audit payloads must be minimized.

## Dossier Impact

Existing Dossier should remain anchored in one Decision/Evaluation. A future optionality section may be acceptable only if it declares itself as derived/non-certifying and references canonical inputs. It must not turn a forecast or option state into a Decision.

## Market Supply Impact

Market Supply can consume optionality later, but F3.5 should not be retrofitted into a forecast engine. Future supply readiness should remain analytical, deterministic, assumption-aware and privacy-controlled. Denominators must show unknown, inaccessible, excluded and evaluated counts rather than hiding uncertainty.

## Modeling Risks

- duplicating eligibility with a new optionality engine;
- country-specific services or hardcoded EU logic;
- using current Policy as if it were known historically;
- turning option preservation into clinical or operational recommendation;
- treating missing evidence as incompatibility;
- presenting future readiness as prediction or export promise;
- exposing aggregate optionality cross-tenant without ADR-0070/0071 controls;
- using LLMs to create regulatory conclusions.

## Recommended Cut

**Recommendation: PROCEED WITH CHANGES.**

Proceed to SPEC/ADR review for a Livestock-owned, derived `MarketOptionAssessment` and a phased plan. Do not implement code until the ADR is accepted or a narrow F0/F1 cut is explicitly authorized. The first implementation should be pure application/domain projection over synthetic policies and existing Evaluation/Decision objects, with no persistence or API.

