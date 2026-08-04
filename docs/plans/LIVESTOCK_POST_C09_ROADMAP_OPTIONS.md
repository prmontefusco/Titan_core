# LIVESTOCK_POST_C09_ROADMAP_OPTIONS

Status: PROPOSTA
Date: 2026-08-04
Scope: Decision-oriented roadmap options after the completion of `LIV-C09`

## 1. Purpose

This document organizes the most natural post-`LIV-C09` directions into a small set of explicit roadmap options.

It does not authorize implementation.

It exists to support a human decision about where Titan should invest next.

## 2. Current Position

After `LIV-C09`, Titan already has:

- governed Livestock sanitary facts;
- explainable eligibility and decision flow;
- canonical dossier and derived verification bundle;
- outbound ERP reflection through outbox;
- operational proof of retry, reconciliation, quarantine, replay, and tenant isolation.

The next increment therefore should not reopen the completed baseline.

The next increment should choose one clear frontier.

## 3. Decision Criteria

The preferred next increment is the one that best matches the immediate business objective while preserving:

1. minimal new domain surface;
2. clear authority boundaries;
3. explicit operational semantics;
4. auditable rollout evidence;
5. low risk of reopening completed Livestock stages.

## 4. Option A

### Production-Grade Operational Hardening

#### Objective

Turn the validated local async boundary into a production-ready operational capability.

#### Main scope

- observability dashboards and alerts for outbox/inbox/worker;
- operational reconciliation routines and runbooks;
- dead-letter and incident workflow policy;
- retry tuning, backoff review, and replay operating rules;
- production-safe metrics, logs, and traces;
- failure classification and operator support tooling.

#### Best when

- the architecture is already considered functionally sufficient;
- the main concern is reliability in real operation;
- rollout confidence matters more than adding new business semantics.

#### Advantages

- lowest domain risk;
- high operational value;
- strengthens production readiness without changing sanitary authority.

#### Risks

- may feel less visible as a product feature;
- does not by itself connect Titan to a real ERP.

#### Recommended label

`POST-LIV-01 Operational Hardening`

## 5. Option B

### Real ERP Adapter Contract

#### Objective

Move from validated outbound reflection to a real external ERP integration contract.

#### Main scope

- approved external contract shape;
- connector semantics for external acknowledgement;
- idempotency strategy across the real external boundary;
- timeout, retry, and unknown-result rules with the real target;
- connector authentication, deployment, and support model;
- explicit handling of technical confirmation versus business completion.

#### Best when

- there is a concrete ERP target already chosen;
- the business priority is system-to-system integration;
- rollout depends on external operational interoperability.

#### Advantages

- highest integration impact;
- converts current outbound capability into real business connectivity.

#### Risks

- highest external dependency risk;
- easiest place to accidentally blur authority boundaries;
- may require new architectural approvals depending on the adapter model.

#### Recommended label

`POST-LIV-02 ERP Adapter`

## 6. Option C

### Rollout and Executive Packaging

#### Objective

Turn the completed Livestock capability into something easier to adopt, demonstrate, audit, and sell internally or externally.

#### Main scope

- executive capability map;
- implementation evidence pack;
- rollout checklist by environment or customer;
- operational ownership model;
- demonstration scripts and stakeholder-facing narratives;
- adoption materials for compliance, operations, and product teams.

#### Best when

- the technical baseline is considered sufficient for now;
- the next challenge is adoption, approval, or commercialization;
- internal alignment is more urgent than new engineering surface.

#### Advantages

- fastest path to organizational leverage;
- low architectural risk;
- increases clarity for non-engineering stakeholders.

#### Risks

- does not expand runtime capability directly;
- may postpone important operational or integration work if chosen too early.

#### Recommended label

`POST-LIV-03 Rollout Package`

## 7. Recommendation

If the goal is the best engineering next step, the recommended order is:

1. `POST-LIV-01 Operational Hardening`
2. `POST-LIV-02 ERP Adapter`
3. `POST-LIV-03 Rollout Package`

Reason:

- `POST-LIV-01` builds directly on `LIV-C09`;
- it reduces delivery risk before introducing a real external dependency;
- it keeps Titan in control of authority, semantics, and failure handling before crossing into a production ERP boundary.

## 8. Alternative Recommendation

If the goal is fastest business connectivity and there is already an approved ERP target, then the order can become:

1. `POST-LIV-02 ERP Adapter`
2. `POST-LIV-01 Operational Hardening`
3. `POST-LIV-03 Rollout Package`

This should be chosen only when the external dependency is already concrete and sponsored.

## 9. Decision Output Suggested

The cleanest next decision is:

- choose exactly one option as the next increment;
- authorize a design package first;
- keep implementation blocked until that package is approved.

## 10. Final Note

The most conservative and architecturally aligned next step is `POST-LIV-01 Operational Hardening`.
