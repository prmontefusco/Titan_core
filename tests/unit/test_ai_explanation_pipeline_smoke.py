import json

import pytest

from apps.validacao.ai_explanation_pipeline_smoke import (
    _assert_payload_minimized,
    _gemini_body,
    _run_context,
    _synthetic_assessment,
)
from packages.livestock_application.market_optionality import (
    MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
    MarketOptionExplanationDataContractService,
    MarketOptionExplanationGuardService,
    MarketOptionExplanationPromptPayload,
)


def test_ai_explanation_pipeline_smoke_body_uses_only_minimized_payload() -> None:
    assessment = _synthetic_assessment()
    context = MarketOptionExplanationGuardService().prepare_context(assessment=assessment)
    payload = MarketOptionExplanationDataContractService().build_prompt_payload(
        explanation_context=context,
        run_context=_run_context("models/synthetic-test"),
    )

    body = _gemini_body(payload)
    body_text = json.dumps(body, ensure_ascii=False, default=str)

    assert str(assessment.context.organization_id) not in body_text
    assert str(assessment.context.subject_id) not in body_text
    assert str(assessment.context.policy_id) not in body_text
    assert str(assessment.decision_id) not in body_text
    assert str(assessment.evaluation_id) not in body_text
    assert "source_reference_aliases" not in body_text
    assert "option_state" in body_text
    assert "knowledge_cutoff" in body_text


def test_ai_explanation_pipeline_smoke_rejects_non_minimized_payload() -> None:
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

    with pytest.raises(SystemExit):
        _assert_payload_minimized(payload)
