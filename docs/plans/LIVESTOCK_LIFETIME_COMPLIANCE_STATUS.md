# LIVESTOCK_LIFETIME_COMPLIANCE_STATUS

Status log type: APPEND_ONLY
Version: 1.1
Date created: 2026-08-04
Rule: entries below are append-only; corrections require a new entry and must not rewrite previous entries.

## Entry 0001

- date: 2026-08-04
- entry_type: INITIALIZATION
- plan_version: 1
- summary:
  - Created initial status registry for the lifetime compliance plan.
  - No implementation authorized.
  - No stage approved.
- checklist_location:
  - found_at: `docs/CHECKLIST_DE_IMPLEMENTACAO.md`
  - root_path_present: `false`
  - blocking_result: `NO_ABSENCE_BLOCK; DOCUMENTARY_PATH_DIVERGENCE_RECORDED`
- stages:
  - `LIV-C01`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C02`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C03`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C04`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C05`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C06`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C07`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C08`: `AGUARDANDO_AUTORIZACAO`
- pending_decisions:
  - Minimum shape for lifetime sanitary coverage
  - Minimum path for acquisition/continuity behavior
  - Correct ownership of market-governed withdrawal semantics
  - Expanded sanitary dossier scope before PDF presentation
- next_action_allowed:
  - Wait for explicit approval or `PLAN_CHANGE_REQUEST`

## Entry 0002

- date: 2026-08-04
- entry_type: DOCUMENTARY_REVIEW
- plan_version: 1.1
- summary:
  - Applied documentary corrections to the proposed plan before approval.
  - Refined `LIV-C07` to make offline verification dimensional, possibly partial, and evidenced by a structured `ValidationReport`/`VerificationReport`.
  - Refined `LIV-C08` to include outbound contract, technical idempotent acknowledgement, delivery state, retry, and reconciliation without ERP authority over the original sanitary fact.
  - Uniformized planning prose toward Portuguese while preserving code/class concepts in English.
- checklist_location:
  - found_at: `docs/CHECKLIST_DE_IMPLEMENTACAO.md`
  - root_path_present: `false`
  - blocking_result: `NO_ABSENCE_BLOCK; DOCUMENTARY_PATH_DIVERGENCE_RECORDED`
- stages:
  - `LIV-C01`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C02`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C03`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C04`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C05`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C06`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C07`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C08`: `AGUARDANDO_AUTORIZACAO`
- pending_decisions:
  - Minimum shape for lifetime sanitary coverage
  - Minimum path for acquisition/continuity behavior
  - Correct ownership of market-governed withdrawal semantics
  - Expanded sanitary dossier scope before PDF presentation
- next_action_allowed:
  - Wait for explicit approval or `PLAN_CHANGE_REQUEST`

## Entry 0003

- date: 2026-08-04
- entry_type: HUMAN_APPROVAL
- plan_version: 1.1
- summary:
  - Human approval recorded for `LIVESTOCK_LIFETIME_COMPLIANCE_PLAN.md` version `1.1`.
  - Exclusively `LIV-C01` is authorized in this approval.
  - `LIV-C02` through `LIV-C08` remain pending explicit authorization.
  - No later stage may be released automatically from this approval.
- checklist_location:
  - found_at: `docs/CHECKLIST_DE_IMPLEMENTACAO.md`
  - root_path_present: `false`
  - blocking_result: `NO_ABSENCE_BLOCK; DOCUMENTARY_PATH_DIVERGENCE_RECORDED`
- stages:
  - `LIV-C01`: `AUTORIZADA`
  - `LIV-C02`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C03`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C04`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C05`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C06`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C07`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C08`: `AGUARDANDO_AUTORIZACAO`
- approval_constraints:
  - `LIV-C01` authorization does not authorize implementation of any later stage.
  - No stage after `LIV-C01` may be auto-approved or auto-released.
  - New human approval is required before any later stage changes status.
- next_action_allowed:
  - Execute only `LIV-C01` in a future run if explicitly requested.
  - Wait for explicit human approval before releasing any later stage.

## Entry 0004

- date: 2026-08-04
- entry_type: STAGE_COMPLETION
- plan_version: 1.1
- stage: `LIV-C01`
- summary:
  - Executed only the authorized `LIV-C01`.
  - Consolidated documentary baseline in `docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md`.
  - Reconfirmed checklist location, path divergence, and the distinction between permanent authority documents and auxiliary implementation documents.
  - No code, migration, ADR, `DOMAIN.md`, or `ARCHITECTURE.md` changes were made.
- checklist_location:
  - found_at: `docs/CHECKLIST_DE_IMPLEMENTACAO.md`
  - root_path_present: `false`
  - blocking_result: `NO_ABSENCE_BLOCK; DOCUMENTARY_PATH_DIVERGENCE_RECORDED`
- stage_result:
  - `LIV-C01`: `CONCLUIDA`
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C03`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C04`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C05`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C06`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C07`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C08`: `AGUARDANDO_AUTORIZACAO`
- completion_evidence:
  - baseline_artifact: `docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md`
  - authority_documents_reread: `AGENTS.md`, `VISION.md`, `DOMAIN.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`
  - reference_search_reconfirmed: `CHECKLIST_DE_IMPLEMENTACAO.md`, `PLANO_DE_IMPLEMENTACAO_VALIDADO.md`, `CORTE_MVP_BACKEND.md`, `PLANO_DE_CONCLUSAO_DO_DOMINIO.md`
- next_action_allowed:
  - Wait for explicit human approval before authorizing `LIV-C02`.
  - No later stage may be released automatically from the completion of `LIV-C01`.

## Entry 0005

- date: 2026-08-04
- entry_type: DOCUMENTARY_MATURITY_REVIEW
- plan_version: 1.1
- stage: `LIV-C01`
- summary:
  - Standardized the documentary structure for future `LIV-Cxx` artifacts by creating `docs/plans/LIVESTOCK_STAGE_PACKAGE_TEMPLATE.md`.
  - Refined `docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md` to include `Artifact ID`, `Derived from`, `Critério de encerramento`, `Dependências liberadas`, and `Não conformidades`.
  - Preserved the authority boundaries of the `LIV-C01` artifact without authorizing any later stage.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C03`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C04`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C05`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C06`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C07`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C08`: `AGUARDANDO_AUTORIZACAO`
- documentary_outputs:
  - template: `docs/plans/LIVESTOCK_STAGE_PACKAGE_TEMPLATE.md`
  - refined_artifact: `docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C01_BASELINE.md`
- next_action_allowed:
  - Wait for explicit human approval before authorizing `LIV-C02`.
  - No later stage may be released automatically from this documentary refinement.

## Entry 0006

- date: 2026-08-04
- entry_type: HUMAN_APPROVAL
- plan_version: 1.1
- stage: `LIV-C02`
- summary:
  - Human approval recorded for execution of `LIV-C02`.
  - `LIV-C02` is now authorized.
  - `LIV-C03` through `LIV-C08` remain pending explicit human authorization.
  - No later stage may be released automatically from this approval.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `AUTORIZADA`
  - `LIV-C03`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C04`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C05`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C06`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C07`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C08`: `AGUARDANDO_AUTORIZACAO`
- approval_constraints:
  - `LIV-C02` authorization does not authorize implementation of any later stage.
  - No stage after `LIV-C02` may be auto-approved or auto-released.
  - New human approval is required before any later stage changes status.
- next_action_allowed:
  - Execute only `LIV-C02` in a future run if explicitly requested.
  - Wait for explicit human approval before releasing any later stage.

## Entry 0007

- date: 2026-08-04
- entry_type: DOCUMENTARY_REFINEMENT
- plan_version: 1.2
- summary:
  - Refined the implementation plan structurally without changing its approved scope.
  - Added global `Architectural Principles`.
  - Added a global rule forbidding new `Aggregate`, `Entity`, `Value Object` or `Service` without prior proof that existing concepts are insufficient.
  - Added `Decision rule` and `Architectural Question` blocks to modeling-heavy stages.
  - Added the explicit invariant in `LIV-C08` that no administrative ERP operation automatically generates `Evidence`, `Fact`, `Evaluation` or `Decision`.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `AUTORIZADA`
  - `LIV-C03`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C04`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C05`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C06`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C07`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C08`: `AGUARDANDO_AUTORIZACAO`
- next_action_allowed:
  - Execute only `LIV-C02` if explicitly requested.
  - Wait for explicit human approval before releasing any later stage.

## Entry 0008

- date: 2026-08-04
- entry_type: DESIGN_PACKAGE
- plan_version: 1.2
- stage: `LIV-C02`
- summary:
  - Created the `Design Package` for `LIV-C02`.
  - Answered the stage `Architectural Question` in favor of reuse of existing concepts without introducing a new `Aggregate`.
  - Recorded the minimum recommended design as derivation and composition over existing coverage/gap concepts.
  - No code, migration, ADR, `DOMAIN.md`, or `ARCHITECTURE.md` changes were made.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `AUTORIZADA`
  - `LIV-C03`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C04`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C05`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C06`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C07`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C08`: `AGUARDANDO_AUTORIZACAO`
- documentary_outputs:
  - design_package: `docs/plans/LIVESTOCK_LIFETIME_COMPLIANCE_C02_DESIGN_PACKAGE.md`
- next_action_allowed:
  - Implement `LIV-C02` if explicitly requested.
  - Wait for explicit human approval before releasing any later stage.

## Entry 0009

- date: 2026-08-04
- entry_type: STAGE_COMPLETION
- plan_version: 1.2
- stage: `LIV-C02`
- summary:
  - Implemented `LIV-C02` according to the approved `Design Package`, without introducing a new `Aggregate`.
  - Coverage now travels as derived fact `livestock.history_coverage` when a received transfer artifact exists.
  - Dossier now declares coverage honestly as `NAO_DECLARADA`, `DECLARED`, or `PARTIAL_DECLARED`, including explicit gaps when present.
  - PostgreSQL/RLS and API E2E evidence were executed successfully after configuring `TITAN_DATABASE_URL`.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `CONCLUIDA`
  - `LIV-C03`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C04`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C05`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C06`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C07`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C08`: `AGUARDANDO_AUTORIZACAO`
- completion_evidence:
  - unit_tests:
    - `python -m uv run --locked pytest tests/livestock_application/test_fact_provider_sanitary.py tests/livestock_application/test_dossier_template.py`
  - postgresql_tests:
    - `python -m uv run --locked pytest tests/integration/test_transfer_artifact_postgresql.py`
  - e2e_tests:
    - `python -m uv run --locked pytest tests/integration/test_livestock_api_saida.py -k cobertura_recebida`
  - quality_checks:
    - `python -m uv run --locked ruff check packages/livestock_application/fact_provider.py packages/livestock_application/dossier_template.py tests/livestock_application/test_fact_provider_sanitary.py tests/livestock_application/test_dossier_template.py`
    - `python -m uv run --locked ruff check apps/api/livestock_queries.py tests/integration/test_transfer_artifact_postgresql.py tests/integration/test_livestock_api_saida.py`
- scope_notes:
  - No new migration was required for this stage.
  - No new `Aggregate`, `Entity`, `Value Object`, or transversal concept was introduced.
  - Existing `mypy` findings outside the immediate stage scope remain unresolved.
- next_action_allowed:
  - Wait for explicit human approval before authorizing `LIV-C03`.
  - No later stage may be released automatically from the completion of `LIV-C02`.

## Entry 0010

- date: 2026-08-04
- entry_type: HUMAN_APPROVAL
- plan_version: 1.2
- stage: `LIV-C03`
- summary:
  - Human approval recorded for execution of `LIV-C03`.
  - `LIV-C03` is now authorized.
  - `LIV-C04` through `LIV-C08` remain pending explicit human authorization.
  - No later stage may be released automatically from this approval.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `CONCLUIDA`
  - `LIV-C03`: `AUTORIZADA`
  - `LIV-C04`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C05`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C06`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C07`: `AGUARDANDO_AUTORIZACAO`
  - `LIV-C08`: `AGUARDANDO_AUTORIZACAO`
- approval_constraints:
  - `LIV-C03` authorization does not authorize implementation of any later stage.
  - No stage after `LIV-C03` may be auto-approved or auto-released.
  - New human approval is required before any later stage changes status.
- next_action_allowed:
  - Execute only `LIV-C03` in a future run if explicitly requested.
  - Wait for explicit human approval before releasing any later stage.

## Entry 0011

- date: 2026-08-04
- entry_type: HUMAN_APPROVAL
- plan_version: 1.2
- summary:
  - Human approval recorded for all remaining implementation stages.
  - `LIV-C03` through `LIV-C08` are now authorized by explicit user instruction.
  - No later stage may be released automatically from the execution or completion of any earlier stage.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `CONCLUIDA`
  - `LIV-C03`: `AUTORIZADA`
  - `LIV-C04`: `AUTORIZADA`
  - `LIV-C05`: `AUTORIZADA`
  - `LIV-C06`: `AUTORIZADA`
  - `LIV-C07`: `AUTORIZADA`
  - `LIV-C08`: `AUTORIZADA`
- approval_constraints:
  - Authorization of all remaining stages does not auto-complete any stage.
  - Execution of one stage does not auto-release the next stage.
  - Stage completion still requires explicit append-only status evidence.
- next_action_allowed:
  - Execute `LIV-C03` as the next implementation step.
  - Preserve append-only control for every later stage transition.

## Entry 0012

- date: 2026-08-04
- entry_type: STAGE_COMPLETION
- plan_version: 1.2
- stage: `LIV-C03`
- summary:
  - Implemented `LIV-C03` as an Application orchestration over existing concepts, without introducing a new `Aggregate`.
  - Added a composed documentary acquisition path that registers `ReceivedTransferArtifact` and any imported facts in one explicit use case.
  - Preserved the ADR-0042 invariants that imported facts retain external provenance and that missing prior history remains an explicit coverage gap.
  - No migration was required for this stage.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `CONCLUIDA`
  - `LIV-C03`: `CONCLUIDA`
  - `LIV-C04`: `AUTORIZADA`
  - `LIV-C05`: `AUTORIZADA`
  - `LIV-C06`: `AUTORIZADA`
  - `LIV-C07`: `AUTORIZADA`
  - `LIV-C08`: `AUTORIZADA`
- completion_evidence:
  - unit_tests:
    - `python -m uv run --locked pytest tests/livestock_application/test_acquisition_continuity_service.py tests/livestock_application/test_transfer_artifact_service.py tests/livestock_application/test_imported_fact_service.py`
  - api_surface_tests:
    - `python -m uv run --locked pytest tests/api/test_core_public_surface.py`
  - e2e_tests:
    - `python -m uv run --locked pytest tests/integration/test_livestock_api_saida.py -k documental`
  - quality_checks:
    - `python -m uv run --locked ruff check packages/livestock_application/acquisition_continuity_service.py apps/api/livestock_writes.py tests/livestock_application/test_acquisition_continuity_service.py tests/integration/test_livestock_api_saida.py tests/api/test_core_public_surface.py`
- scope_notes:
  - The implementation chose the minimum path recommended by the plan: Application orchestration over `Animal`, `ExternalCounterparty`, `ReceivedTransferArtifact`, and `ImportedLivestockFact`.
  - No new `Aggregate`, `Entity`, `Value Object`, transversal concept, or schema change was introduced.
  - Later authorized stages remain unauthorized for automatic release despite the broad approval entry.
- next_action_allowed:
  - Start `LIV-C04` only by explicit execution choice.
  - No later stage may be auto-completed or auto-released from the completion of `LIV-C03`.

## Entry 0013

- date: 2026-08-04
- entry_type: STAGE_COMPLETION
- plan_version: 1.2
- stage: `LIV-C04`
- summary:
  - Implemented `LIV-C04` by making imported sanitary facts enter the `FactSnapshot` with provenance and confidence preserved as separate dimensions.
  - Imported facts now travel into snapshot with explicit `origin`, `asserted_by`, `confidence_tier`, `source_artifact_id`, and `source_reference`, without becoming local observation.
  - Preserved the existing pharmacological eligibility behavior that already consumed imported withdrawal contributions.
  - No migration was required for this stage.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `CONCLUIDA`
  - `LIV-C03`: `CONCLUIDA`
  - `LIV-C04`: `CONCLUIDA`
  - `LIV-C05`: `AUTORIZADA`
  - `LIV-C06`: `AUTORIZADA`
  - `LIV-C07`: `AUTORIZADA`
  - `LIV-C08`: `AUTORIZADA`
- completion_evidence:
  - unit_tests:
    - `python -m uv run --locked pytest tests/livestock_application/test_fact_provider_sanitary.py -k "importado or cobertura"`
    - `python -m uv run --locked pytest tests/livestock_application/test_eligibility_service.py -k imported_treatment_fact_blocks_eligibility_with_provenance`
  - quality_checks:
    - `python -m uv run --locked ruff check packages/livestock_application/fact_provider.py tests/livestock_application/test_fact_provider_sanitary.py`
    - `python -m uv run --locked ruff format --check packages/livestock_application/fact_provider.py tests/livestock_application/test_fact_provider_sanitary.py`
- scope_notes:
  - The implementation extended the existing snapshot path instead of introducing any new aggregate, entity, schema, or policy concept.
  - Imported evidence remains imported assertion; it is not promoted to local fact ownership.
  - Later authorized stages remain blocked from automatic release despite their approved status.
- next_action_allowed:
  - Start `LIV-C05` only by explicit execution choice.
  - No later stage may be auto-completed or auto-released from the completion of `LIV-C04`.

## Entry 0014

- date: 2026-08-04
- entry_type: STAGE_COMPLETION
- plan_version: 1.2
- stage: `LIV-C05`
- summary:
  - Implemented `LIV-C05` by making the market withdrawal basis explicit in the vertical configuration and using it to recompute `livestock.withdrawal` during market-specific evaluation.
  - The solution did not introduce a new table or persistent concept; it kept the minimum approved path by combining existing withdrawal contributions with governed market configuration.
  - Market evaluation no longer silently reuses the local technical medication period when a governed market basis is declared.
  - Market profile responses now expose the declared withdrawal basis explicitly for auditability.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `CONCLUIDA`
  - `LIV-C03`: `CONCLUIDA`
  - `LIV-C04`: `CONCLUIDA`
  - `LIV-C05`: `CONCLUIDA`
  - `LIV-C06`: `AUTORIZADA`
  - `LIV-C07`: `AUTORIZADA`
  - `LIV-C08`: `AUTORIZADA`
- completion_evidence:
  - unit_tests:
    - `python -m uv run --locked pytest tests/livestock_application/test_market_eligibility.py -k "withdrawal_basis or declared_withdrawal or adopted_market"`
  - integration_tests:
    - `python -m uv run --locked pytest tests/integration/test_livestock_api_leitura.py -k perfis_de_mercado`
  - quality_checks:
    - `python -m uv run --locked ruff check packages/livestock_application/market_eligibility.py tests/livestock_application/test_market_eligibility.py apps/api/livestock_queries.py tests/integration/test_livestock_api_leitura.py`
    - `python -m uv run --locked ruff format --check packages/livestock_application/market_eligibility.py tests/livestock_application/test_market_eligibility.py apps/api/livestock_queries.py tests/integration/test_livestock_api_leitura.py`
- scope_notes:
  - The chosen shape is an explicit combination of existing withdrawal contributions plus governed vertical configuration.
  - `Medication`, `Rule`, `NormativeBasis`, and configuration remain distinct concerns; this stage did not collapse them into a single persistence model.
  - No migration or schema decision was introduced in advance of further normative modeling.
- next_action_allowed:
  - Start `LIV-C06` only by explicit execution choice.
  - No later stage may be auto-completed or auto-released from the completion of `LIV-C05`.

## Entry 0015

- date: 2026-08-04
- entry_type: DESIGN_PACKAGE
- plan_version: 1.2
- requested_stage: `LIV-C06`
- referenced_plan_stage: `LIV-C05`
- summary:
  - Created [LIV-C05_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C05_DESIGN_PACKAGE.md) for the withdrawal-by-policy stage requested in this execution.
  - Confirmed that `LIV-C06` remains `AUTORIZADA` in the status log, while the approved plan still numbers the same semantic stage as `LIV-C05`.
  - Recorded the current architectural gate: the repository still lacks an approved implementation contract that carries market withdrawal requirement, classification, and normative grounding through `Evaluation` and `Dossier` without overloading `MarketProfile`.
  - No implementation started in this execution.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `CONCLUIDA`
  - `LIV-C03`: `CONCLUIDA`
  - `LIV-C04`: `CONCLUIDA`
  - `LIV-C05`: `CONCLUIDA`
  - `LIV-C06`: `AUTORIZADA`
  - `LIV-C07`: `AUTORIZADA`
  - `LIV-C08`: `AUTORIZADA`
- documentary_outputs:
  - design_package: `docs/plans/LIV-C05_DESIGN_PACKAGE.md`
- blocking_notes:
  - Stage numbering diverges between the current request (`LIV-C06`) and plan v1.2 (`LIV-C05`) for the same withdrawal-by-policy semantics.
  - Current code still relies on `MarketProfile.withdrawal_basis` as concrete vertical configuration for foreign-market withdrawal timing.
  - `Prescription` does not currently model a prescription-specific withdrawal requirement.
  - No later stage may be released automatically from this design-package entry.
- next_action_allowed:
  - Wait for explicit human decision on whether the implementation must remove/block concrete vertical withdrawal periods until policy-grounded basis is approved, or proceed with a narrower compliant change.
  - Keep any subsequent stage append-only and non-automatic.

## Entry 0016

- date: 2026-08-04
- entry_type: STAGE_COMPLETION
- plan_version: 1.2
- requested_stage: `LIV-C06`
- referenced_plan_stage: `LIV-C05`
- summary:
  - Implemented the minimum approved path for withdrawal-by-policy without introducing any new aggregate, entity, enum, table, or migration.
  - Foreign-market default profiles no longer declare a concrete withdrawal period silently; when no governed market basis exists, market evaluation now fails closed with explicit gap `CARENCIA_POR_MERCADO_AUSENTE`.
  - Market-oriented evaluation no longer reuses a dependent-subject persisted evaluation as if it were the primary animal evaluation; when needed, the animal evaluation is recomputed for the dossier and decision path.
  - The implementation preserves historical reproducibility by leaving persisted legacy decisions untouched and by restricting the new behavior to future market-oriented evaluations.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `CONCLUIDA`
  - `LIV-C03`: `CONCLUIDA`
  - `LIV-C04`: `CONCLUIDA`
  - `LIV-C05`: `CONCLUIDA`
  - `LIV-C06`: `AUTORIZADA`
  - `LIV-C07`: `AUTORIZADA`
  - `LIV-C08`: `AUTORIZADA`
- completion_evidence:
  - design_package:
    - `docs/plans/LIV-C05_DESIGN_PACKAGE.md`
  - unit_tests:
    - `python -m uv run --locked pytest tests/livestock_application/test_market_eligibility.py`
  - integration_tests:
    - `python -m uv run --locked pytest tests/integration/test_livestock_api_leitura.py -k "perfis_de_mercado or mercado"` (executed in this environment; all selected tests were skipped)
  - quality_checks:
    - `python -m uv run --locked ruff check apps/api/livestock_queries.py packages/livestock_application/market_eligibility.py tests/livestock_application/test_market_eligibility.py tests/integration/test_livestock_api_leitura.py`
    - `python -m uv run --locked ruff format --check tests/integration/test_livestock_api_leitura.py`
- scope_notes:
  - `Medication.withdrawal_period_days` is no longer promoted as universal regulatory truth for the foreign-market defaults touched by this stage.
  - The stage still does not implement prescription-specific withdrawal requirements or a policy-grounded normative persistence model for market withdrawal.
  - No later stage may be auto-completed or auto-released from this completion entry.
- residual_risks:
  - The repository still lacks a first-class policy contract that carries normative basis, source classification, and composition strategy for withdrawal requirements across markets.
  - Integration coverage for the affected API flows remains unconfirmed in this local execution because the selected integration tests were skipped in the current environment.
- next_action_allowed:
  - Keep `LIV-C06` as `AUTORIZADA` only; do not auto-start or auto-complete it from this entry.
  - Any subsequent normative modeling or policy generalization requires its own explicit execution step.

## Entry 0017

- date: 2026-08-04
- entry_type: DESIGN_PACKAGE
- plan_version: 1.2
- stage: `LIV-C06`
- summary:
  - Created [LIV-C06_DESIGN_PACKAGE.md](/C:/programing/Titan/docs/plans/LIV-C06_DESIGN_PACKAGE.md) for the authorized decision-emission stage.
  - Confirmed that the repository already contains the central governance model, persistence, Dossier support, unit coverage, PostgreSQL roundtrip coverage, and the API gate that opens a `DecisionProposal` when automatic emission is refused.
  - Recorded the residual gap as a production caller problem: the repository still lacks a fully validated official API path that closes proposal -> review -> human decision -> dossier end to end.
  - No later stage was authorized or released by this entry.
- stages:
  - `LIV-C01`: `CONCLUIDA`
  - `LIV-C02`: `CONCLUIDA`
  - `LIV-C03`: `CONCLUIDA`
  - `LIV-C04`: `CONCLUIDA`
  - `LIV-C05`: `CONCLUIDA`
  - `LIV-C06`: `AUTORIZADA`
  - `LIV-C07`: `AUTORIZADA`
  - `LIV-C08`: `AUTORIZADA`
- documentary_outputs:
  - design_package: `docs/plans/LIV-C06_DESIGN_PACKAGE.md`
- blocking_notes:
  - The repository still lacks an approved production rule for resolving human decision authority from the real `OrganizationContext`.
  - Any implementation would need an explicit decision about which permission authorizes human review/emission, how `DecisionAuthorityProfile` is derived in production, and whether the same actor may review and emit in the minimum path.
  - The remaining work must stay limited to the official caller flow and must not introduce a new aggregate, new central concept, or authority chosen by the client.
  - No later stage may be released automatically from this design-package entry.
- next_action_allowed:
  - Wait for explicit human decision on authority/permissive resolution for human decision emission before implementing `LIV-C06`.
  - Keep `LIV-C07` and later stages blocked from automatic release.
