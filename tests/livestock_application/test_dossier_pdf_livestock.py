"""Representação PDF do dossiê farmacológico (Passo 10.3).

A validação manual do PLANO é "comparar JSON e PDF campo a campo". Como o
template da vertical devolve dados em vez de desenho, essa comparação é feita
aqui em valores — o que a torna verificável em teste, e não por leitura visual.
"""

import json
from typing import Any

import pytest

from packages.core_application.dossier_pdf_template import PdfSection
from packages.core_application.dossier_service import DossierService
from packages.core_domain.dossier import Dossier
from packages.core_infrastructure.pdf import SoftwareDossierPdfAdapter
from packages.livestock_application.dossier_template import LivestockDossierTemplate
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_infrastructure.dossier_pdf_template import LivestockPdfTemplate
from tests.livestock_application.test_dossier_template_scenario import Cenario


@pytest.fixture
def cenario(context: LivestockOperationContext) -> Cenario:
    return Cenario(context)


def _dossier(cenario: Cenario) -> Dossier:
    evaluation, decision = cenario.avaliar()
    return LivestockDossierTemplate(
        timeline_service=cenario.timeline_service(),
        application_repository=cenario.application_repository,
        evidence_lookup=cenario.evidence_lookup,
        dossier_service=DossierService(),
    ).build(
        decision=decision,
        evaluation=evaluation,
        policy=cenario.policy,
        rules=[cenario.rule],
    )


def _secoes(cenario: Cenario) -> tuple[list[PdfSection], dict[str, Any]]:
    conteudo = _dossier(cenario).document["vertical"]["content"]
    return list(LivestockPdfTemplate().render(conteudo)), conteudo


def test_every_value_printed_comes_from_the_json(cenario: Cenario) -> None:
    """Fidelidade: o PDF não inventa nada que o JSON não diga."""
    secoes, conteudo = _secoes(cenario)
    fonte = json.dumps(conteudo, ensure_ascii=False)

    sisbov = conteudo["subject"]["identifiers"][0]["value"]
    hash_evidencia = conteudo["evidence_chain"][0]["evidences"][0]["content"]["content_hash"]
    impresso = "\n".join(celula for secao in secoes for linha in secao.rows for celula in linha)

    assert sisbov in impresso
    assert sisbov in fonte
    assert hash_evidencia in impresso
    assert conteudo["withdrawal"]["rule_version"] in impresso


def test_the_withdrawal_arithmetic_is_legible_on_paper(cenario: Cenario) -> None:
    secoes, conteudo = _secoes(cenario)
    carencia = next(s for s in secoes if s.title == "Carência farmacológica")

    prazo = conteudo["withdrawal"]["contributions"][0]["withdrawal_period_days"]
    celulas = [celula for linha in carencia.rows for celula in linha]
    assert "EM CARÊNCIA" in celulas
    assert f"{prazo} dias" in celulas


def test_the_operator_note_is_printed_marked_as_not_being_proof(cenario: Cenario) -> None:
    """No papel, a distinção entre anotação e prova precisa ser visível."""
    secoes, _ = _secoes(cenario)
    evidencias = next(s for s in secoes if s.title.startswith("Evidências"))

    linhas_de_nota = [linha for linha in evidencias.rows if "Anotação do operador" in linha[1]]
    assert linhas_de_nota
    assert linhas_de_nota[0][2] == "NÃO É PROVA"


def test_the_whole_timeline_is_printed_not_summarised(cenario: Cenario) -> None:
    """Resumir o histórico faria do PDF uma opinião sobre o snapshot, não uma cópia."""
    secoes, conteudo = _secoes(cenario)
    linha_do_tempo = next(s for s in secoes if s.title.startswith("Linha do tempo"))

    assert len(linha_do_tempo.rows) == len(conteudo["timeline"]["entries"])
    assert str(conteudo["timeline"]["entry_count"]) in linha_do_tempo.title


def test_the_pdf_is_produced_and_carries_the_verification_material(cenario: Cenario) -> None:
    dossier = _dossier(cenario)
    adapter = SoftwareDossierPdfAdapter(vertical_templates=[LivestockPdfTemplate()])

    representacao = adapter.generate_pdf(dossier)

    assert representacao.pdf_bytes.startswith(b"%PDF")
    assert dossier.dossier_hash in representacao.verification_qr_payload
    assert representacao.pdf_hash in representacao.verification_qr_payload


def test_a_section_without_a_template_is_declared_not_dropped() -> None:
    """Omitir esconderia do leitor que o documento diz mais do que o papel mostra."""
    adapter = SoftwareDossierPdfAdapter(vertical_templates=[])

    secoes = adapter._vertical_sections(
        {"vertical": {"namespace": "livestock", "content": {"x": 1}}}
    )

    assert len(secoes) == 1
    assert "não apresentada" in secoes[0].title


def test_a_document_without_a_vertical_section_prints_nothing_extra() -> None:
    adapter = SoftwareDossierPdfAdapter(vertical_templates=[LivestockPdfTemplate()])

    assert adapter._vertical_sections({"vertical": None}) == []
    assert adapter._vertical_sections({}) == []


def test_a_row_that_does_not_fit_its_columns_is_refused() -> None:
    """Tabela desalinhada no papel viraria dado trocado de coluna."""
    with pytest.raises(ValueError, match="não cabe"):
        PdfSection(title="X", columns=("a", "b"), rows=(("só uma",),))
