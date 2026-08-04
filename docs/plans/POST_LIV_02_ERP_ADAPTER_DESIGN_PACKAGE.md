# POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE

Status: PROPOSTA
Design status: APPROVABLE_IN_CONCEPT
Implementation gate: BLOCKED_PENDING_TARGET_CONTRACT
Date: 2026-08-04
Artifact ID: `POST-LIV-02-DP-v1`
Derived from:

- [LIVESTOCK_EXECUTIVE_CLOSURE_LIV_C01_TO_C09.md](/C:/programing/Titan/docs/plans/LIVESTOCK_EXECUTIVE_CLOSURE_LIV_C01_TO_C09.md)
- [LIVESTOCK_POST_C09_ROADMAP_OPTIONS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_POST_C09_ROADMAP_OPTIONS.md)
- [POST_LIV_01_OPERATIONAL_HARDENING_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/POST_LIV_01_OPERATIONAL_HARDENING_DESIGN_PACKAGE.md)
- `LIV-C08`
- `LIV-C09`
- `POST-LIV-01`

## 1. Objective

Define the minimum approved path to move from Titan's validated outbound ERP reflection to a real external ERP adapter contract, without transferring sanitary authority, introducing silent business completion semantics, or creating a second source of truth for operational state.

## 2. Scope

This package covers:

- the external contract boundary for a real ERP adapter;
- explicit acknowledgement semantics across broker, adapter, and ERP;
- idempotency identity across Titan and the real external target;
- timeout, retry, rejection, and unknown-result rules against a real connector;
- adapter-side authentication and deployment boundary at a conceptual level;
- proof obligations required before implementation starts.

This package does not cover:

- inbound ERP authority over sanitary facts;
- new Livestock sanitary domain concepts;
- silent conversion of technical confirmation into sanitary completion;
- production rollout packaging;
- changes to `DOMAIN.md`, `ARCHITECTURE.md`, or ADRs unless a blocker proves them insufficient.

## 3. Authority Inputs

- [AGENTS.md](/C:/programing/Titan/AGENTS.md)
- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md)
- [LIV-C08_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C08_DESIGN_PACKAGE.md)
- [LIV-C09_OPERATIONAL_INTEGRATION_VALIDATION_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C09_OPERATIONAL_INTEGRATION_VALIDATION_DESIGN_PACKAGE.md)
- [POST_LIV_01_OPERATIONAL_HARDENING_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/POST_LIV_01_OPERATIONAL_HARDENING_DESIGN_PACKAGE.md)
- [0006-entrega-assincrona-com-outbox-e-message-broker.md](/C:/programing/Titan/docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md)
- [0020-integracoes-externas-e-validacao-de-fontes.md](/C:/programing/Titan/docs/adr/0020-integracoes-externas-e-validacao-de-fontes.md)
- [0029-rabbitmq-como-message-broker-inicial.md](/C:/programing/Titan/docs/adr/0029-rabbitmq-como-message-broker-inicial.md)
- [0038-executor-de-workers-e-consumo-da-inbox.md](/C:/programing/Titan/docs/adr/0038-executor-de-workers-e-consumo-da-inbox.md)

## 4. Current Proven State

The repository already proves:

- authoritative sanitary treatment registration inside Titan;
- outbound ERP command reflection via transactional outbox;
- explicit worker-side handling of the Livestock outbound contract;
- tenant-safe operational diagnostics derived from native transport records;
- retry, quarantine, replay, reconciliation, and unknown-result supportability in the local validated boundary.

Confirmed code anchors:

- [packages/livestock_application/erp_outbox.py](/C:/programing/Titan/packages/livestock_application/erp_outbox.py)
- [packages/livestock_application/erp_inbox.py](/C:/programing/Titan/packages/livestock_application/erp_inbox.py)
- [packages/core_infrastructure/persistence/outbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/outbox.py)
- [packages/core_infrastructure/persistence/inbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/inbox.py)
- [packages/core_infrastructure/persistence/operational_support.py](/C:/programing/Titan/packages/core_infrastructure/persistence/operational_support.py)
- [apps/worker/main.py](/C:/programing/Titan/apps/worker/main.py)

## 5. Architectural Question

How can Titan connect the approved outbound sanitary reflection to a real ERP target while preserving Titan as the sole sanitary authority and keeping technical delivery outcomes explicitly separate from business or sanitary completion?

## 6. Exact Problem

Titan can already emit and validate the local operational boundary.

What it does not yet prove is:

- what the real external acknowledgement means;
- what exactly counts as external duplicate protection;
- how unknown outcome is reconciled when the real external side may already have executed;
- how connector authentication and deployment fit without moving authority outward;
- how the adapter contract avoids becoming a silent business workflow.

So the remaining problem is not Livestock domain modeling.

It is external-boundary semantics.

## 7. Principles For This Increment

- Titan remains the sole sanitary authority;
- technical confirmation is not sanitary completion;
- external idempotency must be explicit and reusable across retries;
- unknown result must remain honest and reconcilable;
- no ERP-originated technical event creates `Evidence`, `Fact`, `Evaluation`, or `Decision`;
- connector convenience must not override auditability;
- deployment architecture must not create hidden authority or state duplication.

## 8. Alternatives

### Alternative A

Treat broker acceptance or local worker completion as sufficient proof of ERP completion.

Assessment:

- lowest implementation effort;
- architecturally incorrect;
- violates the explicit boundary preserved in `LIV-C08`, `LIV-C09`, and `POST-LIV-01`.

Conclusion:

- rejected.

### Alternative B

Implement a real adapter where Titan publishes the outbound command and records only explicit technical delivery evidence from the external boundary, with unknown-result honesty preserved.

Assessment:

- minimal authority-preserving approach;
- aligned with current outbox/inbox/worker design;
- still requires precise contract semantics before implementation.

Conclusion:

- recommended.

### Alternative C

Create a larger ERP synchronization subsystem with internal business workflow authority.

Assessment:

- highest complexity;
- highest chance of creating a second truth about execution;
- not justified by current evidence.

Conclusion:

- rejected unless a future blocker proves the minimum adapter insufficient.

## 9. Recommended Minimum

The minimum recommended path is Alternative B.

That means:

- Titan emits an authenticated and auditable outbound operational intent derived from an authoritative sanitary fact;
- the outbound intent is authoritative regarding its origin and requested correlation, but it does not unilaterally determine the ERP's accounting, inventory, financial, or administrative truth;
- the adapter reports only explicit technical and external operational outcomes defined by the approved contract;
- the external effect identity is stable across retries;
- uncertainty is preserved as uncertainty;
- the adapter does not create new sanitary meaning.

Outbound sanitary fact, operational intent, and external effect are distinct concepts.

## 10. Decisions That Must Be Proven Before Implementation

The implementation must not begin until the following are answered explicitly:

1. what is the concrete ERP target or target class;
2. what exact outbound contract shape is approved;
3. what acknowledgement the ERP or adapter can really provide;
4. what identifier the ERP accepts for idempotency;
5. what evidence proves external rejection versus timeout versus uncertain outcome;
6. what operational actor is allowed to reconcile unknown external outcomes;
7. whether the adapter is in-process, sidecar, separate service, or external connector.

Additional gate conditions:

8. whether confirmation is synchronous, callback-based, polling-based, or unavailable;
9. whether the target supports explicit external idempotency and how it is enforced;
10. what structured rejection classes and retry rules are contractually available;
11. how tenant scoping, endpoint resolution, and credentials are separated by environment and, when needed, by organization.

## 11. Target Capabilities

The increment should eventually deliver:

1. a concrete outbound adapter contract;
2. explicit delivery outcome semantics across every phase;
3. stable external idempotency behavior;
4. adapter authentication and connectivity model;
5. executable validation against a realistic stub or approved target-compatible simulator.

## 12. Proposed Deliverables

### 12.1 External contract specification

A versioned contract defining:

- request payload;
- response or callback shape if any;
- correlation and idempotency identifiers;
- supported technical outcomes;
- supported external operational outcomes;
- unsupported or indeterminate cases;
- timeouts and retry ownership.

The Titan-side contract must remain neutral regarding ERP implementation details.

ERP-specific identifiers and model names remain inside the concrete adapter.

### 12.2 Delivery outcome matrix

A matrix separating at minimum:

- broker accepted;
- consumer accepted;
- adapter attempted;
- external received;
- external accepted;
- external applied;
- external rejected;
- external outcome unknown;
- duplicate safely recovered;
- duplicate detected but unresolved.

External receipt, external acceptance, and confirmed external effect are distinct outcomes.

A successful HTTP response, broker acknowledgement, or worker completion is never promoted to confirmed external effect unless the external contract explicitly guarantees that meaning.

The matrix must also declare:

- whether confirmation is synchronous, callback-based, polling-based, or unavailable;
- whether callback duplication is possible;
- how late confirmation after reconciliation is treated;
- whether the adapter or Titan is responsible for polling;
- how callback authentication is validated when callbacks exist.

### 12.3 Adapter boundary document

A document proving:

- where credentials live;
- where retries happen;
- who owns reconciliation;
- how multi-tenant separation is enforced;
- what is logged and what is forbidden in logs.

Minimum security requirements:

- secrets per environment;
- rotation model;
- no secrets in repository;
- TLS requirements;
- mutual authentication or token model according to the approved target;
- replay protection for callback or confirmation flow;
- destination allowlist;
- strict request and response validation;
- size limits;
- timeout policy;
- circuit breaker policy;
- SSRF prevention.

The external destination must be deployment-controlled and never selected from sanitary payload content.

## 13. Tests Required

At minimum:

1. same outbound intent reuses the same external idempotency identity;
2. new legitimate intent gets a new external identity;
3. repeated delivery attempts preserve the external operation identity while keeping attempt identity independently observable;
4. timeout after possible external execution does not silently retry destructively;
5. external rejection remains outside sanitary authority and does not alter sanitary truth;
6. external receipt, acceptance, and confirmed effect are distinguishable;
7. callback duplication is handled idempotently;
8. late callback after timeout or reconciliation is preserved historically and resolved idempotently;
9. callback or query response cannot select another `Organization` or overwrite Titan correlation;
10. external rejection classes expose structured reason codes and retry classification;
11. tenant A cannot observe or operate tenant B adapter flow;
12. tenant-scoped idempotency does not collide across organizations;
13. adapter logs exclude protected sanitary payload, credentials, and ERP-specific unsafe internals;
14. simulated unknown outcome remains explicitly indeterminate;
15. executable validation does not depend on a real production ERP;
16. malicious or payload-provided destination data is ignored or rejected;
17. if the ERP does not support adequate idempotency, implementation remains blocked or requires a formally approved compensating mechanism.

## 14. Acceptance Criteria

- [ ] Titan remains the sole sanitary authority.
- [ ] Outbound sanitary fact, operational intent, and external effect are represented as distinct concepts.
- [ ] No technical acknowledgement is treated as sanitary proof or business completion.
- [ ] Operation identity, message identity, and delivery-attempt identity are distinguishable.
- [ ] External idempotency identity is explicit and stable across retry.
- [ ] Unknown external outcome remains honest and reconcilable.
- [ ] Duplicate detection and safe duplicate recovery are distinguishable.
- [ ] External receipt, acceptance, and confirmed effect are not conflated.
- [ ] The contract declares whether confirmation is synchronous, callback-based, polling-based, or unavailable.
- [ ] External outcomes use structured reason codes and explicit retry classification.
- [ ] The adapter boundary does not create a new canonical workflow state machine.
- [ ] Organization isolation is preserved across the real connector boundary.
- [ ] The external destination is deployment-controlled and cannot be selected from message payload.
- [ ] ERP-specific identifiers and model names remain inside the concrete adapter.
- [ ] Callback or query responses cannot select `Organization` or overwrite correlation established by Titan.
- [ ] Credentials and endpoints are tenant- and environment-scoped where required.
- [ ] A late external confirmation after an unknown result is handled idempotently and preserved historically.
- [ ] Credentials, tokens, and protected sanitary payload are excluded from logs and diagnostics.
- [ ] Implementation depends on an approved concrete contract, not an inferred one.

## 15. Risks

- confusing ERP technical completion with sanitary completion;
- adding connector behavior that rewrites or overrides Titan history;
- choosing an idempotency strategy the ERP cannot actually honor;
- under-specifying timeout semantics and creating destructive retries;
- leaking protected payload into adapter logs or observability;
- building the adapter before the target contract is concretely approved.

External rejection may include distinct classes such as:

- retryable technical failure;
- permanent contract rejection;
- external business rejection;
- authentication failure;
- rate limiting.

Those remain outside sanitary authority, but they require distinct operational handling and retry classification.

## 16. Blocking Conditions

Stop and raise a change request if the increment requires:

- inbound ERP authority over sanitary facts;
- new sanitary business semantics inside the adapter;
- new aggregate or entity to explain transport state;
- unapproved external vendor commitment, credentials, or deployment architecture;
- changes to architectural authority documents.

If the chosen ERP cannot provide sufficient confirmation or idempotency semantics for safe operation, implementation remains blocked unless a compensating mechanism is formally approved.

## 17. Recommended Next Step

Human review and approval of this design package.

Only after approval should implementation begin for `POST-LIV-02`.

Recommended decomposition after approval:

1. `POST-LIV-02A` - neutral external contract plus target-compatible simulator;
2. `POST-LIV-02B` - first concrete ERP adapter;
3. `POST-LIV-02C` - validation against a controlled real instance.
