from typing import Any

from apps.validacao.simulacao_comercial import (
    _animal_aparece_com_saida_para_frigorifico,
    _matriz_comercial_com_sujeito_escolhido_tem_forma_esperada,
    _matriz_comercial_tem_forma_esperada,
)


def test_matriz_comercial_tem_forma_esperada_quando_destinos_estao_comparaveis() -> None:
    assert _matriz_comercial_tem_forma_esperada(
        [
            {
                "market": "exportacao-china",
                "status": "CONDICIONADO",
                "dependency": {
                    "subject_key": "slaughterhouse",
                    "selected_subject_id": None,
                },
                "requirements": [
                    {"status": "ELEGIVEL"},
                    {"status": "CONDICIONADO"},
                ],
                "gaps": [{"code": "DEPENDENCIA_DE_SUJEITO_NAO_ESCOLHIDO"}],
            },
            {
                "market": "exportacao-estados-unidos",
                "status": "ELEGIVEL",
                "requirements": [{"status": "ELEGIVEL"}],
                "gaps": [],
            },
            {
                "market": "exportacao-uniao-europeia",
                "status": "AUSENTE",
                "requirements": [{"status": "AUSENTE"}],
                "gaps": [{"code": "REGRA_GOVERNADA_AUSENTE"}],
            },
        ]
    )


def test_matriz_comercial_tem_forma_esperada_falha_quando_ue_nao_explica_ausencia() -> None:
    assert not _matriz_comercial_tem_forma_esperada(
        [
            {
                "market": "exportacao-china",
                "status": "CONDICIONADO",
                "dependency": {
                    "subject_key": "slaughterhouse",
                    "selected_subject_id": None,
                },
                "requirements": [
                    {"status": "ELEGIVEL"},
                    {"status": "CONDICIONADO"},
                ],
                "gaps": [{"code": "DEPENDENCIA_DE_SUJEITO_NAO_ESCOLHIDO"}],
            },
            {
                "market": "exportacao-estados-unidos",
                "status": "ELEGIVEL",
                "requirements": [{"status": "ELEGIVEL"}],
                "gaps": [],
            },
            {
                "market": "exportacao-uniao-europeia",
                "status": "AUSENTE",
                "requirements": [{"status": "AUSENTE"}],
                "gaps": [],
            },
        ]
    )


def test_matriz_comercial_com_sujeito_escolhido_tem_forma_esperada() -> None:
    assert _matriz_comercial_com_sujeito_escolhido_tem_forma_esperada(
        [
            {
                "market": "exportacao-china",
                "status": "ELEGIVEL",
                "dependency": {
                    "subject_key": "slaughterhouse",
                    "selected_subject_id": "frigorifico-1",
                },
                "requirements": [
                    {"status": "ELEGIVEL"},
                    {
                        "status": "ELEGIVEL",
                        "dependency": {"selected_subject_id": "frigorifico-1"},
                        "gaps": [],
                    },
                ],
                "gaps": [],
            },
            {
                "market": "exportacao-estados-unidos",
                "status": "ELEGIVEL",
                "requirements": [{"status": "ELEGIVEL"}],
                "gaps": [],
            },
            {
                "market": "exportacao-uniao-europeia",
                "status": "AUSENTE",
                "requirements": [{"status": "AUSENTE"}],
                "gaps": [{"code": "REGRA_GOVERNADA_AUSENTE"}],
            },
        ],
        "frigorifico-1",
    )


def test_matriz_comercial_com_sujeito_escolhido_falha_com_id_diferente() -> None:
    assert not _matriz_comercial_com_sujeito_escolhido_tem_forma_esperada(
        [
            {
                "market": "exportacao-china",
                "status": "ELEGIVEL",
                "dependency": {
                    "subject_key": "slaughterhouse",
                    "selected_subject_id": "frigorifico-2",
                },
                "requirements": [
                    {"status": "ELEGIVEL"},
                    {
                        "status": "ELEGIVEL",
                        "dependency": {"selected_subject_id": "frigorifico-2"},
                        "gaps": [],
                    },
                ],
                "gaps": [],
            },
            {
                "market": "exportacao-estados-unidos",
                "status": "ELEGIVEL",
                "requirements": [{"status": "ELEGIVEL"}],
                "gaps": [],
            },
            {
                "market": "exportacao-uniao-europeia",
                "status": "AUSENTE",
                "requirements": [{"status": "AUSENTE"}],
                "gaps": [{"code": "REGRA_GOVERNADA_AUSENTE"}],
            },
        ],
        "frigorifico-1",
    )


def test_animal_aparece_com_saida_para_frigorifico() -> None:
    items: list[dict[str, Any]] = [
        {"animal_id": "outro", "saida": None},
        {
            "animal_id": "animal-1",
            "saida": {
                "exit_type": "ABATE",
                "destination_counterparty_id": "frigorifico-1",
            },
        },
    ]

    assert _animal_aparece_com_saida_para_frigorifico(items, "animal-1", "frigorifico-1")


def test_animal_aparece_com_saida_para_frigorifico_falha_com_destino_errado() -> None:
    items: list[dict[str, Any]] = [
        {
            "animal_id": "animal-1",
            "saida": {
                "exit_type": "ABATE",
                "destination_counterparty_id": "frigorifico-2",
            },
        }
    ]

    assert not _animal_aparece_com_saida_para_frigorifico(items, "animal-1", "frigorifico-1")
