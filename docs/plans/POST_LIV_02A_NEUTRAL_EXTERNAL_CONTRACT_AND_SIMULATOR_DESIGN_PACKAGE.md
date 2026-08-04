# POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT_AND_SIMULATOR_DESIGN_PACKAGE

Status: PROPOSTA
Design status: APPROVABLE_IN_CONCEPT
Implementation gate: BLOCKED_PENDING_HUMAN_APPROVAL
Date: 2026-08-04
Artifact ID: `POST-LIV-02A-DP-v1`
Derived from:

- [LIVESTOCK_EXECUTIVE_CLOSURE_LIV_C01_TO_C09.md](/C:/programing/Titan/docs/plans/LIVESTOCK_EXECUTIVE_CLOSURE_LIV_C01_TO_C09.md)
- [LIVESTOCK_POST_C09_ROADMAP_OPTIONS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_POST_C09_ROADMAP_OPTIONS.md)
- [POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE.md)
- `POST-LIV-02`

## 1. Objective

Define the minimum approved increment that converts the `POST-LIV-02` architectural direction into an implementable neutral outbound contract plus a target-compatible simulator, without introducing a concrete ERP adapter, vendor-specific Titan semantics, or any new sanitary source of truth.

## 2. Scope

This package covers:

- a Titan-side neutral outbound operational contract;
- explicit contract identities for operation, message, and delivery attempt;
- explicit external acknowledgement classes that do not overstate completion;
- a target-compatible simulator boundary for executable validation;
- the minimum validation evidence required before any concrete ERP adapter starts.

This package does not cover:

- Odoo, Dolibarr, SAP, or any other real ERP adapter implementation;
- vendor-specific request models inside Titan contracts;
- production credentials or live deployment wiring;
- inbound ERP authority over sanitary facts;
- new Livestock domain concepts;
- changes to `DOMAIN.md`, `ARCHITECTURE.md`, or ADRs unless a blocker proves them insufficient.

## 3. Authority Inputs

- [AGENTS.md](/C:/programing/Titan/AGENTS.md)
- [VISION.md](/C:/programing/Titan/VISION.md)
- [DOMAIN.md](/C:/programing/Titan/DOMAIN.md)
- [ARCHITECTURE.md](/C:/programing/Titan/ARCHITECTURE.md)
- [DEVELOPMENT.md](/C:/programing/Titan/DEVELOPMENT.md)
- [docs/CHECKLIST_DE_IMPLEMENTACAO.md](/C:/programing/Titan/docs/CHECKLIST_DE_IMPLEMENTACAO.md)
- [LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md](/C:/programing/Titan/docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_STATUS.md)
- [POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE.md)
- [0006-entrega-assincrona-com-outbox-e-message-broker.md](/C:/programing/Titan/docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md)
- [0020-integracoes-externas-e-validacao-de-fontes.md](/C:/programing/Titan/docs/adr/0020-integracoes-externas-e-validacao-de-fontes.md)
- [0029-rabbitmq-como-message-broker-inicial.md](/C:/programing/Titan/docs/adr/0029-rabbitmq-como-message-broker-inicial.md)
- [0038-executor-de-workers-e-consumo-da-inbox.md](/C:/programing/Titan/docs/adr/0038-executor-de-workers-e-consumo-da-inbox.md)

## 4. Current Proven State

The repository already proves:

- Titan emits outbound Livestock operational reflection through the transactional outbox;
- worker-side consumption remains explicit and technically scoped;
- inbox, replay, quarantine, reconciliation, and unknown-result handling already exist for local operational reliability;
- `POST-LIV-01` added a derived operational support summary without creating a second transport truth.

Confirmed anchors:

- [packages/livestock_application/erp_outbox.py](/C:/programing/Titan/packages/livestock_application/erp_outbox.py)
- [packages/livestock_application/erp_inbox.py](/C:/programing/Titan/packages/livestock_application/erp_inbox.py)
- [apps/worker/livestock_handlers.py](/C:/programing/Titan/apps/worker/livestock_handlers.py)
- [apps/worker/main.py](/C:/programing/Titan/apps/worker/main.py)
- [packages/core_infrastructure/persistence/outbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/outbox.py)
- [packages/core_infrastructure/persistence/inbox.py](/C:/programing/Titan/packages/core_infrastructure/persistence/inbox.py)
- [packages/core_application/operational_support.py](/C:/programing/Titan/packages/core_application/operational_support.py)
- [packages/core_infrastructure/persistence/operational_support.py](/C:/programing/Titan/packages/core_infrastructure/persistence/operational_support.py)

The repository does not yet prove:

- a neutral, versioned external ERP contract approved for Titan;
- a simulator that exercises real external acknowledgement semantics while remaining vendor-neutral at the Titan boundary;
- the exact split between operation identity, message identity, and delivery-attempt identity in the external contract.

## 5. Architectural Question

How can Titan define a neutral outbound external contract and executable simulator that preserve the approved authority boundary, without leaking ERP-specific semantics into Titan and without requiring a real ERP before contract validation begins?

## 6. Exact Problem

`POST-LIV-02` already established the correct architectural direction:

- Titan produces the authoritative sanitary-origin operational intent;
- the adapter or target reports only explicit technical or external operational outcomes;
- unknown remains unknown when confirmation is insufficient.

The remaining gap is narrower:

- Titan still lacks a concrete neutral contract artifact;
- there is no approved simulator contract to validate acknowledgement semantics;
- implementation could drift into vendor-specific fields too early if the neutral contract is not fixed first.

So this increment is not about building a real connector yet.

It is about fixing the contract boundary before any vendor binding exists.

## 7. Principles For This Increment

- reuse the approved outbox and worker foundation before creating new transport abstractions;
- keep Titan contracts neutral and push ERP-specific translation into future concrete adapters;
- separate operation identity, message identity, and delivery-attempt identity explicitly;
- derive operational meaning from explicit evidence only;
- preserve `UNKNOWN`, `INDETERMINATE`, and `INCONSISTENT` when evidence is insufficient or contradictory;
- simulator behavior must validate contract semantics, not invent sanitary authority;
- no concrete external target is implied merely because the simulator resembles one target class;
- no new aggregate, entity, or canonical state machine may be introduced unless existing concepts are proven insufficient.

## 8. Alternatives

### Alternative A

Skip the neutral contract and go directly to a first ERP-specific adapter.

Assessment:

- fastest path to a concrete connector;
- highest risk of leaking vendor semantics into Titan;
- weakens future adapter portability;
- increases chance of retrofitting the contract after code already depends on it.

Conclusion:

- rejected.

### Alternative B

Define a neutral Titan-side external contract and a target-compatible simulator before any real adapter.

Assessment:

- smallest surface that closes the current architectural gap;
- keeps vendor binding deferred to a later stage;
- allows executable validation of identities, acknowledgements, and unknown outcomes;
- aligned with `POST-LIV-02` and the post-LIV governance direction.

Conclusion:

- recommended.

### Alternative C

Define the neutral contract only on paper and defer executable validation until the real adapter.

Assessment:

- lower short-term effort;
- leaves acknowledgement semantics unproven in runtime behavior;
- delays discovery of contract gaps until a more expensive stage.

Conclusion:

- rejected because executable validation is part of the minimum safety proof.

## 9. Recommended Minimum

The minimum recommended path is Alternative B.

That means:

- define a versioned neutral outbound contract owned by Titan;
- define a simulator contract that exercises the same approved semantics expected from the first target class;
- keep ERP-specific translation and credentials out of this increment;
- validate the semantics through tests and an executable validation script before any concrete adapter starts.

This increment should prove the contract, not the vendor.

## 10. Target Contract Concepts

The neutral contract must describe at least:

1. outbound operational intent identity;
2. message identity;
3. delivery-attempt identity;
4. correlation identity preserved across retries;
5. tenant-safe scoping rules;
6. request payload sections that are allowed at the neutral boundary;
7. explicit acknowledgement classes;
8. structured rejection classes;
9. unknown-result rules;
10. callback or polling semantics when applicable;
11. observation timestamps and provenance;
12. replay and late-confirmation behavior.

The neutral contract must not include vendor-specific names such as:

- ERP table names;
- vendor model names;
- vendor record identifiers as Titan concepts;
- target-specific URLs inside payload content.

## 11. Simulator Obligations

The simulator must be target-compatible in behavior, but not authoritative for Titan domain truth.

It must support at minimum:

1. accepted request with explicit external receipt only;
2. accepted request with later external confirmation;
3. explicit external rejection;
4. timeout with unknown external outcome;
5. duplicate delivery correlated by the same operation identity;
6. duplicate delivery safely recovered without repeating the protected external effect;
7. malformed or unauthorized callback or response rejection;
8. late confirmation after prior unknown classification.

The simulator is a validation instrument.

It is not a source of sanitary facts, evidence, evaluations, or decisions.

## 12. Proposed Deliverables

### 12.1 Versioned neutral contract document

A repository artifact describing:

- contract version;
- neutral request schema;
- neutral acknowledgement and rejection schema;
- identity model;
- retry and timeout rules;
- callback or polling expectations;
- explicit indeterminate and inconsistent diagnostic cases.

### 12.2 Outcome semantics matrix

A matrix separating at minimum:

- outbound intent created;
- outbox persisted;
- worker claimed;
- external request attempted;
- external receipt confirmed;
- external acceptance confirmed;
- external effect confirmed;
- external rejection confirmed;
- outcome unknown;
- duplicate detected;
- duplicate safely recovered;
- inconsistent evidence;
- indeterminate evidence.

### 12.3 Simulator behavior specification

A document defining:

- supported scenarios;
- how identities are preserved;
- which responses are synchronous versus deferred;
- how callback or polling is represented if included;
- what reason codes are emitted;
- what scenarios remain blocked or unsupported.

### 12.4 Executable validation plan

A validation plan describing:

- which script will exercise the simulator;
- how organization context is resolved safely;
- what evidence must be printed per step;
- what assertions are mandatory for safe approval.

## 13. Tests Required

At minimum:

1. same outbound intent preserves the same operation identity across retry;
2. delivery attempts remain independently observable;
3. a new legitimate intent receives a new operation identity;
4. tenant A operation identity does not collide with tenant B;
5. external receipt, acceptance, and confirmed effect remain distinct;
6. duplicate detection and safe duplicate recovery remain distinct;
7. timeout after possible execution remains unknown until explicit evidence arrives;
8. late confirmation after timeout is preserved historically and resolved idempotently;
9. malformed callback or response is rejected without changing correlation;
10. unauthorized callback or response cannot bind a different organization;
11. simulator never creates sanitary `Fact`, `Evidence`, `Evaluation`, or `Decision`;
12. destination selection cannot be influenced by payload content;
13. indeterminate and inconsistent conditions are surfaced explicitly;
14. validation remains executable without a real ERP instance;
15. unsupported target semantics keep the next increment blocked instead of silently assumed.

## 14. Acceptance Criteria

- [ ] A versioned neutral contract artifact exists.
- [ ] Titan-side contract semantics are explicitly separated from vendor translation semantics.
- [ ] Operation identity, message identity, and delivery-attempt identity are distinguishable.
- [ ] Retry preserves the operation identity while creating a new attempt identity when appropriate.
- [ ] External receipt, acceptance, and confirmed effect are not conflated.
- [ ] Duplicate detection and safe duplicate recovery are distinguishable.
- [ ] Unknown, indeterminate, and inconsistent outcomes remain explicit when evidence is insufficient.
- [ ] Simulator behavior is defined for success, rejection, duplicate, timeout, and late-confirmation scenarios.
- [ ] No vendor-specific contract fields are introduced into Titan concepts.
- [ ] No simulator output creates sanitary authority.
- [ ] Organization scoping and correlation safety are explicit.
- [ ] The increment remains implementable without a live ERP.
- [ ] The next concrete adapter stage stays blocked until this contract package is approved and implemented.

## 15. Risks

- contract neutrality may be weakened by premature target-specific convenience fields;
- simulator behavior may over-promise confirmation semantics not actually guaranteed by the first real target;
- retry and unknown semantics may still be misread as business completion if reason codes are underspecified;
- identity handling may be conflated if operation and attempt scopes are not tested separately;
- a too-abstract contract may become unusable for the first real adapter.

## 16. Blocking Conditions

Stop and raise a change request if this increment requires:

- new sanitary domain authority or reinterpretation;
- changes to `DOMAIN.md`, `ARCHITECTURE.md`, or existing ADRs;
- introduction of a concrete ERP dependency before contract approval;
- a new aggregate, entity, or table solely to summarize transport state;
- hardcoded vendor semantics at the Titan contract boundary.

Stop and wait for explicit target clarification if the first target class cannot be simulated without choosing incompatible acknowledgement semantics.

## 17. Recommended Next Step

Human review and approval of this design package.

Only after approval should implementation begin for `POST-LIV-02A`.

Recommended follow-on order:

1. implement the neutral contract artifact and simulator boundary;
2. validate it with automated tests and an executable script;
3. only then open `POST-LIV-02B` for the first concrete ERP adapter.
