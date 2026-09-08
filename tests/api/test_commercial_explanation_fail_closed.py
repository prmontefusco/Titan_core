"""FINDING-001: a explicacao preserva a conclusao sanitaria da avaliacao."""

from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy import Connection

from apps.api import livestock_queries as api
from packages.core_domain import OrganizationContext

MARKET = "exportacao-china"
GAP = "Nao existe prazo de carencia aplicavel declarado para este mercado."


@pytest.mark.parametrize(
    ("status", "selected", "heterogeneous"),
    [
        ("INDETERMINADO", None, False),
        ("INDETERMINADO", "estabelecimento-ficticio", False),
        ("INDETERMINADO", "estabelecimento-ficticio", True),
        ("ELEGIVEL", "estabelecimento-ficticio", False),
        ("CONDICIONADO", None, False),
    ],
)
def test_lot_explanation_preserves_canonical_market_conclusion(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    selected: str | None,
    heterogeneous: bool,
) -> None:
    """Base suficiente libera; carencia ausente nunca e suprida pela apresentacao."""
    indeterminate = status == "INDETERMINADO"
    eligible = status == "ELEGIVEL"
    summary = GAP if indeterminate else "Resultado canonico do animal."
    animals: list[dict[str, Any]] = [
        {
            "animal_id": "animal-inconclusivo" if indeterminate else "animal-ficticio",
            "status": status,
            "summary": summary,
            "gaps": [{"code": "CARENCIA_POR_MERCADO_AUSENTE", "message": GAP}]
            if indeterminate
            else [],
        }
    ]
    if heterogeneous:
        animals.append(
            {"animal_id": "animal-elegivel", "status": "ELEGIVEL", "summary": "Elegivel."}
        )
    market: dict[str, Any] = {
        "market": MARKET,
        "status": status,
        "summary": "Conclusao canonica do lote.",
        "dependency": {"subject_label": "estabelecimento", "selected_subject_id": selected},
        "animals": animals,
        "indeterminate_animal_ids": ["animal-inconclusivo"] if indeterminate else [],
    }
    outlook = (
        "TOTALMENTE_COMERCIALIZAVEL"
        if eligible
        else "INCONCLUSIVO"
        if indeterminate
        else "DEPENDENTE_DE_ACAO"
    )
    evaluation = api.AvaliacaoMercadosLoteResponse(
        lot_id="lote-ficticio",
        member_count=len(animals),
        requested_markets=[MARKET],
        commercial_outlook=outlook,
        can_sell_to_any_requested_market=eligible,
        executive_summary="Resumo da avaliacao canonica.",
        eligible_markets=[MARKET] if eligible else [],
        blocked_markets=[],
        conditioned_markets=[MARKET] if status == "CONDICIONADO" else [],
        indeterminate_markets=[MARKET] if indeterminate else [],
        missing_markets=[],
        required_subjects=[],
        market_gaps=[],
        markets=[market],
    )
    evaluator = Mock(return_value=evaluation)
    monkeypatch.setattr(api, "executar_avaliacao_orientada_a_mercados_para_lote", evaluator)
    context = Mock(spec=OrganizationContext)
    connection = Mock(spec=Connection)

    response = api.gerar_explicacao_comercial(
        api.ExplicacaoComercialRequest(
            lot_id=evaluation.lot_id,
            markets=[MARKET],
            slaughterhouse_counterparty_id=selected,
        ),
        contexto=context,
        connection=connection,
    )

    assert response.commercial_outlook == outlook
    assert response.can_sell_to_any_requested_market is eligible
    assert response.executive_summary == evaluation.executive_summary
    assert response.markets[0].status == status
    assert response.markets[0].summary == market["summary"]
    if indeterminate:
        assert response.markets[0].why == [GAP]
        assert "pode ser comercializado" not in response.narrative
        assert response.markets[0].affected_animal_ids == (
            ["animal-inconclusivo"] if selected is not None else []
        )
    elif eligible:
        assert response.markets[0].next_action is None
        assert response.markets[0].affected_animal_ids == []
    else:
        assert "selecione o estabelecimento" in response.markets[0].why[0]
        assert response.markets[0].affected_animal_ids == []
    evaluator.assert_called_once_with(
        api.AvaliacaoMercadosLoteRequest(
            lot_id=evaluation.lot_id,
            markets=[MARKET],
            slaughterhouse_counterparty_id=selected,
        ),
        contexto=context,
        connection=connection,
    )
