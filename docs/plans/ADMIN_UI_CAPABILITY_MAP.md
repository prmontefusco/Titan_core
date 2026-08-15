# Admin UI Capability Map

## 1. Executive Summary

**Discovery outcome: PROCEED; ADMIN-CUT-01 implemented as an access-request overview.** The repository already
contains an authenticated React shell and a real, organization-scoped access-request queue.
It does not yet expose sufficient administrative APIs to implement a general Admin console.
The first safe cut is therefore an `Overview` that reuses the existing shell and surfaces only
the pending access requests already returned by the backend; it must not infer authority from
the entity-kind claim.

## 2. Frontend, shell and authentication

- React, Vite, TypeScript and `react-router-dom` in `apps/web`.
- OIDC Authorization Code + PKCE is provided by Keycloak; the browser never handles a Titan
  password (`DEVELOPMENT.md`, ADR-0028).
- `ApplicationShell`, `TopBar`, `Sidebar` and `UserAccountMenu` already exist and are reused.
- The frontend sends the active Organization identifier to the API, but the server constructs
  the authoritative `OrganizationContext`; visual hiding is not enforcement.

## 3. Admin capability matrix

| Admin capability | Backend | API | Authorization | Frontend | Status | Gap |
|---|---|---|---|---|---|---|
| Active Organization / session / logout | Implemented | status + OIDC | server context | shell/menu | IMPLEMENTED_BACKEND | no selector |
| Entity-type access requests | Implemented | list and decide | backend permission | queue/dashboard | IMPLEMENTED_BACKEND | no general invitations |
| Organizations and memberships | Persistence/domain | no admin list/edit found | server-side | none | PARTIAL_BACKEND | public admin API/UI |
| Roles and permissions | Persistence/domain | no management API found | Role→Permission server-side | none | PARTIAL_BACKEND | capability contract |
| Decision review | domain/API page exists | review endpoint | authority profile | `DecisionReview` | PARTIAL_BACKEND | general proposal queue remains deferred |
| Policies/rules governance | implemented vertical flow | policy/rule endpoints | backend authorization | governance page | PARTIAL_BACKEND | not a generic platform admin module |
| Dossiers/verification | services/endpoints exist | verification endpoint | contract-specific | no admin surface | READ_ONLY_AVAILABLE | safe listing/query contract |
| Audit/integrity | domain/checkpoints | no safe browsing API found | protected | none | PARTIAL_BACKEND | redacted read model |
| Outbox/inbox/workers | services/persistence | no admin operations API found | technical | none | PARTIAL_BACKEND | diagnostics/read model |
| Livestock daily operation | implemented | existing APIs | domain permissions | animal/lot pages | DOMAIN_OPERATION | must remain outside Admin |

## 4. Proposed information architecture

Only `Overview` and `Access requests` are enabled in ADMIN-CUT-01. Future navigation remains
documented, not rendered: Access, Governance, Reviews, Verification, Audit, Operations,
Integrations and Settings. Their implementation requires a server-backed capability/navigation
contract; entity kinds and frontend routes are not substitutes for authorization.

## 5. Overview and security

`NeedsAttention` may show the real pending-request count, including loading, 403, error and
empty states. It must not manufacture alerts for verification, integrity, messaging or workers.
403 remains an unauthorized state, never an empty list. `DecisionProposal`, `DecisionReview`
and `Decision` remain distinct per ADR-0054.

## 6. ADMIN-CUT-01 — IMPLEMENTED

`ApplicationShell`, `TopBar`, `Sidebar`, `UserAccountMenu`, `AdminDashboard` and `AdminQueue`
are reused. The Overview now shows only the real pending access-request count and routes to the
existing queue; it has explicit loading, empty, error and unauthorized states. No API, migration,
authorization rule, Role/Permission model or dependency was added.

## 7. Deferred capabilities and human decisions

- Organization, Membership, invitation and Role management require public API and authorization
  decisions (RED: tenancy/authorization).
- Operations, audit and verification dashboards require redacted read models and explicit
  capability contracts.
- A generic Administration navigation model must wait for those contracts; it must not use
  `if role == admin` or entity-kind claims as enforcement.
