# MARKET SUPPLY INTELLIGENCE DESIGN PACKAGE

Status: ACCEPTED ARCHITECTURE BASELINE / CUT F NOT AUTHORIZED

Date: 2026-08-28

## 1. Objective

Define a non-regulatory analytical layer for market supply intelligence without implementing code, persistence, migrations, API, cross-tenant access or forecast execution. ADR-0069 accepts the architectural boundary; CUT F still requires separate authorization.

## 2. Existing Capabilities Reused

- `MarketReadinessService` for current contextual readiness derived from `Decision`/`Evaluation`.
- `RuleResult`, `missing_evidence_types`, coverage facts and evaluation limitations for gap explanations.
- `FactSnapshot.reference_time` and `knowledge_cutoff` for temporal boundaries.
- Dossier/VerificationBundle only as historical regulatory/evidence artifacts, not forecast containers.

## 3. Proposed Concepts

### CommercialDemand

Commercial intent owned by the buyer/frigorifico Organization in Titan Livestock, not Policy and not Core.

Candidate fields for future review:

- buyer/requesting Organization;
- purpose;
- Policy reference/version;
- quantity;
- commercial window;
- candidate population constraints;
- disclosure constraints;
- created_at/requested_by;
- status and revocation/cancellation semantics.

Design answers:

| Question | Proposed answer |
|---|---|
| Business problem | express buyer/frigorifico need for quantity, window and Policy context |
| Semantic owner | Livestock product/application, not Core yet |
| Status | future Livestock concept; persistence shape deferred to CUT F SPEC |
| Invariants | not Policy, Rule, Evaluation, Decision, Fact or regulatory evidence |
| Organization owner | buyer/frigorifico Organization |
| Tenant boundary | grants no supplier access by existence |
| Lifecycle | draft/requested/active/cancelled/expired candidates, undecided |
| Temporal semantics | created_at, window, reference_time, knowledge_cutoff |
| Authorization | buyer can manage own demand; supplier visibility requires explicit purpose/scope |
| Provenance | records requester, Policy reference and source of demand |
| Explainability | report must show demand inputs and limitations |
| Auditability | creation, update, cancellation and use require audit if implemented |
| Policy interaction | references Policy/version; does not define criteria |
| Evaluation/Decision interaction | none directly; consumes derived results |
| MarketReadiness interaction | uses readiness counts under matching context |
| Dossier/VerificationBundle interaction | none; not embedded in eligibility Dossier |
| Persistence alternatives | no persistence for prototype, command record, append-only demand record |
| Failure modes | missing Policy, unauthorized population, expired window, insufficient scope |
| Security/privacy risks | demand could pressure disclosure; existence may reveal buyer intent |
| Alternatives rejected | modeling as Policy, Rule or Decision |

### SupplyForecast

Projection under explicit assumptions. It is not Decision, Evaluation or certificate.

Required future metadata:

- generated_at;
- reference_time;
- horizon/window;
- knowledge_cutoff;
- assumptions/version;
- source population;
- Policy/version;
- uncertainty and limitations;
- provenance.

Design answers:

| Question | Proposed answer |
|---|---|
| Business problem | estimate potential capacity in a future commercial window |
| Semantic owner | Livestock analytics/application |
| Status | computed-on-demand analytical projection; not aggregate root in this design |
| Invariants | non-decisional, non-regulatory, assumption-aware |
| Organization owner | owner of the generated report or analysis context, undecided |
| Tenant boundary | cannot read supplier data without explicit authorization |
| Lifecycle | generated, superseded by new run, expired by horizon |
| Temporal semantics | generated_at, reference_time, knowledge_cutoff, horizon/window |
| Authorization | same or stricter than source data; no forecast by inaccessible data |
| Provenance | source population, readiness inputs, assumptions/version |
| Explainability | show assumptions, excluded subjects, uncertainty and gaps |
| Auditability | every generated report should be reproducible from preserved inputs |
| Policy interaction | tied to Policy/version |
| Evaluation/Decision interaction | consumes outputs; never creates or changes them |
| MarketReadiness interaction | starts from readiness and gap categories |
| Dossier/VerificationBundle interaction | separate `SupplyIntelligenceReport` |
| Persistence alternatives | transient result by default, immutable `SupplyForecastSnapshot` only when report/audit/reproducibility requires it |
| Failure modes | unknown data, stale assumptions, unauthorized population |
| Security/privacy risks | future claims overread as guaranteed supply |
| Alternatives rejected | ML first, `FutureEligibilityDecision`, Dossier section, mutable forecast state |

### SupplyDemandAnalysis

Composition of `CommercialDemand`, `MarketReadiness`, and optionally `SupplyForecast`.

Outputs may include `ready_now`, `potential_in_window`, `gap_resolvable`, `indeterminate`, `estimated_capacity`, and `estimated_shortage`. These are analytics only.

Design answers:

| Question | Proposed answer |
|---|---|
| Business problem | compare demand with current and potential supply |
| Semantic owner | Livestock analytics/application |
| Status | derived analysis/read model, not Decision |
| Invariants | explains counts and gaps; does not certify availability |
| Organization owner | report/request owner, with source scopes preserved |
| Tenant boundary | aggregate-first; identity-last; no implicit supplier access |
| Lifecycle | generated for a demand/context; immutable if saved |
| Temporal semantics | generated_at, reference_time, knowledge_cutoff, demand window |
| Authorization | requires access to aggregate inputs and future detail separately |
| Provenance | demand id, population digest, readiness/report inputs |
| Explainability | show formulas, exclusions, assumptions and unknowns |
| Auditability | preserved input references and query audit required if persisted |
| Policy interaction | only through referenced Policy/version |
| Evaluation/Decision interaction | reads existing results only |
| MarketReadiness interaction | primary current-state input |
| Dossier/VerificationBundle interaction | separate report artifact |
| Persistence alternatives | transient result, immutable report, cached projection |
| Failure modes | undercovered population, stale readiness, forecast absent |
| Security/privacy risks | aggregate leakage and differencing attacks |
| Alternatives rejected | modifying MarketReadiness or Decision semantics |

### GapAnalysis

Derived from existing results:

- RuleResult status/reason;
- missing evidence types;
- coverage limitations;
- readiness status;
- inaccessible/unknown/conflicting sources.

No parallel commercial taxonomy should override RuleResult semantics.

Design answers:

| Question | Proposed answer |
|---|---|
| Business problem | explain why capacity cannot meet demand |
| Semantic owner | derived Livestock analytics over existing results |
| Status | composition, not domain authority |
| Invariants | derive only from existing reasons, coverage and limitations |
| Organization owner | same as report context |
| Tenant boundary | cannot expose individual reasons outside FieldScope |
| Lifecycle | generated with analysis/report |
| Temporal semantics | bound to Evaluation/readiness context |
| Authorization | aggregate reasons need aggregate FieldScope |
| Provenance | references source result classes, not raw hidden facts |
| Explainability | show category, count, unknowns and limitations |
| Auditability | query/report audit if shared |
| Policy interaction | gaps are Policy-contextual |
| Evaluation/Decision interaction | reads RuleResult and limitations only |
| MarketReadiness interaction | uses readiness gap summary |
| Dossier/VerificationBundle interaction | no eligibility Dossier mutation |
| Persistence alternatives | report section only preferred initially |
| Failure modes | missing reason, inaccessible reason, mixed policies |
| Security/privacy risks | rare gap category can identify producer |
| Alternatives rejected | separate gap engine or commercial override taxonomy |

### Candidate Population

Candidate Population is the explicit set or query basis considered before readiness, forecast or demand analysis. It is not automatically a new aggregate root.

Design answers:

| Question | Proposed answer |
|---|---|
| Business problem | explain which subjects were considered/excluded |
| Semantic owner | Livestock analytics/application |
| Status | `CandidatePopulationCriteria -> PopulationResolver -> CandidatePopulationSnapshot`; no standalone Aggregate Root initially |
| Invariants | no hidden population, no current-state-as-history |
| Organization owner | source Organization or authorized network context, undecided |
| Tenant boundary | supplier subjects remain tenant-owned |
| Lifecycle | resolved for one analysis; saved only if report requires it |
| Temporal semantics | reference_time, knowledge_cutoff, membership/effective criteria |
| Authorization | every included subject must be accessible for that purpose |
| Provenance | criteria, filters, source repositories, exclusions |
| Explainability | list counts and exclusion reasons; identity only if authorized |
| Auditability | resolution should be auditable if shared |
| Policy interaction | population is filtered before Policy/readiness use |
| Evaluation/Decision interaction | points to existing subject results |
| MarketReadiness interaction | input to readiness report |
| Dossier/VerificationBundle interaction | not a Dossier |
| Persistence alternatives | criteria-only query for prototype, immutable snapshot/report component when materialized |
| Failure modes | inaccessible subject, ambiguous membership, stale lot |
| Security/privacy risks | population size can leak participation |
| Alternatives rejected | automatic `CandidatePopulation` aggregate root |

### SupplyIntelligenceReport

Separate analytical artifact, not an eligibility Dossier. Name accepted by ADR-0069.

Design answers:

| Question | Proposed answer |
|---|---|
| Business problem | package supply intelligence with context and limitations |
| Semantic owner | Livestock analytics/application |
| Status | accepted analytical artifact concept; implementation format deferred |
| Invariants | analytical, non-regulatory, non-decisional, temporally bounded |
| Organization owner | report generator/authorized requester, undecided |
| Tenant boundary | contains only fields allowed by FieldScope |
| Lifecycle | generated, shared, expired/superseded, revoked-for-new-access |
| Temporal semantics | generated_at, reference_time, knowledge_cutoff, horizon |
| Authorization | sharing requires Purpose/GrantScope/FieldScope |
| Provenance | demand, population, readiness, forecast assumptions |
| Explainability | human-readable limitations and unknowns |
| Auditability | report generation and access must be audited if shared |
| Policy interaction | declares Policy/version used |
| Evaluation/Decision interaction | references derived results, never mutates |
| MarketReadiness interaction | embeds aggregate readiness counts |
| Dossier/VerificationBundle interaction | separate; may reuse hashing later without becoming Dossier |
| Persistence alternatives | static file, immutable DB artifact, or both; generated mutable view rejected for historical reports |
| Failure modes | stale report, revoked access, partial inputs |
| Security/privacy risks | report redistribution and inference |
| Alternatives rejected | eligibility Dossier section, VerificationBundle mutation |

## 4. Boundaries

- No official recognition.
- No future eligibility promise.
- No changes to Decision/Evaluation.
- No forecast inside eligibility Dossier as regulatory proof.
- No cross-tenant data access until ADR-0070 controls are implemented in an approved cut.

## 5. Proposed Cuts After Approval

1. CUT F0: non-production synthetic/in-memory analytical prototype.
2. CUT F1: single-Organization producer-side Market Supply analysis.
3. CUT F2: authorization/grant/profile preparation.
4. CUT F3: cross-Organization aggregate visibility after aggregation privacy controls.
5. CUT F4: detailed candidate disclosure.

## 6. Decisions Resolved By ADR-0069/0070

| Decision | Resolution |
|---|---|
| Is `CommercialDemand` a Livestock concept or Core concept? | Livestock first |
| Persist forecast or compute on demand? | Compute on demand by default; snapshot only for report/audit/reproducibility |
| Where does supply analytics artifact live? | Separate `SupplyIntelligenceReport`, not Dossier/VerificationBundle |
| Can buyers see aggregate readiness before producer opt-in? | No by default |
| Can forecasts use hypothetical corrective actions? | Only as assumptions/scenarios, never Decision |

## 7. Remaining Human Review

- Authorize a specific CUT F/F0 implementation.
- Approve concrete persistence/API contracts for any future production cut.
- Approve concrete `CandidatePopulationSnapshot` digest model.
- Approve concrete report storage/export behavior.

## 8. Acceptance Criteria For This Design Package

- It does not authorize BUILD.
- It incorporates the resolved RED decisions from ADR-0069/0070.
- It reuses MarketReadiness instead of creating a decision engine.
- It keeps Policy distinct from CommercialDemand.
- It keeps forecast distinct from Decision/Evaluation/Dossier.
