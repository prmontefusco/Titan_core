# POST_LIV_02B_ODOO_COMMUNITY_ADAPTER_DESIGN_PACKAGE

Status: PROPOSTA
Design status: APPROVED_IN_PRINCIPLE
Implementation gate: BLOCKED_PENDING_ODOO_TARGET_DECISION
Date: 2026-08-04
Artifact ID: `POST-LIV-02B-DP-v1`
Derived from:

- [LIVESTOCK_EXECUTIVE_CLOSURE_LIV_C01_TO_C09.md](/C:/programing/Titan/docs/plans/LIVESTOCK_EXECUTIVE_CLOSURE_LIV_C01_TO_C09.md)
- [POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE.md)
- [POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT_AND_SIMULATOR_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT_AND_SIMULATOR_DESIGN_PACKAGE.md)
- `POST-LIV-02`
- `POST-LIV-02A`

## 1. Objective

Define the minimum approved path to implement the first concrete ERP adapter using `Odoo Community` as the inaugural real target, while preserving Titan's neutral outbound contract, keeping Odoo-specific semantics inside the adapter boundary, and preventing Odoo from becoming a sanitary source of truth.

This increment treats the external connector surface as a Titan architectural product in its own right:

`Titan Connector API v1`

The Odoo-specific component is therefore the first implementation of that API, not the definition of Titan's external contract itself.

## 2. Scope

This package covers:

- the first concrete mapping from Titan's neutral outbound operational intent to an `Odoo Community` target contract;
- Odoo-specific acknowledgement, rejection, timeout, and unknown-outcome semantics;
- adapter-side identity, correlation, and idempotency behavior for the chosen Odoo interaction model;
- authentication, endpoint, and isolation requirements for a concrete Odoo adapter;
- proof obligations required before implementation of the adapter starts.

This package does not cover:

- inbound Odoo authority over sanitary facts;
- a generic multi-ERP abstraction beyond the already approved neutral Titan contract;
- automatic creation of `Fact`, `Evidence`, `Evaluation`, or `Decision` from Odoo results;
- production rollout, vendor onboarding, or commercial deployment commitments;
- corrections to unrelated repository-wide `mypy` debt;
- automatic correction or compensation of already confirmed external operational effects after later sanitary correction;
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
- [POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE.md)
- [POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT_AND_SIMULATOR_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT_AND_SIMULATOR_DESIGN_PACKAGE.md)
- [0006-entrega-assincrona-com-outbox-e-message-broker.md](/C:/programing/Titan/docs/adr/0006-entrega-assincrona-com-outbox-e-message-broker.md)
- [0020-integracoes-externas-e-validacao-de-fontes.md](/C:/programing/Titan/docs/adr/0020-integracoes-externas-e-validacao-de-fontes.md)
- [0029-rabbitmq-como-message-broker-inicial.md](/C:/programing/Titan/docs/adr/0029-rabbitmq-como-message-broker-inicial.md)
- [0038-executor-de-workers-e-consumo-da-inbox.md](/C:/programing/Titan/docs/adr/0038-executor-de-workers-e-consumo-da-inbox.md)

## 4. Current Proven State

The repository already proves:

- Titan emits a neutral outbound operational intent contract for Livestock treatment reflection;
- Titan distinguishes operation identity from delivery processing and preserves unknown-result honesty;
- local simulator behavior already proves explicit technical and external operational outcomes without binding Titan to one ERP;
- the worker and inbox paths can process the neutral contract without granting sanitary authority to downstream systems.

Confirmed anchors:

- [packages/livestock_application/erp_contract.py](/C:/programing/Titan/packages/livestock_application/erp_contract.py)
- [packages/livestock_application/erp_outbox.py](/C:/programing/Titan/packages/livestock_application/erp_outbox.py)
- [packages/livestock_application/erp_inbox.py](/C:/programing/Titan/packages/livestock_application/erp_inbox.py)
- [apps/worker/livestock_handlers.py](/C:/programing/Titan/apps/worker/livestock_handlers.py)
- [apps/validacao/post_liv_02a_neutral_contract.py](/C:/programing/Titan/apps/validacao/post_liv_02a_neutral_contract.py)

The repository does not yet prove:

- which Odoo Community integration surface is the first approved target;
- which concrete business operation is the first supported external effect;
- which Odoo response semantics count as external receipt, acceptance, or confirmed effect;
- whether Odoo can honor Titan's required idempotency model directly;
- how unknown results are reconciled against Odoo specifically;
- how Odoo credentials, endpoints, and tenant scoping are resolved safely in the first real adapter;
- how Titan references map to Odoo product, lot, company, warehouse or location concepts without silent master-data creation;
- how units and conversions are governed without implicit rounding or stock reinterpretation.

## 5. Architectural Question

How can Titan implement a first concrete `Odoo Community` adapter that translates the already approved neutral operational intent into a real Odoo operation without leaking Odoo models into Titan, over-claiming completion semantics, or weakening historical reproducibility?

## 6. Exact Problem

`POST-LIV-02A` proved that Titan can emit a neutral outbound contract and validate its semantics locally.

The next gap is not generic anymore.

It is target-specific:

- Odoo Community must be chosen as the first real adapter target;
- Odoo-specific request and acknowledgement semantics must be mapped explicitly;
- Odoo-specific limitations around idempotency, callbacks, polling, and external confirmation must be evaluated honestly before code starts.

So this increment is not about redefining Titan's outbound contract.

It is about binding that contract to a concrete Odoo boundary with the minimum necessary surface.

## 7. Principles For This Increment

- Titan's neutral contract remains the canonical outbound intent at the Titan boundary;
- `Titan Connector API v1` is the stable connector-facing contract product for this increment;
- Odoo-specific identifiers, model names, routes, and payloads stay inside the concrete adapter;
- Titan sanitary fact, outbound operational intent, and Odoo administrative effect remain distinct concepts;
- no Odoo response is promoted to sanitary truth;
- HTTP success, RPC success, or queue acceptance are not automatically equivalent to confirmed external effect;
- operation identity, message identity, and delivery-attempt identity remain distinguishable;
- the stable `operation_id` originates in Titan and is preserved externally; local Odoo record identities do not replace or redefine it;
- unknown outcome remains explicit when Odoo semantics do not prove the effect conclusively;
- if Odoo cannot satisfy safe idempotency or confirmation semantics, the adapter remains blocked rather than improvised;
- no automatic master-data creation in Odoo is allowed in the first increment to resolve missing mappings;
- unit preservation is mandatory; conversion, rounding, or packaging transformation require explicit governed mapping;
- the first target implementation must prefer the smallest Odoo surface that still preserves auditability and replay safety.

## 7.1 Supported Connector Capabilities

`Titan Connector API v1` MUST:

- receive operational intent from Titan;
- preserve Titan `operation_id` as the stable external identity;
- support lookup by Titan `operation_id`;
- support duplicate recovery semantics;
- support reconciliation after unknown outcomes;
- preserve adapter and mapping version metadata in technical receipts.

`Titan Connector API v1` MUST NOT:

- produce sanitary authority;
- create `Fact`;
- emit `Evaluation`;
- emit `Decision`;
- alter Titan historical records.

## 8. Candidate Target Shapes

### Alternative A

Bind directly to Odoo inventory movement models as if their write acknowledgement were proof of external completion.

Assessment:

- simplest mapping to code quickly;
- highest risk of conflating write acceptance with durable external effect;
- encourages Titan-facing leakage of Odoo model semantics.

Conclusion:

- rejected.

### Alternative B

Use the neutral Titan contract and map it to one approved Odoo operational endpoint or RPC interaction, with explicit classification of receipt, acceptance, rejection, and unknown-result semantics.

Assessment:

- smallest coherent first adapter;
- aligned with `POST-LIV-02` and `POST-LIV-02A`;
- keeps the generic contract stable while allowing a concrete target.

Conclusion:

- recommended.

### Alternative C

Create a broader Odoo synchronization subsystem that mirrors multiple Odoo objects and lifecycle states before proving the minimum target operation.

Assessment:

- significantly more complex;
- increases risk of second-source transport state and vendor coupling;
- not justified for the inaugural adapter.

Conclusion:

- rejected.

### Alternative D

Expose Titan through a thin custom `titan_connector` module inside Odoo Community, with a versioned Odoo-side endpoint dedicated to Titan's first operation.

Assessment:

- adds one extra maintained component on the Odoo side;
- offers the strongest chance of stable idempotency, constrained authorization, explicit correlation lookup, and target-specific response semantics;
- may reduce leakage of internal Odoo model structure into the Titan adapter;
- introduces packaging, upgrade, and compatibility responsibilities for the Odoo module.

Conclusion:

- must be compared explicitly against direct generic API usage before implementation is authorized.

## 8.1 Odoo Integration Surface Comparison

### Option 1

Use Odoo generic remote APIs directly.

Advantages:

- less code inside Odoo;
- simpler initial installation footprint;
- no custom Odoo addon lifecycle to maintain.

Risks:

- weaker control over semantic response shape;
- harder idempotency guarantees;
- more exposure to internal Odoo model structure;
- potentially multiple Odoo calls for one Titan intent;
- more complex reconciliation and permission hardening.

### Option 2

Use a thin custom Odoo module such as `titan_connector`.

Advantages:

- dedicated, versioned endpoint;
- explicit idempotency storage or unique constraint on the Odoo side;
- atomic target operation boundary;
- cleaner lookup by Titan `operation_id`;
- reduced leakage of Odoo internal model names to Titan.

Risks:

- addon installation and upgrade burden;
- Odoo version compatibility maintenance;
- extra security review surface;
- extra codebase to validate operationally.

Decision rule:

- the preferred option is the one that introduces the smallest total cross-boundary semantic risk while preserving explicit idempotency, correlation lookup, minimum privilege, and reproducible reconciliation.

Chosen direction for this package:

- `Titan Connector API v1` as the stable connector product contract;
- `Titan Connector for Odoo Community` as the first concrete implementation of that API.

## 9. Recommended Minimum

The minimum recommended path is Alternative B.

That means:

- select one Odoo Community interaction surface as the first approved target;
- keep Titan's external contract neutral and versioned;
- implement a concrete adapter that translates neutral intent to Odoo-specific request data internally;
- record only explicit technical or external operational outcomes that the approved Odoo contract can actually prove;
- preserve unknown and indeterminate cases instead of silently normalizing them.

This increment should prove the first real target, not broaden the Titan domain.

The first approved external effect should prefer command acceptance of an idempotent operational intent over a richer end-to-end stock workflow unless stronger semantics are explicitly proven and approved.

## 10. Odoo Decisions That Must Be Proven Before Implementation

The following proposal defines the first concrete Odoo target with the smallest surface judged coherent for Titan.

It is intentionally conservative: it optimizes for explicit correlation, idempotency, and auditable command acceptance before broader stock workflow semantics.

### 10.1 Proposed First Target Decision

1. `Odoo Community version:`
   - Proposed: `Odoo Community 18.x`
   - Rationale:
     - current enough to justify a first concrete adapter target;
     - narrow major-version range reduces surface drift;
     - exact patch version remains deployment-specific and outside Titan contract semantics.
   - Compatibility rule:
     - minor upgrades inside `18.x` are expected to remain compatible;
     - major upgrades require explicit compatibility validation;
     - unsupported versions are rejected explicitly.

1.1 `Titan Connector API version:`
   - Proposed: `v1`
   - Rationale:
     - freezes the connector surface independently from Odoo and from future Titan internal evolution;
     - allows later evolution such as `Titan Connector API v2` without implicit semantic drift.

2. `Tenant topology:`
   - Proposed: `one Odoo database per Titan Organization integration`
   - Rejected for first increment:
     - multi-company shared database;
     - mixed topology support.
   - Rationale:
     - smallest isolation model;
     - simplest credential and endpoint scoping;
     - avoids ambiguous company context in the inaugural adapter.

3. `Integration interface:`
   - Proposed: `custom controller endpoint`
   - Transport expectation:
     - HTTPS request from Titan adapter to Odoo addon controller;
     - JSON body defined by the target contract.
   - Rationale:
     - stronger control over response semantics than generic XML-RPC or JSON-RPC ORM exposure;
     - allows explicit idempotency and lookup by Titan `operation_id`;
     - reduces leakage of internal Odoo model semantics to Titan.
   - Invariant:
     - the controller is the only supported integration surface for the first increment;
     - direct XML-RPC or JSON-RPC access to internal stock models is intentionally unsupported.

4. `Custom module required: YES / NO`
   - Proposed: `YES`
   - Module concept: `titan_connector`
   - Rationale:
     - safest path to stable semantic response shape;
     - cleanest place for Odoo-side idempotency storage and unique constraint;
     - enables minimum-privilege service surface narrower than generic ORM access.

5. `First external effect:`
   - Proposed: `command acceptance of operational intent`
   - Concrete meaning:
     - Odoo accepts an idempotent request to register a livestock treatment operational consumption intent;
     - the first increment proves acceptance and durable correlation, not full stock-effect finality.
   - Not included in the first increment:
     - generalized stock effect confirmation workflow;
     - automatic reservation, accounting, or compensating stock choreography.

6. `Odoo models hidden behind adapter:`
   - Proposed:
     - all internal stock and connector persistence models remain hidden behind `titan_connector`;
     - Titan only knows the controller contract and returned receipt classes.
   - Explicitly forbidden at Titan boundary:
     - `stock.move`;
     - `stock.picking`;
     - `product.product`;
     - direct ORM model names as contract fields.

7. `Idempotency storage:`
   - Proposed:
     - Odoo addon table or equivalent connector-owned persistence with unique constraint on Titan `operation_id`;
     - request digest stored alongside the operation to detect same-id different-payload conflicts.
   - Decision rule:
     - same `operation_id` plus same material request returns deterministic duplicate recovery;
     - same `operation_id` plus different material request is a conflict.

8. `Correlation lookup:`
   - Proposed:
     - Odoo lookup by Titan `operation_id` through the `titan_connector`;
     - Odoo local record identifiers are returned only as Odoo-side references, never as replacement identities.

9. `Confirmation model:`
   - Proposed: `synchronous command acceptance with later query-based reconciliation support`
   - Meaning:
     - synchronous response proves controller receipt and classified acceptance or rejection;
     - it does not automatically prove the full downstream stock effect unless the contract explicitly says so.
   - Rejected for first increment:
     - callback-based confirmation;
     - no-confirmation blind fire-and-forget.

10. `Reconciliation method:`
   - Proposed:
     - adapter queries `titan_connector` by Titan `operation_id`;
     - reconciliation returns one of:
       - accepted and still pending internally;
       - accepted and applied according to approved contract semantics;
       - rejected;
       - unknown or indeterminate.

11. `Titan Organization -> Odoo tenant/company mapping:`
   - Proposed:
     - one Titan Organization maps to one Odoo database integration profile;
     - no multi-company fan-out in the first increment.
   - Clarification:
     - this is an implementation strategy for the first connector target, not a Titan architectural invariant.

12. `Medication -> product mapping:`
   - Proposed:
     - explicit preconfigured mapping profile outside the outbound payload;
     - adapter rejects missing or ambiguous mapping.

13. `MedicationBatch -> lot mapping:`
   - Proposed:
     - explicit preconfigured mapping profile outside the outbound payload;
     - adapter rejects missing or ambiguous mapping;
     - no automatic lot creation in the first increment.

14. `Property -> warehouse/location mapping:`
   - Proposed:
     - explicit preconfigured mapping profile outside the outbound payload;
     - adapter rejects missing or ambiguous mapping;
     - no warehouse or location inference by free text or fallback search.

15. `Unit conversion policy:`
   - Proposed:
     - preserve Titan unit exactly at adapter boundary;
     - allow conversion only through explicit versioned mapping profile;
     - reject incompatible or unapproved conversion;
     - no silent rounding from liquid dose to package count.

16. `Service identity and minimum permissions:`
   - Proposed:
     - dedicated Odoo technical user restricted to the `titan_connector` surface;
     - no general administrative ORM permissions in the first increment;
     - privileges only for the approved command and reconciliation lookup.

17. `Timeout and retry policy:`
   - Proposed:
     - bounded synchronous timeout model with explicit distinction between:
       - network timeout;
       - transport timeout;
       - application timeout;
     - unknown-result classification on timeout after request dispatch uncertainty;
     - retry preserves Titan `operation_id` and creates a new delivery attempt identity;
     - automatic retry only when safe under the approved idempotency rules.

18. `Unknown-result policy:`
   - Proposed:
     - timeout, interrupted connection, or ambiguous Odoo response yields `EXTERNAL_UNKNOWN`;
     - no silent conversion of unknown to accepted or rejected;
     - reconciliation by `operation_id` is mandatory before any destructive replay judgment.

19. `Correction/compensation explicitly deferred: YES / NO`
   - Proposed: `YES`
   - Meaning:
     - later sanitary correction does not mutate the prior Odoo effect silently;
     - compensation, reversal, or follow-up external intent remains a separate approved concern.

### 10.2 Consequence Of This Proposal

Under this proposal, `POST-LIV-02B` becomes implementable as:

- a Titan-side concrete adapter for one Odoo Community target;
- a thin Odoo-side `Titan Connector for Odoo Community` module implementing `Titan Connector API v1`;
- synchronous command acceptance plus query-based reconciliation;
- explicit preconfigured mapping profile;
- one database per Titan Organization integration profile.

Implementation remains blocked only if this proposal is rejected or if the repository reveals a conflicting authority constraint not currently evidenced.

## 11. Odoo-Specific Contract Mapping Requirements

The adapter specification must define at minimum:

1. Titan neutral operation identity;
2. Titan message identity;
3. Titan delivery-attempt identity;
4. Odoo external reference that preserves Titan `operation_id`;
5. Odoo-facing idempotency mechanism or compensating reconciliation mechanism;
6. request payload mapping from Titan neutral fields to Odoo-specific fields;
7. Odoo response mapping back into approved external outcome classes;
8. timeout semantics;
9. retry ownership;
10. reconciliation query model if confirmation is not immediate.

Identity invariants:

- Titan `operation_id` is the stable identity of the outbound operational intent;
- Odoo local `record_id` or equivalent is only the identity of the Odoo-side artifact;
- `delivery_attempt_id` identifies each technical call separately;
- Odoo local identifiers do not replace, redefine, or supersede Titan `operation_id`.

The Titan side must not grow fields such as:

- `odoo_model`;
- `odoo_record_id`;
- `stock_move_id`;
- `product_product_id`;
- `stock_picking_id`.

Those belong inside the Odoo adapter or its internal persistence, not in Titan's neutral contract.

## 11.1 Mapping Policy

The adapter must define explicit mapping policy for:

- Titan medication reference -> Odoo product;
- Titan medication batch -> Odoo lot or serial;
- Titan Organization -> Odoo database, company, or equivalent tenant scope;
- Titan property or operational stock scope -> Odoo warehouse or location;
- Titan quantity and unit -> Odoo product quantity and unit of measure.

The mapping policy must distinguish explicitly:

- mapping missing;
- mapping ambiguous;
- mapping disabled;
- external entity absent;
- incompatible unit;
- conversion not approved.

Invariants:

- the first increment does not create Odoo master data automatically to resolve missing mappings;
- missing or ambiguous mapping does not become silent fallback or implicit lookup expansion;
- no fallback by first warehouse is allowed;
- no search by warehouse name is allowed as silent recovery strategy;
- unit conversion is governed, versioned, and explicit;
- incompatible or unapproved conversion is rejected honestly.

## 12. Security And Isolation Requirements

The Odoo adapter boundary must prove:

- destination host is deployment-controlled and never selected from payload content;
- credentials are environment-scoped and, when needed, Organization-scoped;
- no Odoo credential, token, session cookie, or secret is logged;
- request and response validation are explicit;
- TLS expectations are declared;
- timeouts, retry limits, and circuit-breaker conditions are declared;
- callback or polling endpoints, if any, cannot choose `Organization` or overwrite Titan correlation;
- no cross-tenant credential or endpoint reuse occurs silently;
- authenticated Odoo access is not treated as sufficient authorization for the target operation;
- the Odoo service identity has minimum required permissions only.

The design must also freeze which tenant topology is supported in the first increment and how company context is resolved safely inside that topology.

## 13. Proposed Deliverables

### 13.1 Odoo target contract decision

A document that freezes:

- the first chosen Odoo interface;
- the first chosen Odoo business operation;
- whether a thin custom Odoo module is required;
- the exact meaning of success, rejection, and unknown outcome for that interface.

### 13.2 Odoo mapping specification

A document defining:

- Titan neutral request fields;
- Odoo-specific translated request fields;
- allowed omissions and defaults;
- correlation rules;
- returned identifiers and their semantic meaning;
- mapping prerequisites for medication, batch, tenant scope, property scope, and unit semantics.

### 13.3 Odoo outcome matrix

A matrix separating at minimum:

- adapter transport attempted;
- Odoo endpoint reached;
- Odoo request accepted technically;
- Odoo effect confirmed by the contract;
- Odoo explicit rejection;
- Odoo duplicate safely recovered;
- Odoo duplicate detected but unresolved;
- Odoo timeout with unknown outcome;
- Odoo reconciliation result after prior unknown outcome.

### 13.4 Odoo adapter boundary note

A document proving:

- credential location;
- endpoint resolution;
- timeout model;
- retry model;
- reconciliation ownership;
- logging and observability restrictions;
- adapter name and version;
- supported Odoo version range;
- mapping profile version used by the adapter.

### 13.5 Adapter technical receipt

An adapter receipt model preserving at minimum:

- `adapter_name`;
- `adapter_version`;
- `connector_api_version`;
- `target_product`;
- `target_version_range`;
- `mapping_profile_version`;
- `neutral_contract_version`.

## 14. Tests Required

At minimum:

1. same Titan outbound intent preserves the same external operation identity across retries;
2. each delivery attempt remains independently observable;
3. a new Titan intent receives a new Odoo operation correlation identity;
4. Odoo technical receipt is distinguishable from confirmed external effect;
5. explicit Odoo rejection remains outside sanitary authority;
6. timeout after possible Odoo execution remains unknown until reconciliation;
7. duplicate delivery and safe duplicate recovery are distinguishable;
8. Odoo response payload cannot choose another `Organization`;
9. Odoo-specific identifiers remain inside the adapter boundary and do not leak into Titan neutral payloads;
10. malicious destination override from payload is ignored or rejected;
11. tenant A credentials and endpoint cannot be used for tenant B;
12. validation can run against an approved Odoo-compatible stub before real deployment;
13. if Odoo lacks safe idempotency semantics, implementation blocks or uses a formally approved compensating mechanism;
14. late confirmation after a prior unknown outcome is preserved historically and resolved idempotently.
15. product mapping missing is rejected explicitly;
16. batch mapping missing is rejected explicitly;
17. two Odoo products mapped to one Titan reference are treated as ambiguous and rejected;
18. unit incompatibility is rejected explicitly;
19. unapproved conversion is rejected explicitly;
20. wrong Odoo company or tenant context is rejected explicitly;
21. Odoo service identity authenticated but under-privileged is rejected explicitly;
22. same `operation_id` with materially different payload is rejected as conflict;
23. Odoo creates the external record but the adapter loses the response and later reconciliation finds it deterministically;
24. adapter version changes between attempt and reconciliation without rewriting prior history;
25. unsupported Odoo version is rejected before effect execution;
26. correction of the sanitary record does not silently mutate the already confirmed external effect.

## 15. Acceptance Criteria

- [ ] Odoo Community is explicitly frozen as the first concrete adapter target.
- [ ] The design is approved in principle while implementation remains blocked pending target decisions.
- [ ] The first Odoo interface and operation are identified explicitly.
- [ ] The tenant topology supported by the first increment is identified explicitly.
- [ ] The design compares generic Odoo API access against a thin custom Odoo module before target approval.
- [ ] Titan's neutral outbound contract remains unchanged at the Titan boundary.
- [ ] Odoo-specific model names and identifiers remain inside the concrete adapter.
- [ ] Operation identity, message identity, and delivery-attempt identity remain distinguishable.
- [ ] Odoo local identifiers do not replace Titan `operation_id`.
- [ ] External receipt, acceptance, and confirmed effect are not conflated.
- [ ] Unknown Odoo outcome remains explicit when effect confirmation is insufficient.
- [ ] Duplicate detection and safe duplicate recovery are distinguishable.
- [ ] Mapping failures and unit incompatibilities are explicit and never normalized silently.
- [ ] Odoo credentials, tokens, and protected payload are excluded from logs and diagnostics.
- [ ] Organization isolation is preserved through endpoint and credential resolution.
- [ ] Odoo authentication is separated from operation authorization.
- [ ] Implementation remains blocked until Odoo idempotency and confirmation semantics are proven sufficient.
- [ ] No Odoo-originated result creates sanitary authority in Titan.

## 16. Risks

- choosing an Odoo surface whose success semantics are weaker than expected;
- discovering late that Odoo cannot support the required idempotency model directly;
- overfitting Titan to the first Odoo operation;
- leaking vendor-specific identifiers into Titan contracts or diagnostics;
- under-specifying reconciliation after timeout or partial external completion;
- permitting silent creation of Odoo master data or silent unit conversion to hide mapping gaps;
- binding the adapter to the wrong Odoo tenant topology too early;
- mixing pre-existing repository type debt with adapter work and reducing auditability of the increment.

## 17. Blocking Conditions

Stop and raise a change request if this increment requires:

- changing Titan's neutral outbound contract for Odoo-specific convenience;
- giving Odoo authority over sanitary facts, evidence, evaluations, or decisions;
- introducing a second canonical transport state machine;
- embedding vendor-specific model semantics in Titan contracts;
- using an Odoo target whose idempotency and confirmation semantics cannot be proven safe;
- requiring silent master-data creation or implicit unit conversion to make the first effect succeed;
- changing `DOMAIN.md`, `ARCHITECTURE.md`, or ADRs.

Stop and wait for explicit approval if the first Odoo target requires:

- a custom Odoo module not yet approved as part of the target contract;
- a new public API shape exposed by Titan;
- a new mutable operational endpoint outside the approved adapter boundary.

Known deferred concern:

- later sanitary correction or compensation must produce a new outbound operational intent and must not silently rewrite or delete the prior Odoo-side effect. The concrete compensation semantics remain outside this increment unless separately approved.

## 18. Recommended Next Step

Human review and approval of this design package.

Only after approval should implementation begin for `POST-LIV-02B`.

Recommended implementation sequence after approval:

1. freeze the first Odoo interface and operation in code-facing documentation;
2. implement the smallest concrete Odoo adapter behind the existing neutral contract;
3. validate it first against a controlled Odoo-compatible stub;
4. keep real Odoo instance validation for `POST-LIV-02C`.
