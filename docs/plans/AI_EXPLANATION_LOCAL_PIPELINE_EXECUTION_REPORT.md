# AI Explanation Local Pipeline Execution Report

**Status:** COMPLETED
**Date:** 2026-09-04
**Scope:** application-only local/mock explanation pipeline over canonical Market Optionality output.

## Summary

This increment turns the F7 guard into a complete local application pipeline:

```text
MarketOptionAssessment
    -> MarketOptionExplanationContext
    -> MarketOptionExplanationPromptPayload
    -> deterministic local text provider
    -> Titan-built canonical draft
    -> MarketOptionExplanationGuardService
    -> released text or canonical fallback
```

The pipeline does not call Gemini or any external provider. It exists to make the future AI boundary executable in tests while production provider governance remains blocked.

On 2026-09-04, the local pipeline added an executable DataContract allow-list for Market Optionality AI Explanation. The provider-facing prompt payload is now built from approved fields only and excludes raw Organization, subject, Policy, Decision and Evaluation identifiers.

The same increment series now versions the synthetic prompt template, explanation schema and deterministic guard. The prompt payload carries `prompt_template_id`, `prompt_template_version`, `prompt_template_digest`, `guard_version`, `guard_digest` and its own canonical `payload_digest`, without storing raw prompts/outputs or calling an external provider.

The pipeline now also produces a minimized local audit envelope. The envelope carries DataContract, processing activity, provider/model labels, schema/template/guard versions and digests, prompt payload digest, source-reference digest, fallback digest, released-output digest only when the guard accepts, violation codes and limitations. It never stores raw prompt text, raw provider output text, raw source identifiers or domain objects.

The provider boundary now receives only `MarketOptionExplanationPromptPayload` and returns text. Canonical draft metadata, source references, allowed claims, reason codes, missing evidence types and limitations are assembled by Titan after provider text generation. This prevents provider implementations from receiving repositories, Domain objects, full explanation context or raw canonical identifiers through the provider interface.

The validation suite now includes `apps/validacao/ai_explanation_pipeline_smoke.py`, a non-production Gemini smoke that composes the real local pipeline with a synthetic `MarketOptionAssessment`. It sends only `MarketOptionExplanationPromptPayload.fields`, omits source-reference aliases, omits generated text from console output and validates the guard/audit envelope boundary with the local key stored outside Git.

On 2026-09-05, the local pipeline added an executable synthetic provider profile. The profile denies provider-side retention, telemetry, abuse logging, secondary use, training use and tool execution, and its canonical digest is carried by `MarketOptionExplanationRunContext` and `MarketOptionExplanationAuditEnvelope`.

On 2026-09-05, provider unavailability was made fail-closed. If the text provider raises during generation, the pipeline returns `released_text=None`, preserves the canonical structured fallback, records only `PROVIDER_UNAVAILABLE` in the minimized audit envelope and does not retain provider exception text or diagnostics.

On 2026-09-05, the canonical fallback became a typed immutable value object. `MarketOptionCanonicalExplanation` preserves state, reversibility, Policy/version, `reference_time`, `knowledge_cutoff` and result boundary while exposing an explicit `as_mapping()` projection for canonical audit digests.

On 2026-09-05, derived classification propagation became executable in the local/mock pipeline. The canonical fallback and provider-facing payload now carry `PROTECTED_DERIVED_CANONICAL_EXPLANATION` plus disclosure restrictions stating that derived knowledge inherits source restrictions, generation never declassifies information and the result cannot be reused for export inference or redistribution.

On 2026-09-05, the accepted ADR-0075 ProviderProfile lifecycle became executable in the local/mock pipeline. `MarketOptionExplanationProviderProfile` now carries lifecycle state plus optional effective interval, includes those fields in its canonical digest and is checked before provider invocation and before release. Suspended, revoked, superseded, draft or expired profiles produce `PROVIDER_PROFILE_UNAVAILABLE`, do not call the text provider and return canonical fallback.

On 2026-09-05, provider-safe vocabulary projection became executable. The provider-facing payload no longer exposes canonical `reason_codes`, `missing_evidence_types`, `limitations` or `context_limitations`; it exposes only stable local aliases (`reason_aliases`, `missing_evidence_aliases`, `limitation_aliases`, `context_limitation_aliases`). Canonical codes remain inside Titan for guard/audit composition.

On 2026-09-05, the accepted ADR-0075 structured draft boundary became executable in the local/mock pipeline. `MarketOptionExplanationDraft` now carries a versioned schema plus structured sections, each tied to provider-visible `claim_ref` values generated by Titan from the allowed claim list. The provider-facing payload exposes those `claim_ref` aliases, and the guard rejects drafts that reference unknown claims.

On 2026-09-06, external-provider processing authorization became an executable application-only gate. `MarketOptionExplanationProviderProcessingAuthorization` separates permission to access canonical Titan outputs from permission to send minimized derived content to an AI provider. The pipeline now requires Organization, purpose, ProviderProfile, DataContract, classification ceiling and effective-period compatibility before provider invocation, records only a minimized authorization reference/digest in the audit envelope and returns canonical fallback with `PROVIDER_PROCESSING_UNAUTHORIZED` when the authorization is incompatible.

## Files Changed

- `packages/livestock_application/market_optionality.py`
- `tests/livestock_application/test_market_optionality.py`
- `tests/unit/test_ai_explanation_pipeline_smoke.py`
- `apps/validacao/ai_explanation_pipeline_smoke.py`
- `docs/specs/proposed/2026-09-04-ai-explanation-governance.md`
- `docs/plans/AI_EXPLANATION_GOVERNANCE_DESIGN_PACKAGE.md`
- `docs/plans/AI_EXPLANATION_LOCAL_PIPELINE_EXECUTION_REPORT.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Code Changed

Added:

- `MarketOptionExplanationRunContext`;
- `MarketOptionExplanationResult`;
- `MarketOptionExplanationTextProvider`;
- `DeterministicMarketOptionExplanationTextProvider`;
- `MarketOptionExplanationPipelineService`;
- `MarketOptionExplanationClaimType`;
- `MarketOptionExplanationClaim`;
- `MarketOptionExplanationDataContractService`;
- `MarketOptionExplanationPromptPayload`;
- `MarketOptionExplanationPromptTemplate`;
- `MarketOptionExplanationProviderProfile`;
- `MarketOptionExplanationProviderProfileState`;
- `MarketOptionExplanationProviderProcessingAuthorization`;
- `MarketOptionExplanationDraftSection`;
- `MarketOptionCanonicalExplanation`;
- `MarketOptionExplanationAuditEnvelope`;
- `MarketOptionExplanationAuditEnvelopeService`;
- `apps/validacao/ai_explanation_pipeline_smoke.py`.

The service requires synthetic governance references (`data_contract_id`, version, processing activity, provider profile and model name), prepares canonical context, builds a minimized prompt payload, requests text from a supplied provider, wraps that text in Titan-built canonical draft metadata, validates it with the deterministic guard and releases text only when validation passes.

When validation fails, `released_text` is `None` and callers retain a canonical fallback containing only structured Market Optionality state, reversibility, Policy/version and temporal coordinates.

After ADR-0074 was accepted with changes, the pipeline was hardened with structured allowed claims. `MarketOptionExplanationContext` now carries claims originated by Titan before draft generation, and the guard rejects provider-originated claims that are not present in that allow-list.

The DataContract step runs before provider text generation and fails closed for unapproved contract id/version. It preserves audience, subject type, market purpose, Policy version, `reference_time`, `knowledge_cutoff`, option state, reversibility, allowed claims and limitations, while keeping raw canonical identifiers out of provider-visible fields. Canonical source references remain internally available through aliases for guard/audit composition.

Prompt template, schema and guard identities are represented as deterministic local metadata. Their digests are computed through Titan's canonical serializer, so a template or guard-version change becomes visible in the payload identity used by the pipeline.

The audit envelope is generated after guard validation and before returning the result. Accepted explanations receive a released-output digest; rejected drafts preserve violation codes and keep released-output digest absent.

Provider runtime failure is handled as a non-release outcome. The pipeline does not expose provider exception text, retry metadata or diagnostics; it records the stable violation code `PROVIDER_UNAVAILABLE` and returns the same canonical fallback shape used for guard rejection.

The fallback is now represented by `MarketOptionCanonicalExplanation` instead of an arbitrary mapping. The value object remains deterministic and digestable through `as_mapping()`, but callers can rely on typed fields for temporal coordinates, Policy reference and result boundary.

The fallback and minimized prompt payload also include output classification and disclosure restrictions. This makes classification inheritance machine-visible in the application pipeline without introducing production DataClassification persistence, provider governance or user-visible API behavior.

ProviderProfile lifecycle state and effective interval are now part of the executable provider boundary. The pipeline validates profile availability before provider invocation and rechecks it before releasing accepted text, preserving ADR-0075 without adding persistence, provider adapter or external behavior.

Provider-safe aliases now replace internal vocabulary in the provider payload. This preserves the canonical vocabulary internally while reducing semantic leakage to provider adapters.

## Invariants Preserved

- No external AI provider is called by production/application code.
- No prompt or output is persisted.
- No API, UI, worker or migration was introduced.
- No Fact, Evidence, Rule, Policy, Evaluation, Decision, Dossier, VerificationBundle, forecast or option state is created by AI.
- Provider draft output cannot be released without passing the deterministic guard.
- AI/provider draft output cannot originate externally presented explanation claims.
- Provider-facing prompt payloads are built from an executable allow-list and exclude raw canonical identifiers.
- Prompt template, schema and guard versions/digests are preserved before provider text generation.
- Provider profile version/digest and no-retention/no-telemetry/no-secondary-use constraints are validated before release.
- ProviderProfile lifecycle state and effective interval are validated before provider invocation and release.
- Provider-facing payloads expose provider-safe aliases rather than canonical internal reason/evidence/limitation codes.
- Provider implementations receive only the minimized prompt payload and return text.
- Explicitly authoritative or forecast-like provider text is rejected before release.
- Provider unavailability cannot block canonical explanation fallback or leak provider diagnostics through the audit envelope.
- Canonical fallback is typed, immutable and keeps `reference_time`/`knowledge_cutoff` explicit.
- AI explanation fallback and provider payload preserve derived classification and disclosure restrictions.
- Audit material is minimized to digests, codes and governance references; raw prompt/output text is not retained.
- Later provider behavior cannot rewrite historical canonical records.
- No cross-tenant context or disclosure semantics were introduced.

## Tests Added

`tests/livestock_application/test_market_optionality.py` now covers:

- guarded local deterministic summary release;
- fallback with no released text when a provider invents material;
- rejection of provider-originated structured claims outside the Titan allow-list;
- provider-facing prompt payload minimization without raw Organization/subject/Policy/Decision/Evaluation ids;
- fail-closed behavior for unapproved AI Explanation DataContract id/version;
- prompt template and guard digest mismatch rejection;
- provider profile rejection for unapproved retention, telemetry, secondary use or digest mismatch;
- ProviderProfile lifecycle/effective-period digesting and fail-closed non-call behavior;
- provider-safe alias projection for reason, missing-evidence, limitation and context-limitation vocabulary;
- prompt payload digest changes when prompt template version changes;
- minimized audit envelope without raw prompt/output/source identifiers;
- released-output digest required only for accepted explanations;
- provider interface constrained to prompt payload only;
- fallback when provider text contains prohibited authority/forecast terms;
- fallback when the provider is unavailable, without retaining provider exception diagnostics;
- typed canonical fallback with stable mapping projection for audit digesting;
- derived output classification and disclosure restrictions in fallback and minimized payload;
- synthetic Gemini pipeline smoke over minimized prompt payload;
- mandatory governance references in the run context.

## Tests Executed

- `python -m uv run --locked python -m pytest tests/livestock_application/test_market_optionality.py tests/unit/test_ai_explanation_pipeline_smoke.py -q` - 41 passed.
- `python -m uv run --locked ruff check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked ruff format --check packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked python -m mypy packages/livestock_application/market_optionality.py tests/livestock_application/test_market_optionality.py` - passed.
- `python -m uv run --locked python -m pytest -q` with PostgreSQL integration required - 1665 passed, 4 warnings.
- `python -m uv run --locked ruff check .` - passed.
- `python -m uv run --locked ruff format --check .` - passed.
- `python -m uv run --locked python -m mypy` - passed.
- `python -m uv run --locked python -m alembic check` - passed, no new upgrade operations detected.

## Migrations

None.

## Security Impact

Positive. The future provider boundary now has an executable local pipeline that fails closed before releasing generated text.

## Tenant Isolation Impact

No infrastructure access was introduced. The pipeline works only over a supplied canonical `MarketOptionAssessment`.

## Temporal Semantics Impact

Positive. The canonical fallback and explanation context preserve `reference_time` and `knowledge_cutoff`.

## Human Decisions Required

No additional decision is required for this local/mock pipeline. Production provider integration, persisted DataContract governance, prompt/output retention, user-visible AI output and provider/model selection remain outside this build.
