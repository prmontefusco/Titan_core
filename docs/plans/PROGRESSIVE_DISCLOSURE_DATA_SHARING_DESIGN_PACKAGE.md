# PROGRESSIVE DISCLOSURE AND DATA SHARING DESIGN PACKAGE

Status: ACCEPTED ARCHITECTURE BASELINE / CUT F NOT AUTHORIZED

Date: 2026-08-28

## 1. Objective

Define a future authorization and disclosure path for Market Supply Intelligence without implementing cross-tenant access, consent, grants, APIs, migrations or aggregate queries. ADR-0070 accepts the architectural direction; production still requires a future approved CUT F or prerequisite cut.

## 2. Existing Capabilities Reused

- Organization isolation and Authorization semantics from `DOMAIN.md`.
- `SharingRequest`, `GrantAssessment`, `AuthorizationGrant`, `AccessPurpose`, `GrantScope`, `GrantScopeResolution`, `FieldScope`, `AccessRestriction`, and `DataAccessRecord`.
- BuyerPolicy sharing decisions in ADR-0065 and ADR-0068.
- Uniform denial principles and protected metadata boundaries.

## 3. Accepted Disclosure Principles

- Aggregate-first, identity-last.
- Absence of a valid grant denies access.
- Relationship, shared Policy, known identifier, buyer/supplier contract, CommercialDemand, or common network participation does not imply access.
- Producer participation is explicit opt-in by default.
- Authorization surrounds population resolution and disclosure; it is not an after-the-fact filter.
- Field redaction alone is not enough to prevent disclosure.
- Export and redistribution are deny-by-default.
- Revocation is prospective and does not rewrite historical artifacts or audit.

## 4. Initial AccessPurposes

### MARKET_SUPPLY_AGGREGATE_ASSESSMENT

Authorizes only the approved aggregate analytical surface. It does not authorize producer identity, property identity, AnimalIdentifier, individual treatment, Evidence, Dossier, VerificationBundle, or individual Evaluation/Decision details.

### MARKET_SUPPLY_CANDIDATE_DISCLOSURE

Applies only after explicit commercial/candidate-selection context exists. It authorizes only fields allowed by FieldScope/GrantScope. Aggregate permission cannot silently escalate into candidate disclosure.

## 5. Disclosure Phases

### Phase A - Authorized Aggregate Visibility

Possible future output:

- number of participating Organizations/properties;
- animals considered;
- readiness counts by status;
- high-level gap categories;
- current capacity;
- potential capacity in window, if forecast is approved;
- estimated shortage;
- data cutoff, Policy version and limitations.

Forbidden without additional approval:

- producer identity;
- property identity;
- Animal ID;
- raw facts/evidence;
- individual Evaluation/Decision;
- individual Dossier or VerificationBundle.

### Phase B - Commercial Intent

An approved `CommercialDemand` anchors purpose, quantity, window, Policy/version and candidate constraints. It still grants no supplier access by itself.

### Phase C - Candidate Selection

Selection must be deterministic, scoped, auditable and authorization-aware. It cannot reserve animals or alter operational state by itself.

### Phase D - Authorized Subject Detail

Detailed disclosure requires FieldScope, GrantScope, Purpose, beneficiary capacity, audit and revocation rules.

### Phase E - Evidence/Artifact Sharing

Evidence, Dossier and VerificationBundle continue to follow their own sharing/publication mechanisms. Market Supply aggregate access does not imply artifact access.

## 6. AggregationPrivacyPolicy Direction

Future implementation should define `AggregationPrivacyPolicy` or an equivalent name aligned to the repository language. It must support:

- configurable minimum floors by deployment, product or profile;
- separate floors for Organizations, properties and subjects where applicable;
- dynamic risk assessment for geography, rare attributes, filter combinations, window, prior queries, differencing risk, timing and repeated access;
- suppression, generalization, freshness bands, precision reduction or temporary denial when risk is too high.

No arbitrary global threshold is accepted by this design package.

## 7. Revocation and Historical Access

After effective revocation:

- new query: denied;
- query reexecution: denied;
- new analytical report: denied;
- new detailed disclosure: denied.

Previously delivered material remains historical/auditable and is not erased. It must not be treated as evidence of current authorization. Reports must carry enough generated-at, cutoff, grant/context and validity metadata to avoid being presented as fresh analysis.

## 8. Export and Redistribution

Viewing aggregate analytics inside Titan does not authorize CSV/PDF export, external API extraction, redistribution, ingestion into external AI systems, secondary analytics, resale or publication.

Any future export/redistribution requires explicit operation or AccessPurpose, GrantScope, FieldScope and restrictions.

## 9. Required Future Decisions

| Topic | Decision Needed Before Production |
|---|---|
| GrantScope | fixed set, dynamic criteria, authorized snapshot, or combination per cut |
| FieldScope | concrete aggregate fields and detailed fields |
| AggregationPrivacyPolicy | profile, minimum floors and dynamic risk controls |
| Audit | required DataAccessRecord/AuditTier and volume/cost profile |
| Reidentification | differencing and repeated-query controls |
| Producer opt-in UX | who can approve, reduce, suspend or revoke participation |
| Export | explicit operation-level authorization model |

## 10. Non-goals

- no improvised consent model;
- no broad buyer visibility;
- no access by relationship alone;
- no leakage of identifiers, provenance or metadata outside FieldScope;
- no use of cache or projection as authorization;
- no CUT F implementation in this pass.

## 11. Proposed Architecture Direction

Use existing Core authorization concepts first. Do not create a Livestock-only consent shortcut. If product validation proves the need, formalize a profile that composes:

- SharingRequest;
- GrantAssessment;
- AuthorizationGrant;
- AccessPurpose;
- GrantScopeResolution;
- FieldScope;
- AccessRestriction;
- DataAccessRecord.

## 12. Decisions Resolved By ADR-0070

| Decision | Resolution |
|---|---|
| Allow aggregate visibility before explicit producer participation? | No |
| AccessPurpose model | two initial distinct purposes |
| Minimum aggregate threshold | configurable/profile concern, not global architectural constant |
| Dynamic criteria grants | possible only through explicit GrantScope design |
| Historical access after revocation | preserve delivered audit/history, block new access |
| Export/redistribution of aggregate | deny by default |

## 13. Acceptance Criteria For This Design Package

- No BUILD authorized.
- No cross-tenant implementation.
- Resolved Product Owner decisions are incorporated.
- Remaining decisions are implementation/security profile choices, not ADR acceptance blockers.
- BuyerPolicy sharing is not stretched into herd disclosure.
