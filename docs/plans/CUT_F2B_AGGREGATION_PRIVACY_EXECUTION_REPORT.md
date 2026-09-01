# CUT F2B - Aggregation Privacy Runtime Execution Report

Status: IMPLEMENTED AS IN-MEMORY SECURITY PREREQUISITE / NOT PRODUCTION PROFILE / NO BUYER-FACING ACCESS

Date: 2026-08-28

## 1. Scope

CUT F2B implements the smallest runtime prerequisite accepted after ADR-0070: an in-memory `AggregationPrivacyPolicy` assessment for future Market Supply aggregate release.

It does not implement CUT F3. It does not create a buyer-facing endpoint, persistence, migration, query repository, CommercialDemand, CandidatePopulation resolver, cross-tenant herd query, report storage or production privacy threshold.

## 2. Code Changed

- `packages/livestock_application/market_supply_privacy.py`
  - Defines `AggregationPrivacyPolicy`.
  - Defines `AggregationQueryFingerprint`.
  - Defines `AggregationPrivacyInput`.
  - Defines `AggregationPrivacyAssessment`.
  - Defines `AggregationPrivacyAssessmentService`.

The service evaluates an already-built aggregate result before release. It has no database dependency and performs no population resolution or data access.

## 3. Controls Implemented

- Minimum Organization cohort assessment.
- Minimum property cohort assessment.
- Minimum subject cohort assessment.
- High geographic precision suppression for property/precise output.
- Rare attribute filter suppression.
- Excessive filter-combination suppression.
- Difference-attack detection using related query fingerprints and small result deltas.
- Repeated-query detection within an explicitly configured policy window.

## 4. Architectural Boundaries

- `Organization` remains the tenant boundary.
- No Animal field was added.
- No eligibility/readiness boolean was persisted.
- No Policy, Rule, Evaluation, Decision, Dossier or VerificationBundle semantics changed.
- No Evidence/Fact boundary changed.
- No official-source integration was introduced.
- No Odoo, Geodata or sensor behavior changed.

## 5. Security Impact

Positive but preparatory. The runtime now gives future aggregate release code a dedicated suppression gate before any field-level or aggregate result can be returned.

Residual production risk remains high until Product/Security approve concrete policy values, persistence of query audit records, retention, rate limits, uniform external responses and revocation behavior.

## 6. Tenant Isolation Impact

No cross-tenant read path was created. Inputs are caller-provided counts and query fingerprints. Future CUT F3 must prove that authorization and privacy checks happen before any buyer-visible release.

## 7. Temporal Semantics Impact

The query fingerprint requires UTC `requested_at`. Repeated-query evaluation is based on the policy's explicit `repeated_query_window`. No historical Evaluation, Decision, Dossier or VerificationBundle is rewritten.

## 8. Tests Added

- `tests/livestock_application/test_market_supply_privacy.py`

Covered scenarios:

- release permitted when controls pass;
- suppression for insufficient Organization, property and subject cohorts;
- suppression for property/precise geographic precision;
- suppression for rare attribute filters and excessive filter combinations;
- suppression for related-query differencing risk;
- unrelated previous queries do not create differencing risk;
- suppression for repeated query inside policy window;
- validation of explicit policy and UTC query timestamp semantics.

## 9. Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_privacy.py`
- `python -m uv run --locked python -m ruff check packages/livestock_application/market_supply_privacy.py tests/livestock_application/test_market_supply_privacy.py`
- `python -m uv run --locked python -m mypy packages/livestock_application/market_supply_privacy.py tests/livestock_application/test_market_supply_privacy.py`

## 10. Migrations

None.

## 11. HUMAN GATES Remaining

- Approve concrete production `AggregationPrivacyPolicy` profile values.
- Approve query audit persistence model, retention and allowed metadata.
- Approve uniform buyer-facing denial/suppression semantics.
- Approve revocation behavior for new queries and reexecutions.
- Approve any CommercialDemand persistence/API.
- Approve any CandidatePopulation snapshot/digest persistence.
- Approve CUT F3 before any cross-Organization aggregate visibility.
