"""O cenário demonstrativo é reproduzível (Passo 10.6).

Um roteiro de demonstração que ninguém executa apodrece em silêncio: a API muda,
o cenário para de funcionar, e só se descobre na hora de mostrar a alguém. Estes
testes rodam a demonstração inteira no portão.
"""

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Connection, create_engine

from apps.demo.__main__ import Demonstracao, _gravar_artefatos, _relatorio
from apps.seed.__main__ import semear
from packages.core_domain.decision import DecisionResult
from packages.core_domain.dossier import Dossier, compute_dossier_hash

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)


@pytest.fixture
def connection() -> Iterator[Connection]:
    """Tudo desfeito ao final: a demonstração não deixa resíduo no banco de teste."""
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


@pytest.fixture
def resultado(connection: Connection) -> tuple[Demonstracao, dict[str, Any]]:
    semeado = semear(
        connection,
        issuer="http://localhost:8080/realms/titan",
        subs={"operador": "teste-operador", "auditor": "teste-auditor"},
    )
    demo = Demonstracao(connection, semeado)
    return demo, demo.executar()


def test_bloqueia_e_depois_aprova_sobre_os_fatos_corrigidos(
    resultado: tuple[Demonstracao, dict[str, Any]],
) -> None:
    """O ponto do produto: redecidir sobre correção, sem apagar a decisão anterior."""
    _, dados = resultado

    assert dados["decisao_1"].result is DecisionResult.REJEITADA
    assert dados["decisao_2"].result is DecisionResult.APROVADA
    assert dados["decisao_1"].decision_id != dados["decisao_2"].decision_id


def test_o_registro_corrigido_permanece_legivel(
    resultado: tuple[Demonstracao, dict[str, Any]],
) -> None:
    _, dados = resultado
    aplicacoes = [
        entrada
        for entrada in dados["linha_do_tempo"]
        if entrada.entry_type == "livestock.treatment_applied"
    ]

    assert len(aplicacoes) == 2, "Corrigir acrescenta; não sobrescreve."
    marcadas = [entrada for entrada in aplicacoes if entrada.superseded_by is not None]
    assert len(marcadas) == 1


def test_a_sequencia_do_plano_e_percorrida_inteira(
    resultado: tuple[Demonstracao, dict[str, Any]],
) -> None:
    """O PLANO lista: cadastro, tratamento, bloqueio, correção, reavaliação e dossiê."""
    demo, _ = resultado
    titulos = [passo.titulo for passo in demo.passos]

    assert titulos == [
        "Cadastro",
        "Insumo",
        "Tratamento",
        "Bloqueio",
        "Correção",
        "Reavaliação",
        "Dossiê",
    ]


def test_o_dossie_gravado_em_disco_verifica_se_sem_o_titan(
    resultado: tuple[Demonstracao, dict[str, Any]], tmp_path: Path
) -> None:
    """A prova precisa sobreviver ao transporte: JSON em disco, lido de volta."""
    _, dados = resultado

    caminho_json, caminho_pdf = _gravar_artefatos(dados["dossie"], tmp_path)

    documento = json.loads(caminho_json.read_text(encoding="utf-8"))
    reconstruido = Dossier.from_dict(documento)
    assert reconstruido.verify()
    assert reconstruido.dossier_hash == compute_dossier_hash(reconstruido.document)
    assert caminho_pdf.read_bytes().startswith(b"%PDF")


def test_o_relatorio_narra_o_que_aconteceu(
    resultado: tuple[Demonstracao, dict[str, Any]], tmp_path: Path
) -> None:
    """O relatório é a entrega para quem assiste, e precisa dizer o essencial."""
    demo, dados = resultado
    artefatos = _gravar_artefatos(dados["dossie"], tmp_path)

    texto = _relatorio(demo, dados, artefatos)

    assert "REJEITADA" in texto
    assert "APROVADA" in texto
    assert "Corrigir acrescentou" in texto


def test_nenhum_dado_pessoal_no_cenario(resultado: tuple[Demonstracao, dict[str, Any]]) -> None:
    """A entrega do PLANO exige fixtures fictícias, sem dados reais ou pessoais."""
    _, dados = resultado
    documento = json.dumps(dados["dossie"].to_dict(), ensure_ascii=False)

    for suspeito in ("@", "cpf", "CPF"):
        assert suspeito not in documento, f"'{suspeito}' aparece no dossiê da demonstração."
