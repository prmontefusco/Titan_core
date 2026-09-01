# Progressive Disclosure Threat Model

Status: ACCEPTED ARCHITECTURE BASELINE / SECURITY DESIGN REQUIRED BEFORE PRODUCTION / CUT F NOT AUTHORIZED

Date: 2026-08-28

## Assets

- Producer identity.
- Property identity and location.
- Animal identifiers.
- Individual sanitary facts and treatments.
- Evidence, Dossier and VerificationBundle material.
- Readiness counts and gap summaries.
- CommercialDemand metadata.
- Audit and access history.

## Trust Boundaries

- Organization remains the tenant boundary.
- Buyer/frigorifico Organization owns its `CommercialDemand`.
- Producer Organization owns its herd, facts, evidence and subject details.
- Aggregate analysis crosses boundaries only after explicit authorization.
- Cache, projection and report materialization are not authorization.

## Threats

| Threat | Example | Required Control |
|---|---|---|
| Filter inference | Buyer narrows by geography, breed and window until one producer remains | Aggregation privacy policy, query limits, minimum cohort assessment |
| Small group disclosure | Aggregate of one property reveals readiness of that property | Dynamic disclosure safety assessment |
| Difference attack | Buyer repeats query with one changed filter and subtracts counts | Query audit, rate limits, differencing controls |
| Timing inference | Immediate change after producer action reveals event | freshness bands, delayed aggregation where required |
| Geography inference | Regional filter reveals property identity | geospatial precision reduction and FieldScope |
| Attribute combination | Rare attributes identify Animal/group | risk assessment before releasing dimensions |
| Existence leak | 404/empty response distinguishes no data from no access | uniform denial and inaccessible/unknown handling |
| Purpose creep | Aggregate read reused for export, IA or redistribution | Purpose-bound Authorization and FieldScope |
| Revocation confusion | Buyer keeps using old report as if current | report validity, generated_at, revoked-access handling |
| Evidence leakage | aggregate explanation links to raw Evidence/Dossier | separate Evidence/artifact sharing path |

## Accepted Revocation Semantics

Revocation must stop future access after effective time. It cannot erase material already legitimately delivered.

- New query: denied.
- Query reexecution: denied.
- New analytical report: denied.
- New detailed disclosure: denied.
- Previously delivered material remains historical/auditable and does not prove current authorization.
- Export/redistribution is denied by default unless explicitly authorized.

## Security Decisions Still Required Before Production

- Concrete `AggregationPrivacyPolicy` profile.
- Minimum floors by Organization, property and subject where applicable.
- Dynamic risk factors and suppression/generalization behavior.
- Query fingerprinting and differencing detection design.
- Audit tier, retention and allowed metadata.
- FieldScope for Phase A aggregate output.
- Producer opt-in authority and revocation workflow.
