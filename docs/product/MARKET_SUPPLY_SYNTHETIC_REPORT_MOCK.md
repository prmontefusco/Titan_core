# Market Supply Synthetic Report Mock

STATUS: SYNTHETIC VALIDATION ARTIFACT / NOT FOR PRODUCTION

Date: 2026-08-28

## Purpose

Validate whether the first Market Supply Intelligence vocabulary answers buyer and producer questions without exposing producer, property, Animal, treatment, Evidence, Dossier or individual Decision details.

This mock is generated from the same synthetic scenario represented by:

```text
python -m uv run --locked python -m apps.validacao.market_supply_synthetic
```

## Context

| Field | Value |
|---|---|
| Report type | SupplyIntelligenceReport |
| Status | SYNTHETIC_PROTOTYPE_NOT_FOR_PRODUCTION |
| Purpose | MARKET_SUPPLY_AGGREGATE_ASSESSMENT |
| Policy | SYNTHETIC_MARKET_POLICY_A |
| Policy version | v0.synthetic |
| Commercial window | 2026-09-15 to 2026-09-30 |
| Generated at | 2026-08-28T18:00:00+00:00 |
| Reference time | 2026-08-28T12:00:00+00:00 |
| Knowledge cutoff | 2026-08-28T12:00:00+00:00 |

## Buyer View

| Question | Synthetic Answer |
|---|---|
| Tenho capacidade suficiente? | Not currently. Estimated capacity is 5 against demand of 7. |
| Quanto esta ready agora? | 3 subjects are READY. |
| Quanto pode estar disponivel na janela? | 2 additional subjects are potential in window under explicit assumptions. |
| Qual o deficit? | Estimated shortage is 2. |
| Quais sao os principais gaps? | Documentation, sanitary history, territorial evidence, unknown source and withdrawal period. |
| O que nao pode ser determinado? | 1 subject is INDETERMINATE and 1 is NOT_EVALUATED in the authorized aggregate population. |

## Aggregate Counts

| Status | Count |
|---|---:|
| READY | 3 |
| CONDITIONED | 2 |
| INDETERMINATE | 1 |
| NOT_READY | 1 |
| NOT_EVALUATED | 1 |

Authorized population considered: 8.

Excluded from the synthetic population: 1, because it was not authorized for aggregate assessment.

## Gap Summary

| Gap | Count |
|---|---:|
| DOCUMENTATION_GAP | 1 |
| SANITARY_HISTORY_GAP | 1 |
| TERRITORIAL_EVIDENCE_GAP | 1 |
| UNKNOWN_SOURCE | 1 |
| WITHDRAWAL_PERIOD | 1 |

Gap categories are synthetic labels for validation only. Future production GapAnalysis must derive from canonical RuleResult, missing evidence, coverage, limitations and readiness material.

## Forecast Scenario

Forecast is included in this mock only as deterministic synthetic scenario.

Assumptions:

- no additional incompatible treatment occurs before the window;
- conditioned documentation gap can be resolved before window start.

Limitations:

- not a Decision;
- not future eligibility;
- not a guarantee of availability;
- synthetic data only.

## Producer View

| Question | Synthetic Answer |
|---|---|
| Quantos animais meus estao ready? | The mock does not expose producer-specific identity; a future producer-side F1 can answer this inside one Organization. |
| Quais estao condicionados? | Not disclosed in aggregate buyer view. |
| Quais gaps consigo resolver? | The aggregate shows high-level gap categories only; candidate detail requires a later FieldScope. |
| Que informacao seria compartilhada? | Counts, high-level gaps, capacity/shortage, timestamps, Policy/version and limitations. |
| Quem poderia ve-la? | Only a requester authorized for MARKET_SUPPLY_AGGREGATE_ASSESSMENT in a future implementation. |
| Para qual finalidade? | Aggregate market supply assessment only; no candidate disclosure, export or redistribution. |

## Explicitly Not Disclosed

- producer names;
- property identity;
- AnimalIdentifier;
- treatments;
- raw Evidence;
- Dossier;
- individual Evaluation;
- individual Decision;
- candidate membership.

## Validation Questions

- Buyer: does this answer whether capacity is sufficient without exposing identities?
- Buyer: is the distinction between READY now, potential in window and shortage clear?
- Buyer: are unknowns and limitations visible enough to avoid overclaiming?
- Producer: is this aggregate disclosure acceptable before detailed authorization?
- Producer: does the mock make clear which details remain undisclosed?
- Product: does this justify moving to producer-side single-Organization F1?
