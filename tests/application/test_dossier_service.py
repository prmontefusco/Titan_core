"""Testes de aplicação para o Dossier autocontido (Passo 7.5)."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from packages.core_application.decision_service import DecisionService
from packages.core_application.dossier_service import DossierService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_domain.decision import Decision
from packages.core_domain.dossier import (
    DOSSIER_DOCUMENT_VERSION,
    Dossier,
    compute_dossier_hash,
)
from packages.core_domain.evaluation import Evaluation, EvaluationOutcome
from packages.core_domain.evidence import (
    ConfidenceLevel,
    ConfidenceTier,
    Evidence,
    EvidenceRevocation,
    Source,
    SourceType,
    compute_content_hash,
)
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.nonconformity import NonConformity, NonConformityOrigin
from packages.core_domain.policy import Policy
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _cenario(
    resultado_do_fato: str = "rejected",
) -> tuple[OrganizationId, TypedId, Policy, Rule, Evaluation, Decision]:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    t0 = datetime.now(UTC)

    policy = Policy.create_draft(
        organization_id=org_id, code="pol-sanitaria", name="Política Sanitária"
    ).publish()
    rule = Rule.create(
        policy_id=policy.policy_id,
        organization_id=org_id,
        code="rule-atestado",
        name="Atestado aprovado",
        description="Exige atestado sanitário aprovado",
        severity=SeverityLevel.BLOCKING,
        conditions=(
            RuleCondition(
                fact_type="sanitary.attestation",
                payload_key="result",
                operator=ComparisonOperator.EQUALS,
                expected_value="approved",
                description="Atestado deve estar aprovado",
            ),
        ),
        corrective_action="Reemitir o atestado sanitário.",
    )
    snapshot = FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=t0,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": resultado_do_fato, "emitido_por": "vet-42"},
                observed_at=t0,
                source_reference=UniversalReference(
                    target_id=TypedId.new("evidence"),
                    organization_id=org_id,
                    contract_version=1,
                ),
            )
        ],
    )
    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="CONFORMIDADE_SANITARIA"
    )
    decision = DecisionService().decide(evaluation)
    return org_id, subject_id, policy, rule, evaluation, decision


def test_dossier_is_self_contained_and_verifiable_offline() -> None:
    _, subject_id, policy, rule, evaluation, decision = _cenario()

    dossier = DossierService().build(
        decision=decision, evaluation=evaluation, policy=policy, rules=[rule]
    )

    assert dossier.verify()
    assert dossier.recompute_hash() == dossier.dossier_hash

    doc = dossier.document
    # Tudo que explica a decisão viaja dentro do documento.
    assert doc["subject"]["id"] == str(subject_id.value)
    assert doc["policy"]["code"] == "pol-sanitaria"
    assert doc["rules"][0]["conditions"][0]["expected_value"] == "approved"
    assert doc["facts"]["facts"][0]["payload"]["emitido_por"] == "vet-42"
    assert doc["evaluation"]["outcome"] == EvaluationOutcome.CONDICOES_NAO_SATISFEITAS.value
    assert doc["decision"]["result"] == decision.result.value
    assert doc["decision"]["reasons"][0]["rule_code"] == "rule-atestado"
    assert doc["evidences"]


def test_decision_can_be_reproduced_from_the_document_alone() -> None:
    _, _, policy, rule, evaluation, decision = _cenario()
    doc = (
        DossierService()
        .build(decision=decision, evaluation=evaluation, policy=policy, rules=[rule])
        .document
    )

    # Um leitor sem banco consegue refazer o raciocínio: pega a condição declarada,
    # aplica ao fato preservado e chega ao mesmo resultado da regra.
    condicao = doc["rules"][0]["conditions"][0]
    fato = next(f for f in doc["facts"]["facts"] if f["fact_type"] == condicao["fact_type"])
    satisfeita = fato["payload"][condicao["payload_key"]] == condicao["expected_value"]

    resultado_gravado = doc["evaluation"]["rule_results"][0]["status"]
    assert satisfeita is False
    assert resultado_gravado == "nao_atendida"
    assert doc["decision"]["result"] == "rejeitada"


def test_hash_changes_when_any_content_changes() -> None:
    _, _, policy, rule, evaluation, decision = _cenario()
    dossier = DossierService().build(
        decision=decision, evaluation=evaluation, policy=policy, rules=[rule]
    )

    adulterado = dict(dossier.document)
    adulterado["decision"] = dict(adulterado["decision"])
    adulterado["decision"]["result"] = "aprovada"

    assert compute_dossier_hash(adulterado) != dossier.dossier_hash


def test_hash_is_stable_across_rebuilds_of_the_same_content() -> None:
    _, _, policy, rule, evaluation, decision = _cenario()
    service = DossierService()
    instante = datetime.now(UTC)

    um = service.build(
        decision=decision,
        evaluation=evaluation,
        policy=policy,
        rules=[rule],
        generated_at=instante,
    )
    outro = service.build(
        decision=decision,
        evaluation=evaluation,
        policy=policy,
        rules=[rule],
        generated_at=instante,
    )

    assert um.dossier_hash == outro.dossier_hash
    assert um.dossier_id != outro.dossier_id


def test_nonconformities_travel_with_their_history() -> None:
    org_id, subject_id, policy, rule, evaluation, decision = _cenario()
    nc = NonConformity.detect(
        organization_id=org_id,
        subject_reference=UniversalReference(
            target_id=subject_id, organization_id=org_id, contract_version=1
        ),
        origin=NonConformityOrigin.REGRA_NAO_ATENDIDA,
        severity=SeverityLevel.BLOCKING,
        description="Atestado reprovado.",
        detected_at=evaluation.evaluated_at,
    )

    doc = (
        DossierService()
        .build(
            decision=decision,
            evaluation=evaluation,
            policy=policy,
            rules=[rule],
            nonconformities=[nc],
        )
        .document
    )

    assert doc["nonconformities"][0]["origin"] == "regra_nao_atendida"
    assert doc["nonconformities"][0]["transitions"]


def test_incoherent_material_is_refused() -> None:
    _, _, policy, rule, evaluation, decision = _cenario()
    service = DossierService()

    outra_evaluation = replace(evaluation, evaluation_id=TypedId.new("evaluation"))
    with pytest.raises(ValueError, match="não pertence à avaliação"):
        service.build(decision=decision, evaluation=outra_evaluation, policy=policy, rules=[rule])

    outra_policy = Policy.create_draft(
        organization_id=decision.organization_id, code="outra", name="Outra"
    ).publish()
    with pytest.raises(ValueError, match="não pertence à política"):
        service.build(decision=decision, evaluation=evaluation, policy=outra_policy, rules=[rule])


def test_tampered_evaluation_cannot_compose_a_dossier() -> None:
    _, _, policy, rule, evaluation, decision = _cenario()
    adulterada = replace(evaluation, outcome=EvaluationOutcome.CONDICOES_SATISFEITAS)

    with pytest.raises(ValueError, match="Evaluation não reproduzível"):
        DossierService().build(
            decision=replace(decision, evaluation_id=adulterada.evaluation_id),
            evaluation=adulterada,
            policy=policy,
            rules=[rule],
        )


def test_storing_requires_a_repository() -> None:
    _, _, policy, rule, evaluation, decision = _cenario()
    with pytest.raises(RuntimeError, match="exige repositório"):
        DossierService().build_and_store(
            decision=decision, evaluation=evaluation, policy=policy, rules=[rule]
        )


# -- Conteúdo da evidência no dossiê (correção do Passo 10.2) -----------------


def _evidencia(org_id: OrganizationId, evidence_id: TypedId) -> Evidence:
    """Evidência com o mesmo identificador que a decisão cita."""
    return Evidence(
        evidence_id=evidence_id,
        organization_id=org_id,
        source=Source(
            source_id=TypedId.new("source"),
            source_type=SourceType.DOCUMENT,
            identifier_uri="nfe://35260712345678000199550010000000011000000017",
        ),
        author_reference=UniversalReference(
            target_id=TypedId.new("actor"), organization_id=org_id, contract_version=1
        ),
        content_hash=compute_content_hash(b"conteudo-da-nota-fiscal"),
        registered_at=datetime.now(UTC),
        confidence_level=ConfidenceLevel(
            tier=ConfidenceTier.DOCUMENTED, reason="Nota fiscal anexada pelo produtor."
        ),
    )


def test_evidence_content_travels_inside_the_document() -> None:
    """Sem o conteúdo, o dossiê exigiria o banco do Titan para ser compreendido."""
    org_id, _, policy, rule, evaluation, decision = _cenario()
    citada = decision.evidence_references[0].target_id
    evidencia = _evidencia(org_id, citada)

    dossier = DossierService().build(
        decision=decision,
        evaluation=evaluation,
        policy=policy,
        rules=[rule],
        evidences=[evidencia],
    )

    entrada = dossier.document["evidences"][0]
    assert entrada["id"] == str(citada.value)
    assert entrada["content_status"] == "COPIADO"
    # O hash do conteúdo é o que permite a quem tem o arquivo original conferir
    # que é o mesmo, sem nos consultar.
    assert entrada["content"]["content_hash"] == evidencia.content_hash.hex()
    assert entrada["content"]["source"]["source_type"] == SourceType.DOCUMENT.value
    assert entrada["content"]["confidence"]["tier"] == ConfidenceTier.DOCUMENTED.value
    assert dossier.verify()


def test_absent_evidence_content_is_declared_not_omitted() -> None:
    """Quem lê precisa distinguir 'não havia evidência' de 'havia e não veio'."""
    _, _, policy, rule, evaluation, decision = _cenario()

    dossier = DossierService().build(
        decision=decision, evaluation=evaluation, policy=policy, rules=[rule]
    )

    entrada = dossier.document["evidences"][0]
    assert entrada["content"] is None
    assert entrada["content_status"] == "NAO_ACOMPANHA"
    # O identificador continua lá: a entrada não sumiu, só o conteúdo não veio.
    assert entrada["id"] == str(decision.evidence_references[0].target_id.value)


def test_revoked_evidence_is_never_presented_as_valid() -> None:
    """Apresentar evidência revogada como se valesse transformaria o dossiê em prova falsa."""
    org_id, _, policy, rule, evaluation, decision = _cenario()
    citada = decision.evidence_references[0].target_id
    revogada = _evidencia(org_id, citada).revoke(
        EvidenceRevocation(
            revoked_at=datetime.now(UTC),
            revoking_actor=UniversalReference(
                target_id=TypedId.new("actor"), organization_id=org_id, contract_version=1
            ),
            reason="Nota fiscal cancelada na SEFAZ.",
        )
    )

    dossier = DossierService().build(
        decision=decision,
        evaluation=evaluation,
        policy=policy,
        rules=[rule],
        evidences=[revogada],
    )

    revogacao = dossier.document["evidences"][0]["content"]["revocation"]
    assert revogacao is not None
    assert revogacao["reason"] == "Nota fiscal cancelada na SEFAZ."


def test_unrelated_evidence_is_not_smuggled_into_the_document() -> None:
    """Só entra o que a decisão citou: o dossiê não é vitrine de material avulso."""
    org_id, _, policy, rule, evaluation, decision = _cenario()
    alheia = _evidencia(org_id, TypedId.new("evidence"))

    dossier = DossierService().build(
        decision=decision,
        evaluation=evaluation,
        policy=policy,
        rules=[rule],
        evidences=[alheia],
    )

    entradas = dossier.document["evidences"]
    assert len(entradas) == len(decision.evidence_references)
    assert entradas[0]["content_status"] == "NAO_ACOMPANHA"
    assert str(alheia.evidence_id.value) not in [e["id"] for e in entradas]


def test_previously_stored_dossier_keeps_verifying_after_the_change() -> None:
    """A cadeia de integridade não foi afetada.

    Um dossiê gravado sob o documento versão 1 carrega o próprio documento e o
    próprio hash. Mudar o construtor não reescreve nada do que já existe: ele
    continua conferindo contra si mesmo, e continua declarando a versão sob a qual
    foi emitido.
    """
    org_id = OrganizationId.new()
    documento_v1 = {
        "document_version": 1,
        "serialization": "titan-json-v1",
        "subject": {"entity_type": "batch", "id": str(TypedId.new("batch").value)},
        "evidences": [{"entity_type": "evidence", "id": str(TypedId.new("evidence").value)}],
    }
    antigo = Dossier(
        dossier_id=TypedId.new("dossier"),
        organization_id=org_id,
        subject_reference=UniversalReference(
            target_id=TypedId.new("batch"), organization_id=org_id, contract_version=1
        ),
        purpose="CONFORMIDADE_SANITARIA",
        decision_id=TypedId.new("decision"),
        evaluation_id=TypedId.new("evaluation"),
        generated_at=datetime.now(UTC),
        document=documento_v1,
        dossier_hash=compute_dossier_hash(documento_v1),
        document_version=1,
    )

    assert antigo.verify()
    assert antigo.document_version == 1
    # O documento antigo permanece exatamente como foi emitido: nenhum campo novo
    # foi injetado nele retroativamente.
    assert "content_status" not in antigo.document["evidences"][0]


def test_new_documents_declare_the_new_version() -> None:
    _, _, policy, rule, evaluation, decision = _cenario()

    dossier = DossierService().build(
        decision=decision, evaluation=evaluation, policy=policy, rules=[rule]
    )

    assert dossier.document["document_version"] == DOSSIER_DOCUMENT_VERSION
    assert DOSSIER_DOCUMENT_VERSION == 2
