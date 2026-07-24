"""Template Livestock do dossiê da decisão farmacológica (Passo 10.2).

O que estes testes protegem: o dossiê se explica sem o banco, a identidade é a do
instante da decisão, a cadeia até a evidência é percorrível, e nada do que veio
depois da decisão aparece dentro dela.
"""

import json
from datetime import datetime

import pytest

from packages.core_application.dossier_service import DossierService
from packages.core_domain.decision import DecisionResult
from packages.core_domain.dossier import Dossier, compute_dossier_hash
from packages.livestock_application.dossier_template import (
    LIVESTOCK_NAMESPACE,
    LivestockDossierTemplate,
)
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.shared_kernel import TypedId
from tests.livestock_application.test_dossier_template_scenario import Cenario


@pytest.fixture
def cenario(context: LivestockOperationContext) -> Cenario:
    return Cenario(context)


def _dossier(cenario: Cenario) -> tuple[Dossier, DecisionResult]:
    evaluation, decision = cenario.avaliar()
    template = LivestockDossierTemplate(
        timeline_service=cenario.timeline_service(),
        application_repository=cenario.application_repository,
        evidence_lookup=cenario.evidence_lookup,
        dossier_service=DossierService(),
    )
    dossier = template.build(
        decision=decision,
        evaluation=evaluation,
        policy=cenario.policy,
        rules=[cenario.rule],
    )
    return dossier, decision.result


def test_the_dossier_verifies_itself_offline(cenario: Cenario) -> None:
    """Prova que não depende do Titan: serializa, descarta tudo e ainda confere."""
    dossier, _ = _dossier(cenario)

    transportado = json.loads(json.dumps(dossier.to_dict()))
    reconstruido = Dossier.from_dict(transportado)

    assert reconstruido.verify()
    assert reconstruido.dossier_hash == compute_dossier_hash(reconstruido.document)


def test_the_animal_is_identifiable_by_the_tag_a_fiscal_reads(cenario: Cenario) -> None:
    """UUID ninguém confere contra um boi; brinco e SISBOV, sim."""
    dossier, _ = _dossier(cenario)

    subject = dossier.document["vertical"]["content"]["subject"]
    valores = [tag["value"] for tag in subject["identifiers"]]
    assert "BR12345678" in valores
    # A identidade vem do snapshot congelado, não do cadastro atual.
    assert subject["identity_source"] == "fact_snapshot"


def test_the_blocking_decision_shows_its_arithmetic(cenario: Cenario) -> None:
    dossier, resultado = _dossier(cenario)

    assert resultado is DecisionResult.REJEITADA
    withdrawal = dossier.document["vertical"]["content"]["withdrawal"]
    assert withdrawal["in_withdrawal"] is True
    assert withdrawal["rule_version"] == "titan-livestock-withdrawal-v1"
    contribuicao = withdrawal["contributions"][0]
    aplicado = datetime.fromisoformat(contribuicao["applied_at"])
    fim = datetime.fromisoformat(contribuicao["withdrawal_ends_at"])
    assert (fim - aplicado).days == contribuicao["withdrawal_period_days"]


def test_the_chain_reaches_the_evidence_with_its_content_hash(cenario: Cenario) -> None:
    """Sem o hash, quem tem o arquivo original não teria como conferir que é o mesmo."""
    dossier, _ = _dossier(cenario)

    cadeia = dossier.document["vertical"]["content"]["evidence_chain"]
    assert len(cadeia) == 1
    elo = cadeia[0]
    assert elo["status"] == "RESOLVIDA"
    evidencia = elo["evidences"][0]
    assert evidencia["content_status"] == "COPIADO"
    assert len(evidencia["content"]["content_hash"]) == 64
    assert evidencia["content"]["source"]["source_type"] == "DOCUMENT"
    assert evidencia["content"]["confidence"]["tier"] == "DOCUMENTED"


def test_operator_notes_never_pose_as_evidence(cenario: Cenario) -> None:
    dossier, _ = _dossier(cenario)

    elo = dossier.document["vertical"]["content"]["evidence_chain"][0]
    assert elo["notes"] == ("foto no celular do João",) or elo["notes"] == [
        "foto no celular do João"
    ]
    assert "foto no celular do João" not in json.dumps(elo["evidences"])


def test_the_timeline_travels_whole_up_to_the_decision(cenario: Cenario) -> None:
    dossier, _ = _dossier(cenario)

    timeline = dossier.document["vertical"]["content"]["timeline"]
    tipos = [entrada["entry_type"] for entrada in timeline["entries"]]
    assert "livestock.animal_registered" in tipos
    assert "livestock.identifier_attached" in tipos
    assert "livestock.treatment_applied" in tipos
    assert timeline["entry_count"] == len(timeline["entries"])
    assert timeline["cutoff_axis"] == "recorded_at"


def test_nothing_recorded_after_the_decision_enters_the_proof(cenario: Cenario) -> None:
    """Prova emitida hoje não pode conter o que só foi lançado amanhã."""
    dossier, _ = _dossier(cenario)
    corte = datetime.fromisoformat(
        dossier.document["vertical"]["content"]["timeline"]["known_until"]
    )

    for entrada in dossier.document["vertical"]["content"]["timeline"]["entries"]:
        assert datetime.fromisoformat(entrada["recorded_at"]) <= corte


def test_a_treatment_entered_after_the_decision_stays_out(cenario: Cenario) -> None:
    dossier_antes, _ = _dossier(cenario)
    antes = dossier_antes.document["vertical"]["content"]["timeline"]["entry_count"]

    cenario.tratar(dias_atras=1)
    dossier_depois, _ = _dossier(cenario)
    depois = dossier_depois.document["vertical"]["content"]["timeline"]["entry_count"]

    assert depois > antes, "A nova decisão enxerga o lançamento novo."
    # E a prova antiga continua íntegra, sem o fato que ainda não existia.
    assert dossier_antes.verify()


def test_the_vertical_section_declares_who_it_belongs_to(cenario: Cenario) -> None:
    dossier, _ = _dossier(cenario)

    assert dossier.document["vertical"]["namespace"] == LIVESTOCK_NAMESPACE
    assert dossier.document["vertical"]["section_version"] >= 1


def test_the_template_refuses_a_subject_that_is_not_an_animal(cenario: Cenario) -> None:
    evaluation, decision = cenario.avaliar()
    template = LivestockDossierTemplate(
        timeline_service=cenario.timeline_service(),
        application_repository=cenario.application_repository,
        evidence_lookup=cenario.evidence_lookup,
    )
    from dataclasses import replace

    lote = replace(decision, subject_id=TypedId.new("livestock_lot"))

    with pytest.raises(ValueError, match="dossiê de animal"):
        template.build(
            decision=lote,
            evaluation=evaluation,
            policy=cenario.policy,
            rules=[cenario.rule],
        )
