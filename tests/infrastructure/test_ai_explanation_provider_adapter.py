import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from packages.livestock_application.market_optionality import (
    MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
    MarketOptionAssessment,
    MarketOptionContext,
    MarketOptionExplanationDataContractService,
    MarketOptionExplanationGuardService,
    MarketOptionExplanationPipelineService,
    MarketOptionExplanationPromptPayload,
    MarketOptionExplanationRunContext,
    MarketOptionReversibility,
    MarketOptionState,
)
from packages.livestock_infrastructure.ai_explanation_provider import (
    AIExplanationProviderUnavailable,
    AIProviderHttpResponse,
    GeminiMarketOptionExplanationTextProvider,
    assert_gemini_market_option_explanation_payload_minimized,
    build_gemini_market_option_explanation_body,
)
from packages.shared_kernel import OrganizationId, TypedId

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


@dataclass(slots=True)
class CapturingTransport:
    response: AIProviderHttpResponse
    calls: list[dict[str, object]]

    def post_json(
        self,
        *,
        url: str,
        api_key: str,
        body: dict[str, object],
        timeout_seconds: int,
    ) -> AIProviderHttpResponse:
        self.calls.append(
            {
                "url": url,
                "api_key": api_key,
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.response


def test_gemini_provider_is_disabled_by_default_and_makes_no_http_call() -> None:
    transport = CapturingTransport(response=_gemini_response("ignored"), calls=[])
    provider = GeminiMarketOptionExplanationTextProvider(
        api_key="test-key",
        model_name="models/gemini-test",
        transport=transport,
    )

    with pytest.raises(AIExplanationProviderUnavailable):
        provider.generate_text(
            prompt_payload=_prompt_payload(),
            run_context=_run_context(assessment=_assessment(), model_name="models/gemini-test"),
        )

    assert transport.calls == []


def test_gemini_provider_sends_only_minimized_payload_fields() -> None:
    assessment = _assessment()
    transport = CapturingTransport(response=_gemini_response("Resumo sintético seguro."), calls=[])
    provider = GeminiMarketOptionExplanationTextProvider(
        api_key="test-key",
        model_name="models/gemini-test",
        enabled=True,
        transport=transport,
    )

    text = provider.generate_text(
        prompt_payload=_prompt_payload(assessment=assessment),
        run_context=_run_context(assessment=assessment, model_name="models/gemini-test"),
    )

    assert text == "Resumo sintético seguro."
    assert len(transport.calls) == 1
    body_text = json.dumps(transport.calls[0]["body"], ensure_ascii=False, default=str)
    assert str(assessment.context.organization_id) not in body_text
    assert str(assessment.context.subject_id) not in body_text
    assert str(assessment.context.policy_id) not in body_text
    assert str(assessment.decision_id) not in body_text
    assert str(assessment.evaluation_id) not in body_text
    assert "source_reference_aliases" not in body_text
    assert "reason_codes" not in body_text
    assert "reason_aliases" in body_text
    assert "knowledge_cutoff" in body_text
    assert transport.calls[0]["api_key"] == "test-key"


def test_gemini_provider_rejects_raw_identifier_fields_before_http_call() -> None:
    transport = CapturingTransport(response=_gemini_response("ignored"), calls=[])
    payload = MarketOptionExplanationPromptPayload(
        data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
        data_contract_version=1,
        schema="MARKET_OPTIONALITY_AI_EXPLANATION_CONTEXT_V1",
        prompt_template_id="market-optionality-explanation-canonical-summary",
        prompt_template_version=1,
        prompt_template_digest="a" * 64,
        guard_version=1,
        guard_digest="b" * 64,
        payload_digest="c" * 64,
        fields={"organization_id": "org:leak"},
        source_reference_aliases={},
    )
    provider = GeminiMarketOptionExplanationTextProvider(
        api_key="test-key",
        model_name="models/gemini-test",
        enabled=True,
        transport=transport,
    )

    with pytest.raises(AIExplanationProviderUnavailable):
        provider.generate_text(
            prompt_payload=payload,
            run_context=_run_context(assessment=_assessment(), model_name="models/gemini-test"),
        )

    assert transport.calls == []


def test_gemini_provider_model_mismatch_fails_closed_before_http_call() -> None:
    transport = CapturingTransport(response=_gemini_response("ignored"), calls=[])
    provider = GeminiMarketOptionExplanationTextProvider(
        api_key="test-key",
        model_name="models/gemini-test-a",
        enabled=True,
        transport=transport,
    )

    with pytest.raises(AIExplanationProviderUnavailable):
        provider.generate_text(
            prompt_payload=_prompt_payload(),
            run_context=_run_context(assessment=_assessment(), model_name="models/gemini-test-b"),
        )

    assert transport.calls == []


def test_gemini_provider_environment_factory_is_feature_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(os.environ, "GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.delenv("TITAN_GOOGLE_AI_EXPLANATION_PROVIDER_ENABLED", raising=False)

    disabled = GeminiMarketOptionExplanationTextProvider.from_environment(
        model_name="models/gemini-test",
    )
    assert disabled.enabled is False

    monkeypatch.setitem(os.environ, "TITAN_GOOGLE_AI_EXPLANATION_PROVIDER_ENABLED", "true")
    enabled = GeminiMarketOptionExplanationTextProvider.from_environment(
        model_name="models/gemini-test",
    )
    assert enabled.enabled is True


def test_pipeline_with_gemini_adapter_falls_back_when_provider_disabled() -> None:
    result = MarketOptionExplanationPipelineService(
        text_provider=GeminiMarketOptionExplanationTextProvider(
            api_key="test-key",
            model_name="models/gemini-test",
        )
    ).explain(
        assessment=(assessment := _assessment()),
        run_context=_run_context(assessment=assessment, model_name="models/gemini-test"),
    )

    assert result.released_text is None
    assert result.canonical_fallback.state is MarketOptionState.OPTION_OPEN
    assert [violation.value for violation in result.validation.violations] == [
        "PROVIDER_UNAVAILABLE"
    ]


def test_body_builder_does_not_serialize_source_reference_aliases() -> None:
    payload = _prompt_payload(assessment=_assessment())
    assert payload.source_reference_aliases

    body_text = json.dumps(
        build_gemini_market_option_explanation_body(payload),
        ensure_ascii=False,
        default=str,
    )

    assert "source_reference_aliases" not in body_text
    assert "claim_source" in body_text


def _prompt_payload(
    *,
    assessment: MarketOptionAssessment | None = None,
) -> MarketOptionExplanationPromptPayload:
    assessment = _assessment() if assessment is None else assessment
    context = MarketOptionExplanationGuardService().prepare_context(assessment=assessment)
    payload = MarketOptionExplanationDataContractService().build_prompt_payload(
        explanation_context=context,
        run_context=_run_context(assessment=assessment, model_name="models/gemini-test"),
    )
    assert_gemini_market_option_explanation_payload_minimized(payload)
    return payload


def _assessment() -> MarketOptionAssessment:
    context = MarketOptionContext(
        organization_id=OrganizationId.new(),
        subject_id=TypedId.new("animal"),
        market_purpose="synthetic-ai-provider-validation",
        policy_id=TypedId.new("policy"),
        policy_version=1,
        reference_time=NOW,
        knowledge_cutoff=NOW,
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
        processing_activity="SYNTHETIC_AI_EXPLANATION_PROVIDER_VALIDATION",
        processing_authorization_organization_id=assessment.context.organization_id,
        processing_authorization_purpose=assessment.context.market_purpose,
        provider_profile="GEMINI_SYNTHETIC_VALIDATION_ONLY",
        model_name=model_name,
    )


def _gemini_response(text: str) -> AIProviderHttpResponse:
    return AIProviderHttpResponse(
        status=200,
        body={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": text,
                            }
                        ]
                    }
                }
            ]
        },
    )
