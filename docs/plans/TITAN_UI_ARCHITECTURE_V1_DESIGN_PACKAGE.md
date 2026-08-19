# Titan UI Architecture V1 — Design Package

## 1. Executive Summary

**Status: APPROVED FOR ARCHITECTURAL GUIDANCE.** No implementation is authorized by this package alone. Titan should be one capability- and context-driven application: `OrganizationContext + authenticated principal + server-authorized capability + purpose`, with vertical modules contributing routes and presentation only. It must not fork into applications per persona.

## 2. Authority Inputs

`VISION.md`, `DOMAIN.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, ADR-0002, ADR-0019, ADR-0031, ADR-0053–0055 and `ADMIN_UI_CAPABILITY_MAP.md` were used. Organization is the isolation boundary; the server constructs authorization. UI communicates state and requests operations; it never creates authority.

## 3. Current Frontend State

React/Vite/TypeScript + React Router + OIDC/PKCE. `ApplicationShell`, `TopBar`, `Sidebar` and `UserAccountMenu` are present; routes cover Livestock search/detail/timeline/treatment, market explanation/governance, territorial QA, access request queue and decision review. Loading, error, empty and unauthorized states exist inconsistently. No server capability-navigation contract, Organization selector, notification center, global search or generic read models exist.

## 4. Current Capability Map

| Capability | Existing Backend | Existing API | Existing UI | Category | Status |
|---|---|---|---|---|---|
| Session, logout, active Organization | OIDC/context | yes | shell/menu | SELF_SERVICE | IMPLEMENTED |
| Access requests | service + persistence | list/approve/deny | queue/overview | ADMINISTRATION | IMPLEMENTED |
| Livestock operations | vertical services | extensive | pages | DOMAIN_OPERATION | IMPLEMENTED |
| Rules/policies | governance services | vertical endpoints | governance | GOVERNANCE | PARTIAL |
| Decision review | proposal/review contracts | targeted endpoint | review page | REVIEW | PARTIAL |
| Dossier/verification | services | targeted endpoints | none | VERIFICATION | PARTIAL |
| Audit/integrity | domain/checkpoint | no safe browse API | none | AUDIT | PARTIAL |
| Outbox/inbox/workers | services | no admin read model | none | OPERATIONS | PARTIAL |
| Organizations/memberships/roles | domain/persistence | no management API | none | ADMINISTRATION | PARTIAL |

## 5. Architectural Problems Found

Current navigation mixes Livestock operation, governance and access administration. Entity-kind claims are onboarding input, not authorization. The shell is reusable, but it lacks a capability contract and explicit vertical/context model. Several pages embed bespoke loading/error/empty patterns.

## 6. UI Architectural Principles

1. Backend authorization is authoritative; hidden UI is not enforcement.
2. Navigation derives from server-declared available capabilities when a concrete contract exists.
3. Organization context is always visible; cross-Organization actions require an explicit server-supported context.
4. Domain operation, administration, governance, review, verification, audit, operations, integration and self-service remain separate experiences.
5. Preserve distinctions: Fact/Evidence/Evaluation/Decision; delivery/business completion; unknown/failed; absent/positive.
6. Prefer progressive disclosure and references over raw sensitive payloads.

### Frontend invariants

- Role is never the primary source of visual authorization.
- Active Organization remains visible whenever an action has effect.
- `403 != EMPTY`, `UNKNOWN != FAILED` and `INDETERMINATE != REJECTED`.
- Technical state never becomes a domain conclusion; absence never becomes a positive conclusion.
- `DecisionReview`, `Decision`, `Evaluation` and `Dossier` remain visually distinct.
- Shared components contain no vertical interpretation; a route appears only with a real backend contract.

## 7. Experience Taxonomy

`SELF_SERVICE`: session/profile/password provider links. `DOMAIN_OPERATION`: animal, lot, treatment and other vertical work. `ADMINISTRATION`: access, memberships and Organizations. `GOVERNANCE`: policy/rule lifecycle. `REVIEW`: proposal/review before decision. `VERIFICATION`: dossier/bundle/report. `AUDIT`: read-only history/integrity. `OPERATIONS`: inbox/outbox/quarantine/workers. `INTEGRATION`: connection/profile/diagnostics. `SUPPORT`: privileged, separately authorized diagnosis.

## 8. Application Shell

Retain `ApplicationShell → TopBar + Context + Navigation + MainContent + UserAccountMenu` (**REUSE**). TopBar shows logo, current Organization and account menu. Vertical is a route/module label, not a tenant substitute. Future notification/search affordances remain absent until APIs exist. No role-specific shells.

## 9. Navigation Model

Conceptual groups: Overview; Work (requests/reviews); vertical modules (Livestock); Organizations; People & Access; Governance; Verification; Audit; Operations; Integrations; Settings. A group appears only when a backend capability and route are available. Today only Livestock, access requests and targeted governance/review routes are justified; future groups are **PLANNED**, not routes.

## 10. Organization Context

Show the active Organization persistently, including on destructive/review actions. An `OrganizationSelector` is **NEW_FUTURE**: it requires membership discovery and a server-authorized switch. Relationships, identifiers and counterparty references never imply visibility.

`ContextBanner` is **NEW_FUTURE** for screens whose semantic context materially changes interpretation. It composes only applicable values such as Organization, vertical, purpose, historical reference time, knowledge cutoff or recognition boundary. Likely consumers: Market Eligibility, Decision Review, historical reproduction, Verification and integration diagnostics. It does not replace the persistent Organization context.

## 11. Needs Attention / Work

Model as a future read model/projection, not a universal aggregate or `Task`. A conceptual item has source reference, category, safe reason, severity, times, Organization, target route and server-allowed actions. Initial source is access requests only; review, verification, integrity, quarantine and reconciliation join only with their own read contracts.

## 12. Notifications

`NeedsAttention` means action required; notification means relevant occurrence. Do not derive one from every DomainEvent. A future `NotificationCenter` may initially derive read-only items; persistence, websocket and push require separate decisions.

## 13. Global Search

Future search may federate authorized vertical and transversal results (Animal, Lot, Organization, Decision, Dossier, Bundle). Each provider must authorize before returning existence, label or metadata; 404/empty cannot reveal cross-tenant existence. A universal index is **NOT_NEEDED** until two concrete providers demand it.

## 14. Detail Page Pattern

`EntityDetailPage` is a **NEW_FUTURE pattern**, not a base class: Header (identity/status/context/actions), Summary, optional relations, timeline, evidence/documents, evaluation/decision and audit references. Animal uses domain tabs; Organization/User uses access context; Decision adds authority/reasons; Dossier adds verification dimensions; Integration adds technical state. Omit unsupported sections.

## 15. Status / Reason System

No global status enum. Each presentation carries source domain, code, human label, reason/limitation and severity. `StatusBadge`, `ReasonList`, `LimitationList`, warning/error/information/success are **EXTEND** patterns. Color supplements text/icons. `INDETERMINATE` Decision, `UNKNOWN_RESULT` integration, `QUARANTINED` message and `REVOKED` grant must remain visibly distinct.

## 16. Explainability

Every consequential result should answer “why?” through concise reason lists, limitations, policy/rule references, provenance/evidence references and authority/recognition boundary. Deep technical JSON is diagnostic-only and protected.

`SourceReference` is **NEW_FUTURE**: type, safe identifier, origin, relevant instant, confidence/validation when applicable and a capability-gated “view origin” action. It can compose with Fact, Evidence, territorial capture, imported fact, DecisionReason, Dossier and audit presentation without declaring their semantics identical.

## 17. Timeline / History

Use source-specific timelines: domain events, movements/treatments, reviews, corrections and integration outcomes preserve occurred/recorded/known times, actor, reason and audit reference. A universal merged timeline is premature and may collapse semantics.

## 18. People / Actors / Organizations

Presentation distinguishes authenticated User, Actor, Membership, Organization, counterparty and vertical profile. Do not create Producer/Veterinarian/Buyer applications. Profiles are vertical information; authorization remains context/capability/grant based.

## 19. Verification Center

Future read-only center presents Dossier, Bundle and ValidationReport with separate Integrity, Signature, Trust, Authority, Time, Completeness and Recognition sections. Never reduce this to `VALID=true`; show what was checked and limitations.

## 20. Audit Experience

Predominantly read-only: `AuditReference`, event detail, correction/supersession and integrity status. Do not surface canonical payloads by default. Human audit and technical diagnostics are separate capability-gated surfaces.

## 21. Operations Center

Technical-only future area for Outbox, Inbox, Quarantine, Replay, Reconciliation and Workers. Delivery/acknowledgement/unknown are technical outcomes, never business completion or evidence. Access requires operational/privileged capabilities.

## 22. Integration Center

Future transversal `Integrations → ERP → Odoo` shows Titan-owned connection/profile/contract/health/mapping/reconciliation diagnostics. It does not reproduce Odoo. Odoo implementation is explicitly deferred.

## 23. Settings Hierarchy

Separate My Settings (self-service), Organization Settings (Organization capability) and Platform Settings (platform capability). No empty settings route until a contract exists.

## 24. Functional Design System

| Pattern | Decision |
|---|---|
| ApplicationShell/TopBar/Sidebar/UserAccountMenu | REUSE |
| PageHeader/SectionHeader/Loading/Empty/Error/Unauthorized | EXTEND consistently |
| DataTable/FilterBar/ConfirmationDialog | NEW_FUTURE, only per concrete API |
| StatusBadge/ReasonList/LimitationList/AuditReference | EXTEND as cross-cutting presentation |
| CapabilityGate | NEW_FUTURE; consumes server contract, never enforces |
| NeedsAttention/Timeline/Search/VerificationSummary | NEW_FUTURE, concrete-source first |

## 25. Action Pattern

Actions carry context, capability-independent wording and result feedback. READ is safe; CREATE/EDIT need explicit contract; APPROVE/REJECT/REVIEW/VERIFY/RETRY/REPLAY/RECONCILE/REVOKE/DELETE require server authorization and confirmation/reason when the contract demands it. Never optimistic-success historically relevant actions.

## 26. Error / Empty / Unauthorized Semantics

`EMPTY`, `UNAUTHORIZED/403`, safe `NOT_FOUND/404`, `ERROR`, `PARTIAL`, `UNAVAILABLE` and `INDETERMINATE` are separate components/messages. 403 is never empty; cross-tenant 404 must not reveal existence; no data is not no event; unknown is not failed.

## 27. Responsive Strategy

Shell/self-service/simple reads: **FULL_MOBILE**. Domain detail/search: **READ_MOBILE**. Review/approval forms: **ACTION_LIMITED_MOBILE**. Audit, verification matrices, operations and maps: **DESKTOP_PREFERRED** with safe read fallback. Tables use horizontal access or detail drill-down, not compressed hidden data.

## 28. Accessibility

Keyboard navigation, visible focus, semantic landmarks/headings, labels, accessible dialogs, screen-reader state context, text plus color status, contrast and reduced motion are baseline. Shell menu and mobile sidebar require focus/escape behavior tests.

## 29. Core UI vs Vertical UI Boundaries

Core: shell, context, status/reason presentation, actions, access, verification/audit patterns. Vertical: animal/lot/treatment, market rules and domain terminology. Organization: context/membership surfaces. Integration: technical connector surfaces. Administration is transversal but only API-backed modules enter it.

## 30. Capability Matrix and Priorities

P0: Organization context visibility, consistent status/error semantics. P1: source-backed NeedsAttention and detail pattern, after APIs. P2: verification/audit read surfaces and capability navigation contract. P3: notification center/global search/federation after concrete providers. Priority does not authorize implementation.

## 31. Persona Stress Test

| Scenario | Navigation / constraints |
|---|---|
| Organization administrator | access requests; cannot infer authority from UI |
| Livestock operator | vertical work only; admin routes absent unless server permits |
| limited veterinarian | scoped domain work; no universal veterinarian app |
| decision reviewer | Work/review source; review is not Decision |
| read-only auditor | audit/verification read surface with redaction |
| integration operator | technical Operations/Integrations, not business conclusion |
| two-Organization user | explicit active context; no silent cross-tenant switch |

## 32. Risks

Main risks: role-based frontend architecture, leakage through search/status, collapsing technical/domain state, generalized components before second case, and visual “approval” treated as authority. Controls are server contracts, source-specific patterns and progressive disclosure.

## 33. Conflicts / Gaps

`CONFLICTING`: current shell navigation mixes categories; current entity-kind display can be mistaken for authorization. `ABSENT`: Organization switch, capability manifest, general admin APIs, audit/operations browse models, notifications and search. `PLANNED` documentation is not implementation.

## 34. Human Decisions Required

Future participant taxonomy; Organization relationships and cross-Organization operations; global versus Organization administration; concrete capability grants; review authority; notification policy; sensitive information/redaction; privileged support and integration administration.

## 35. Proposed Implementation Cuts

1. **UI-FOUNDATION-00**: document and enforce these frontend invariants in future design/code review; no component extraction.
2. **UI-FOUNDATION-01**: normalize loading/empty/error/unauthorized/not-found primitives. **Initial cut implemented** after concrete consumers proved the duplication, first in `AdminDashboard`, `AnimalDetail` and `LotDetail`, then extended to `AnimalSearch`, `LotSearch`, `AdminQueue` and `MarketRuleGovernance`.
3. **UI-FOUNDATION-02**: detail page pattern. **Initial cut implemented** with `AnimalDetail` and `LotDetail` as concrete consumers, using compositional components only.
4. **UI-FOUNDATION-03**: Organization context/switch, after membership API and authorization design. Until then, fixed context visibility may expand only on screens that already consume real client-known scope; no selector, no manifest and no semantic `ContextBanner`.
5. **UI-FOUNDATION-04**: server-backed capability/navigation contract, only after ADR-level authorization decision.
6. **UI-FOUNDATION-05**: NeedsAttention projection with two real sources.
6. Verification, Audit, Operations and Integrations follow their safe read models.

## 36. Recommended First Cut

**UI-FOUNDATION-02 initial cut implemented after the baseline guidance.** Treat the invariants as the baseline for every new UI cut. Extract status/reason primitives only when two concrete screens need them. Detail composition may continue incrementally when another concrete page benefits from the same header/section/summary shape. Fixed Organization context visibility was later reinforced in `DecisionReview`, `TreatmentForm`, `AnimalTimeline` and `MarketRuleGovernance` through a small presentation component only; capability navigation and Organization switching remain blocked pending an authorization decision and membership discovery contract.

## 37. Blocking Conditions

Do not implement capability navigation, Organization selection, global search, notifications, audit/operations/verification centers or role-specific applications until the corresponding backend, authorization and redaction contracts exist.

## Decision Log

| Problem | Evidence | Alternatives | Recommendation | Consequences | Reversibility | Human decision |
|---|---|---|---|---|---|---|
| role apps fragment platform | multi-Organization domain + mixed frontend navigation | app per role; capability/context shell | single modular shell | route composition needed | high | no |
| generic task abstraction | one real queue only | universal task; source read models | defer until two sources | no false dashboard | high | no |
| navigation authorization | no manifest API | entity kind; client role; server contract | defer manifest | fewer fake routes | high | yes for contract |
| Organization switching | no membership discovery API | client selector; no selector | visible fixed context | avoids leakage | high | yes |

ADR_REQUIRED: a capability/navigation manifest only if its server representation changes authorization contracts or claims. This Design Package is insufficient to decide its scope and ownership.
