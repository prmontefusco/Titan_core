# POST_LIV_02B_ODOO_TARGET_DECISION

Status: PROPOSTA
Decision status: APPROVED_IN_PRINCIPLE
Implementation gate: BLOCKED_PENDING_HUMAN_APPROVAL
Date: 2026-08-04
Artifact ID: `POST-LIV-02B-TD-v1`
Derived from:

- [POST_LIV_02B_ODOO_COMMUNITY_ADAPTER_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/POST_LIV_02B_ODOO_COMMUNITY_ADAPTER_DESIGN_PACKAGE.md)
- [POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT_AND_SIMULATOR_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT_AND_SIMULATOR_DESIGN_PACKAGE.md)
- [POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/POST_LIV_02_ERP_ADAPTER_DESIGN_PACKAGE.md)

## 1. Decision Objective

Freeze the first concrete technical target for `POST-LIV-02B` so the Odoo connector can be implemented without inventing interface, tenant, idempotency, or confirmation semantics during coding.

## 2. Frozen Target

The first concrete target is:

- `Titan Connector API v1`
- implemented by `Titan Connector for Odoo Community`
- targeting `Odoo Community 18.x`

This means the first real integration is not defined as "Titan talks to Odoo models".

It is defined as:

`Titan -> Titan Connector API v1 -> Titan Connector for Odoo Community -> Odoo Community`

## 3. Technical Target Decision

### 3.1 Odoo product and version

- Target product: `Odoo Community`
- Supported major version range for first increment: `18.x`
- Compatibility policy:
  - minor upgrades inside `18.x` are expected to remain compatible;
  - major upgrades require explicit compatibility validation;
  - unsupported versions are rejected explicitly.

### 3.2 Tenant topology

- First supported topology: `one Odoo database per Titan Organization integration profile`
- Not supported in the first increment:
  - multi-company shared database;
  - mixed database and company routing;
  - implicit company resolution.

This is a first-connector implementation strategy, not a Titan architectural invariant.

### 3.3 Integration interface

- First supported interface: `custom controller endpoint`
- Payload transport: `HTTPS + JSON`
- Controller status:
  - the controller is the only supported integration surface for the first increment;
  - direct XML-RPC or JSON-RPC access to internal Odoo stock models is intentionally unsupported.

### 3.4 Odoo-side component

- Required: `YES`
- Component name: `Titan Connector for Odoo Community`
- Contract role:
  - first implementation of `Titan Connector API v1`;
  - hides Odoo internal model semantics from Titan;
  - owns Odoo-side idempotency, correlation lookup, and connector-specific response semantics.

## 4. First Supported External Effect

- First effect class: `command acceptance of operational intent`
- First concrete meaning:
  - Odoo accepts an idempotent operational consumption intent derived from a sanitary treatment already confirmed in Titan.

The first increment does not claim:

- generalized stock workflow finality;
- accounting finality;
- reservation workflow completion;
- sanitary truth transfer;
- automatic compensation of later sanitary corrections.

## 5. Identity Model

- Canonical external identity: Titan `operation_id`
- Titan transport identity: `message_id`
- Titan technical retry identity: `delivery_attempt_id`
- Odoo local identity: connector-owned record identifier and any internal Odoo references

Invariants:

- Titan `operation_id` remains the stable identity of the external intent;
- Odoo local identifiers do not replace or redefine Titan `operation_id`;
- same `operation_id` plus same request digest is duplicate recovery;
- same `operation_id` plus different material request digest is conflict.

## 6. Confirmation Model

- Initial model: `synchronous command acceptance`
- Required extension: `query-based reconciliation by Titan operation_id`
- Not used in the first increment:
  - callbacks;
  - fire-and-forget delivery without reconciliation path.

Outcome classes the connector must support:

- `EXTERNAL_RECEIVED`
- `EXTERNAL_ACCEPTED`
- `EXTERNAL_REJECTED`
- `EXTERNAL_UNKNOWN`

`EXTERNAL_APPLIED` may only be emitted if the approved controller contract proves that meaning explicitly.

## 7. Idempotency And Lookup

- Idempotency storage owner: `Titan Connector for Odoo Community`
- Minimum rule:
  - unique constraint or equivalent guarantee on Titan `operation_id`
- Conflict protection:
  - request digest stored with the operation
- Lookup rule:
  - reconciliation queries the connector by Titan `operation_id`

## 8. Mapping Policy

Mappings are external configuration, not payload content.

Required mappings:

- Titan medication -> Odoo product
- Titan medication batch -> Odoo lot or serial
- Titan Organization -> Odoo database integration profile
- Titan property or stock scope -> Odoo warehouse or location
- Titan quantity and unit -> Odoo quantity and unit of measure interpretation

Forbidden in the first increment:

- automatic master-data creation;
- fallback by first warehouse;
- search by warehouse name as silent recovery;
- implicit unit conversion;
- silent rounding from dose unit to package quantity.

## 9. Security Model

- dedicated Odoo technical identity with minimum privilege
- credentials scoped by environment and integration profile
- destination host controlled by deployment, never by payload
- no credential, token, cookie, or protected payload in logs
- explicit request and response validation

Authentication is not authorization.

Successful authentication to Odoo does not itself prove permission for the target operation.

## 10. Timeouts And Unknowns

The first implementation must distinguish:

- network timeout
- transport timeout
- application timeout

Any timeout or interrupted response that leaves external execution uncertain must produce `EXTERNAL_UNKNOWN`.

`EXTERNAL_UNKNOWN` requires reconciliation by Titan `operation_id` before any destructive replay decision.

## 11. Deferred Topics

Still out of scope for this decision:

- real Odoo instance validation in `POST-LIV-02C`
- later sanitary correction producing compensating external intents
- support for multi-company tenant topology
- support for other ERP products
- repository-wide `mypy` debt outside this increment

## 12. Acceptance Checklist

- [ ] `Titan Connector API v1` is frozen as the connector product surface.
- [ ] `Titan Connector for Odoo Community` is frozen as the first implementation.
- [ ] `Odoo Community 18.x` is frozen as the first supported target range.
- [ ] `custom controller endpoint` is frozen as the only supported first interface.
- [ ] direct XML-RPC or JSON-RPC access to internal Odoo stock models remains unsupported.
- [ ] first external effect is frozen as command acceptance of operational intent.
- [ ] Titan `operation_id` remains the stable external identity.
- [ ] synchronous acceptance plus query-based reconciliation is frozen as the first confirmation model.
- [ ] explicit mapping policy is required and silent master-data creation is forbidden.
- [ ] timeout ambiguity produces `EXTERNAL_UNKNOWN`, never silent success.

## 13. Recommended Next Step

Human approval of this target decision artifact.

Only after approval should implementation begin for `POST-LIV-02B` under the frozen target described here.
