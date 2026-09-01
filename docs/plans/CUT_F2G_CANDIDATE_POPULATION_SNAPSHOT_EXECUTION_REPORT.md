# CUT F2G - Candidate Population Snapshot Execution Report

Status: IMPLEMENTED AS IN-MEMORY APPLICATION MODEL / NO PERSISTENCE / NO API / NO BUYER-FACING ACCESS

Date: 2026-08-28

## 1. Scope

CUT F2G implements the approved `CandidatePopulationCriteria -> PopulationResolver -> CandidatePopulationSnapshot` direction as an in-memory application model.

It does not implement CUT F3. It does not create persistence, migration, endpoint, worker, cross-tenant query, CommercialDemand, SupplyForecast, SupplyDemandAnalysis or buyer-facing visibility.

## 2. Code Changed

- `packages/livestock_application/market_supply_population.py`
  - Defines `CandidatePopulationCriteria`.
  - Defines `CandidatePopulationSubject`.
  - Defines `CandidatePopulationExclusion`.
  - Defines `CandidatePopulationSnapshot`.
  - Defines `CandidatePopulationResolver`.

The resolver receives candidate subjects already supplied by the caller and never reads Animal, property, database or another Organization.

## 3. Semantics

- Criteria declares Organization, purpose, Policy/version, `reference_time`, `knowledge_cutoff`, commercial window, subject type, required tags and explicit exclusions.
- Resolver includes only subjects matching Organization, subject type, authorization/accessibility, cutoff and required tags.
- Exclusions are summarized by reason and count.
- Snapshot carries canonical `criteria_digest` and `snapshot_digest`.
- Public summary exposes counts/digests/exclusion summaries, not individual subject IDs.

## 4. Architectural Boundaries

- No aggregate root was created.
- No persistence or migration was introduced.
- No cross-Organization data read was introduced.
- No buyer-facing output was introduced.
- No Animal, Policy, Rule, Evaluation, Decision, Dossier or VerificationBundle semantics changed.
- Absence/inaccessibility remains explicit and is not interpreted as a negative fact.

## 5. Security Impact

Positive but preparatory. Future Market Supply orchestration can reference an explicit population snapshot and digest without leaking candidate membership in the public summary.

Remaining production risk: authorization-backed population resolution, snapshot persistence, digest profile, audit linkage and public disclosure policy remain gated.

## 6. Tenant Isolation Impact

No tenant boundary changed. Subjects from another Organization are excluded rather than traversed.

## 7. Temporal Semantics Impact

`reference_time`, `knowledge_cutoff`, optional commercial window and subject `known_at` must be UTC. Subjects known after the cutoff are excluded as `NOT_KNOWN_AT_CUTOFF`.

## 8. Tests Added

- `tests/livestock_application/test_market_supply_population.py`

Covered scenarios:

- deterministic snapshot digest independent of input order;
- explicit and inaccessible exclusions;
- subject known after cutoff excluded;
- subject from another Organization excluded;
- public summary omits individual subject IDs;
- tampered snapshot digest rejected;
- temporal and Policy validation.

## 9. Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_supply_population.py`
- `python -m uv run --locked python -m ruff check packages/livestock_application/market_supply_population.py tests/livestock_application/test_market_supply_population.py`
- `python -m uv run --locked python -m mypy packages/livestock_application/market_supply_population.py tests/livestock_application/test_market_supply_population.py`

## 10. Migrations

None.

## 11. HUMAN GATES Remaining

- Approve production population resolver data sources and authorization strategy.
- Approve persistent snapshot/digest storage, if required.
- Approve whether individual membership can ever be included in buyer-visible artifacts.
- Approve CUT F3 before buyer-facing cross-Organization aggregate visibility.
