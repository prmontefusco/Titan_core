# POST_LIV_01_OPERATIONAL_HARDENING_DESIGN_PACKAGE

Status: PROPOSTA
Date: 2026-08-04
Artifact ID: `POST-LIV-01-DP-v1`
Derived from:

- [LIVESTOCK_EXECUTIVE_CLOSURE_LIV_C01_TO_C09.md](/C:/programing/Titan/docs/plans/LIVESTOCK_EXECUTIVE_CLOSURE_LIV_C01_TO_C09.md)
- [LIVESTOCK_POST_C09_ROADMAP_OPTIONS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_POST_C09_ROADMAP_OPTIONS.md)
- `LIV-C09`

## 1. Objective

Define the minimum post-`LIV-C09` operational hardening increment required to turn the already validated local async boundary into a production-grade operational capability, without expanding Livestock sanitary semantics or transferring authority away from Titan.

## 2. Scope

This package covers:

- operational observability for outbox, inbox, worker, quarantine, replay, and reconciliation;
- explicit runtime diagnostics for `RESULTADO_DESCONHECIDO`, retry, quarantine, and duplicate recovery;
- operational runbook-oriented evidence;
- safe support tooling and read models when strictly needed for operations;
- executable validation of the new observable behaviors.

This package does not cover:

- real ERP adapter implementation;
- new Livestock domain semantics;
- inbound ERP authority;
- changes to `DOMAIN.md`, `ARCHITECTURE.md`, or existing ADRs unless a blocking contradiction appears;
- broader rollout/commercial packaging.

## 3. Authority Inputs

- [AGENTS.md](/C:/programing/Titan/AGENTS.md)
- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md)
- [LIV-C09_OPERATIONAL_INTEGRATION_VALIDATION_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C09_OPERATIONAL_INTEGRATION_VALIDATION_DESIGN_PACKAGE.md)
- [0006-entrega-assincrona-com-outbox-e-message-broker.md](/C:/programing/Titan/docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md)
- [0029-rabbitmq-como-message-broker-inicial.md](/C:/programing/Titan/docs/adr/0029-rabbitmq-como-message-broker-inicial.md)
- [0038-executor-de-workers-e-consumo-da-inbox.md](/C:/programing/Titan/docs/adr/0038-executor-de-workers-e-consumo-da-inbox.md)

## 4. Current Proven State

After `LIV-C09`, the repository already proves:

- outbound Livestock treatment reflection through transactional outbox;
- worker-side explicit handling of `livestock.erp.treatment_application.command`;
- inbox duplicate recovery, retry scheduling, quarantine, replay boundary, and tenant isolation;
- outbox unknown-result retry and expired-claim reconciliation;
- executable validation of the minimum `domain event -> outbox -> inbox -> worker outcome` chain.

Confirmed code anchors:

- [packages/core_infrastructure/persistence/outbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/outbox.py)
- [packages/core_infrastructure/persistence/inbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/inbox.py)
- [apps/worker/main.py](/C:/programing/Titan/apps/worker/main.py)
- [apps/worker/livestock_handlers.py](/C:/programing/Titan/apps/worker/livestock_handlers.py)
- [apps/validacao/liv_c09_integracao_operacional.py](/C:/programing/Titan/apps/validacao/liv_c09_integracao_operacional.py)

## 5. Architectural Question

How can Titan make the approved async boundary operationally supportable in production without introducing a new business source of truth, a parallel workflow engine, or ERP-dependent semantics?

## 6. Exact Problem

`LIV-C09` proved correctness and minimum operational behavior.

It did not yet prove that operators can:

- observe the health of the async boundary quickly;
- distinguish technical states without reading raw tables or code;
- triage unknown results and quarantine safely;
- identify tenant-scoped incidents without exposing protected payload;
- operate replay/reconciliation with production-safe evidence and bounded authority.

So the remaining problem is not domain modeling.

It is operational supportability.

## 7. Principles For This Increment

- reuse before creation;
- observability before automation;
- operator evidence before operator convenience;
- no new sanitary authority;
- no payload leakage for the sake of diagnostics;
- no production support feature may silently mutate historical domain records;
- technical state must stay explicitly technical.

## 8. Alternatives

### Alternative A

Rely on current tests and direct database inspection only.

Assessment:

- lowest immediate effort;
- weakest production supportability;
- fails the platform-quality expectation from `AGENTS.md`.

Conclusion:

- rejected.

### Alternative B

Add operational read models, diagnostics, metrics, and runbook-oriented scripts on top of the current outbox/inbox contracts.

Assessment:

- minimal new domain surface;
- aligned with existing architecture;
- directly strengthens production readiness.

Conclusion:

- recommended.

### Alternative C

Introduce a dedicated operational orchestration subsystem or workflow model.

Assessment:

- highest complexity;
- highest risk of creating a second source of truth for transport state;
- not proven necessary by current evidence.

Conclusion:

- rejected unless a future blocker proves existing concepts insufficient.

## 9. Recommended Minimum

The minimum recommended path is Alternative B.

That means:

- keep the current outbox/inbox/worker model;
- add operational visibility and bounded operational tooling only;
- avoid new aggregate, entity, or domain table unless a concrete gap is proven;
- prefer derived diagnostics over new persistent business concepts.

The operational summary is a derived diagnostic projection.

It does not replace the native states and records of Outbox, Inbox, publication claims, quarantine, replay, or reconciliation.

When the underlying sources disagree or are insufficient, the summary reports an explicit diagnostic condition such as `INDETERMINATE` or `INCONSISTENT` instead of selecting one state silently.

## 10. Target Capabilities

The increment should deliver, at minimum:

1. a tenant-safe operational summary for outbox/inbox health;
2. a clear distinction between pending, claimed, unknown, quarantined, duplicated, and recovered states;
3. executable operational validation steps or scripts for incident triage;
4. explicit operator-facing reason codes for replay, retry, quarantine, and reconciliation paths;
5. production-safe logs/metrics/traces without sanitary payload exposure.

Those labels are diagnostic classifications only, not a new canonical state machine.

## 11. Affected Areas

Likely affected technical areas:

- `packages/core_application/outbox.py`
- `packages/core_application/inbox.py`
- `packages/core_infrastructure/persistence/outbox.py`
- `packages/core_infrastructure/persistence/inbox.py`
- `apps/worker/`
- `apps/validacao/`
- possibly a minimal read-only API surface if operational support cannot be expressed safely by script alone

Any new API must remain strictly operational and read-oriented unless a separate approval authorizes more.

## 12. Proposed Deliverables

### 12.1 Operational summary contract

A read-only operational summary that reports, per `Organization` and bounded scope:

- pending outbox messages;
- active claims;
- expired claims;
- unknown results;
- unknown results currently reconcilable;
- unknown results requiring human intervention;
- quarantined messages;
- duplicate deliveries detected;
- duplicate recoveries completed safely;
- last reconciliation instant;
- oldest pending age;
- oldest unknown age when derivable;
- observation instant;
- scope and filters applied;
- recommended next action for unknown-result diagnostics;
- whether automatic retry is currently blocked;
- reason code when retry is blocked or when evidence is insufficient.

Definition:

A duplicate recovery means that a repeated delivery was correlated with an already processed idempotency identity and resolved without executing the protected effect again.

A duplicate delivery detected but not safely resolved is reported separately.

### 12.2 Operational validation script

A script in `apps/validacao` that:

- resolves `OrganizationContext` from authenticated or controlled execution context;
- shows requests and responses;
- demonstrates diagnosis of at least one unknown-result path and one quarantine path;
- does not require copying identifiers by hand.

The script must not enumerate organizations, choose the first tenant found, or infer tenant identity from operational messages.

### 12.3 Runbook-oriented evidence

At least one artifact or script flow that explains:

- what to inspect first;
- which state means retry is allowed;
- which state means replay is allowed;
- which state remains technical-only and must not be read as business completion.

Inside this increment:

- read-only operational summary;
- diagnostic evidence;
- scripts that exercise already approved mechanisms;
- audit visibility over replay, retry, quarantine, and reconciliation already performed.

Outside this increment unless separately approved:

- endpoint to trigger retry;
- endpoint to release quarantine;
- endpoint to execute replay;
- endpoint to force reconciliation.

This increment may observe and validate existing replay, retry, quarantine, and reconciliation mechanisms.

It does not introduce a new mutable operational API.

Any endpoint capable of triggering those actions requires separate authorization and threat review.

## 13. Tests Required

At minimum:

1. operational summary returns tenant-scoped counts only;
2. organization B cannot read organization A operational state;
3. unknown-result path appears distinctly from success and rejection;
4. contradictory or insufficient evidence is reported as `INDETERMINATE` or `INCONSISTENT`;
5. quarantine path remains visible without exposing protected payload;
6. replay audit remains attributable to operator and reason;
7. reconciliation changes operational state without altering sanitary domain history;
8. executable validation script runs without manual identifier copy;
9. logs or diagnostics avoid medication, animal, dose, or personal data;
10. duplicate detection and safe duplicate recovery are distinguishable;
11. tenant-scoped diagnostics and platform-wide operational metrics remain under separate authorization contracts.

## 14. Acceptance Criteria

- [ ] No new sanitary domain concept is introduced without proof of insufficiency of current concepts.
- [ ] Operational state remains separate from sanitary authority.
- [ ] The operational summary is explicitly a derived projection and never a replacement for native Outbox/Inbox records.
- [ ] Unknown, retry, quarantine, duplicate, and reconciliation states are operationally visible.
- [ ] Contradictory or insufficient transport evidence is reported as `INCONSISTENT` or `INDETERMINATE`, never normalized silently.
- [ ] Duplicate detection and safe duplicate recovery are distinguishable.
- [ ] Unknown results expose the permitted next action and whether automatic retry is blocked.
- [ ] Organization isolation is preserved in operational diagnostics.
- [ ] OrganizationContext is resolved from authenticated or controlled context and is never guessed or enumerated.
- [ ] Tenant summaries and platform-wide operational metrics use separate authorization contracts.
- [ ] Every operational summary declares its observation instant and scope.
- [ ] Support tooling does not expose protected sanitary payload.
- [ ] The increment provides executable validation, not only prose instructions.
- [ ] No new mutable operational endpoint is introduced without separate approval.
- [ ] No later roadmap option is implicitly authorized by artifacts produced here.

## 15. Risks

- creating an operator convenience feature that leaks protected payload;
- accidentally turning support diagnostics into a second workflow authority;
- exposing cross-tenant metadata through aggregated views;
- overengineering a dashboard or subsystem before the minimum supportability gap is proven.

Tenant-facing operational summaries are scoped to one `Organization`.

Cross-tenant fleet metrics, when required for platform operations, are restricted to platform operators, use minimized labels, and are not exposed through the same contract as tenant diagnostics.

## 16. Blocking Conditions

Stop and raise a change request if the increment requires:

- a new aggregate or entity to model transport state;
- incompatible authorization changes;
- persistent storage of protected payload for observability purposes;
- a real ERP target, credentials, or deployment commitment;
- changes to architectural authority documents.

## 17. Recommended Next Step

Human review and approval of this design package.

Only after approval should implementation begin for `POST-LIV-01`.
