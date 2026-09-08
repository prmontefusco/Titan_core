"""Roteiro local de fumaça para AI Explanation via payload minimizado.

Este roteiro não integra IA ao Titan produtivo. Ele compõe o pipeline local de
AI Explanation sobre um `MarketOptionAssessment` sintético, envia somente o
`MarketOptionExplanationPromptPayload` minimizado para a Gemini API e valida que
o guard/fallback continuam sendo a fronteira de release.

Uso:
python -m uv run --locked python -m apps.validacao.ai_explanation_pipeline_smoke
python -m uv run --locked python -m apps.validacao.ai_explanation_pipeline_smoke --pausar
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from apps.validacao.ai_provider_smoke import (
    MODELS_URL,
    PREFERRED_GENERATE_MODELS,
    _load_api_key,
    _request,
    _select_generate_model,
)
from apps.validacao.runner import CINZA, FIM, NEGRITO, VERDE, VERMELHO
from packages.livestock_application.market_optionality import (
    MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
    MarketOptionAssessment,
    MarketOptionContext,
    MarketOptionExplanationPipelineService,
    MarketOptionExplanationPromptPayload,
    MarketOptionExplanationRunContext,
    MarketOptionReversibility,
    MarketOptionState,
)
from packages.livestock_infrastructure.ai_explanation_provider import (
    AIExplanationProviderUnavailable,
    GeminiMarketOptionExplanationTextProvider,
    assert_gemini_market_option_explanation_payload_minimized,
    build_gemini_market_option_explanation_body,
)
from packages.shared_kernel import OrganizationId, TypedId

SYNTHETIC_NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def _synthetic_assessment() -> MarketOptionAssessment:
    context = MarketOptionContext(
        organization_id=OrganizationId.new(),
        subject_id=TypedId.new("animal"),
        market_purpose="synthetic-ai-explanation-validation",
        policy_id=TypedId.new("policy"),
        policy_version=1,
        reference_time=SYNTHETIC_NOW,
        knowledge_cutoff=SYNTHETIC_NOW,
    )
    return MarketOptionAssessment(
        context=context,
        state=MarketOptionState.OPTION_OPEN,
        reversibility=MarketOptionReversibility.NOT_APPLICABLE,
        decision_id=TypedId.new("decision"),
        evaluation_id=TypedId.new("evaluation"),
        reason_codes=("SYNTHETIC_CANONICAL_READY",),
        missing_evidence_types=(),
        limitations=("SYNTHETIC_VALIDATION_ONLY",),
    )


def _run_context(
    *,
    assessment: MarketOptionAssessment,
    model_name: str,
) -> MarketOptionExplanationRunContext:
    return MarketOptionExplanationRunContext(
        data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
        data_contract_version=1,
        processing_activity="SYNTHETIC_AI_EXPLANATION_PIPELINE_VALIDATION",
        processing_authorization_organization_id=assessment.context.organization_id,
        processing_authorization_purpose=assessment.context.market_purpose,
        provider_profile="GEMINI_SYNTHETIC_VALIDATION_ONLY",
        model_name=model_name,
    )


def _gemini_body(prompt_payload: MarketOptionExplanationPromptPayload) -> dict[str, object]:
    return build_gemini_market_option_explanation_body(prompt_payload.provider_payload())


def _assert_payload_minimized(prompt_payload: MarketOptionExplanationPromptPayload) -> None:
    try:
        assert_gemini_market_option_explanation_payload_minimized(prompt_payload.provider_payload())
    except AIExplanationProviderUnavailable as error:
        raise SystemExit(
            f"{VERMELHO}Payload provider-facing não está minimizado: {error}.{FIM}"
        ) from error


def _pause(enabled: bool) -> None:
    if enabled:
        input(f"{CINZA}  — ENTER para o próximo —{FIM}")


def _select_models(api_key: str) -> tuple[str, ...]:
    models = _request(url=MODELS_URL, api_key=api_key)
    if models.status != 200 or not isinstance(models.body, dict):
        raise SystemExit(f"{VERMELHO}Não foi possível listar modelos Gemini.{FIM}")
    listed_model = _select_generate_model(models.body)
    if listed_model is None:
        raise SystemExit(f"{VERMELHO}Nenhum modelo Gemini com generateContent foi listado.{FIM}")
    return tuple(dict.fromkeys((*PREFERRED_GENERATE_MODELS, listed_model)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pausar", action="store_true")
    args = parser.parse_args()

    print(f"\n{NEGRITO}AI Explanation pipeline smoke — Gemini sintética{FIM}")
    print("=" * 62)
    print(
        f"{CINZA}Usa assessment sintético, payload minimizado e chave local ignorada "
        f"pelo Git. Não envia dados reais do Titan.{FIM}"
    )

    api_key = _load_api_key()

    print(f"\n{NEGRITO}[1] Resolver modelo Gemini para generateContent{FIM}")
    print(f"{CINZA}  Por que: confirma provider sem construir integração produtiva.{FIM}")
    model_names = _select_models(api_key)
    print(f"{VERDE}OK{FIM} — candidatos sintéticos: {', '.join(model_names)}")
    _pause(args.pausar)

    print(f"\n{NEGRITO}[2] Executar pipeline com provider recebendo só prompt payload{FIM}")
    print(
        f"{CINZA}  Por que: valida DataContract -> provider text -> guard -> "
        f"audit envelope/fallback.{FIM}"
    )
    assessment = _synthetic_assessment()
    result = None
    selected_model_name = ""
    for model_name in model_names:
        provider = GeminiMarketOptionExplanationTextProvider(
            api_key=api_key,
            model_name=model_name,
            enabled=True,
        )
        candidate_result = MarketOptionExplanationPipelineService(text_provider=provider).explain(
            assessment=assessment,
            run_context=_run_context(assessment=assessment, model_name=model_name),
        )
        if candidate_result.validation.accepted or (
            candidate_result.audit_envelope.release_disposition.value == "NOT_RELEASED"
            and candidate_result.validation.violations
            and all(
                violation.value != "PROVIDER_UNAVAILABLE"
                for violation in candidate_result.validation.violations
            )
        ):
            result = candidate_result
            selected_model_name = model_name
            break
    if result is None:
        raise SystemExit(f"{VERMELHO}generateContent falhou em todos os modelos candidatos.{FIM}")
    print(f"{VERDE}OK{FIM} — provider respondeu e o pipeline gerou audit envelope.")
    print(f"{CINZA}  modelo efetivo: {selected_model_name}{FIM}")
    print(f"{CINZA}  payload_digest: {result.prompt_payload.payload_digest}{FIM}")
    print(f"{CINZA}  guard_accepted: {result.validation.accepted}{FIM}")
    print(f"{CINZA}  released_output_digest: {result.audit_envelope.released_output_digest}{FIM}")
    if result.released_text is None:
        print(
            f"{CINZA}  Texto não liberado pelo guard; fallback canônico preservado "
            f"com segurança.{FIM}"
        )
    else:
        print(f"{CINZA}  Texto liberado omitido; este roteiro valida só o contrato.{FIM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
