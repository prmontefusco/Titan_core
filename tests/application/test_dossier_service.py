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
from packages.core_domain.dossier import compute_dossier_hash
from packages.core_domain.evaluation import Evaluation, EvaluationOutcome
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
