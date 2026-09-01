# CUT F0 Execution Report - Synthetic Market Supply Prototype

Date: 2026-08-28

Status: IMPLEMENTED AS NON-PRODUCTION VALIDATION ARTIFACT

## Scope

CUT F0 was limited to a synthetic, in-memory validation prototype. It does not implement production packages, persistence, migrations, APIs, workers, real grants, cross-tenant queries, official integrations, Dossier changes or VerificationBundle changes.

## Implementation

Created `apps/validacao/market_supply_synthetic.py`, an executable validation script that builds a synthetic `SupplyIntelligenceReport`-shaped JSON document.

The script models, with synthetic data only:

- buyer-owned `CommercialDemand` context;
- `CandidatePopulationSnapshot` summary;
- aggregate `MarketReadiness` counts;
- high-level `GapAnalysis`;
- optional deterministic synthetic `SupplyForecast`;
- `SupplyDemandAnalysis`;
- buyer-visible fields;
- explicitly undisclosed fields;
- limitations and validation questions.

Created `docs/product/MARKET_SUPPLY_SYNTHETIC_REPORT_MOCK.md` as a static mock for Buyer/Producer/Product validation.

## Production Code Changed

None.

The new executable lives under `apps/validacao` and does not call production repositories, APIs, databases or external systems.

## Tests Added

Created `tests/unit/test_market_supply_synthetic.py` with checks that:

- the report is explicitly synthetic and not for production;
- aggregate counts are internally consistent;
- generated_at, reference_time, knowledge_cutoff and Policy/version are explicit;
- forecast is deterministic, limited and non-decisional.

## Verification

```text
python -m uv run --locked python -m apps.validacao.market_supply_synthetic --json-only
```

Result: generated synthetic JSON report successfully.

```text
python -m uv run --locked python -m pytest tests/unit/test_market_supply_synthetic.py tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
```

Result: 35 passed.

```text
python -m uv run --locked python -m pytest
```

Result: 1181 passed, 284 skipped.

```text
python -m uv run --locked python -m ruff check apps/validacao/market_supply_synthetic.py tests/unit/test_market_supply_synthetic.py packages/livestock_application/sanitary_test_coverage.py packages/livestock_application/market_readiness.py tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
```

Result: all checks passed.

```text
python -m uv run --locked python -m ruff format --check apps/validacao/market_supply_synthetic.py tests/unit/test_market_supply_synthetic.py packages/livestock_application/sanitary_test_coverage.py packages/livestock_application/market_readiness.py tests/livestock_application/test_sanitary_test_coverage.py tests/livestock_application/test_dimensional_coverage.py tests/livestock_application/test_market_readiness.py
```

Result: 7 files already formatted.

```text
python -m uv run --locked python -m mypy apps/validacao/market_supply_synthetic.py tests/unit/test_market_supply_synthetic.py
```

Result: success, no issues found in 2 source files.

```text
$env:TITAN_MIGRATION_DATABASE_URL="postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
python -m uv run --locked python -m alembic check
```

Result: `No new upgrade operations detected`, with the known PostGIS `geometry` warning.

Repository-wide checks still have preexisting failures outside CUT F0:

- `python -m uv run --locked python -m ruff check .` fails in BuyerPolicy realistic integration tests and one migration import block.
- `python -m uv run --locked python -m ruff format --check .` reports formatting needed in the same preexisting BuyerPolicy/migration files.
- `python -m uv run --locked python -m mypy` reports existing BuyerPolicy protocol/type errors unrelated to CUT F0.

## Security and Tenant Isolation

No real Organization, producer, property, Animal, Evidence, Dossier or Decision data is used. The prototype contains only synthetic labels and explicitly marks candidate membership as not disclosed.

## Temporal Semantics

The mock includes `generated_at`, `reference_time`, `knowledge_cutoff`, Policy/version and forecast assumptions so reviewers can validate the temporal language before production implementation.

## Remaining Gates

- Product review of the synthetic report vocabulary.
- Decision whether CUT F1 should be producer-side single-Organization analysis.
- Production SPEC before any persistence, API, cross-tenant query, grant model, aggregation privacy runtime or report persistence.
