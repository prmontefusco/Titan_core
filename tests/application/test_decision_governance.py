"""Testes para Incoerência de Evidências (ADR-0035) e Governança Humana (ADR-0016)."""

from datetime import UTC, datetime
from uuid import uuid4

from packages.core_application.decision_governance_service import DecisionGovernanceService
from packages.core_application.evaluation_service import (
    EvidenceInconsistencyDetector,
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_domain.decision import (
    Decision,
    DecisionReason,
    DecisionReasonCode,
    DecisionResult,
    compute_decision_hash,
)
from packages.core_domain.decision_governance import (
    DecisionAuthorityProfile,
    GovernanceStatus,
)
from packages.core_domain.evaluation import (
    Evaluation,
    EvaluationOutcome,
)
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.rule import Rule, SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def test_evidence_inconsistency_detector() -> None:
    org_id = OrganizationId(uuid4())
    subject_id = TypedId(entity_type="lote", value=uuid4())
    now = datetime.now(UTC)

    fact1 = Fact.create(
        fact_type="vaccination.status",
        payload={"dose": 2, "status": "COMPLETO"},
        observed_at=now,
    )
    fact2 = Fact.create(
        fact_type="vaccination.status",
        payload={"dose": 1, "status": "INCOMPLETO"},  # Conflito em dose e status
        observed_at=now,
    )

    snapshot = FactSnapshot(
        organization_id=org_id,
        target_id=subject_id,
        as_of=now,
        facts=(fact1, fact2),
        snapshot_hash="a" * 64,
    )

    detector = EvidenceInconsistencyDetector()
    conflicts = detector.detect(snapshot)

    assert len(conflicts) > 0
    assert "Conflito em 'vaccination.status.dose'" in conflicts[0] or "status" in conflicts[0]


def test_policy_evaluation_produces_evidencia_conflitante() -> None:
    org_id = OrganizationId(uuid4())
    subject_id = TypedId(entity_type="lote", value=uuid4())
    policy_id = TypedId(entity_type="policy", value=uuid4())
    rule_id = TypedId(entity_type="rule", value=uuid4())
    now = datetime.now(UTC)

    fact1 = Fact.create(
        fact_type="certidao.sanitaria",
        payload={"status": "VALIDA"},
        observed_at=now,
    )
    fact2 = Fact.create(
        fact_type="certidao.sanitaria",
        payload={"status": "INVALIDA"},
        observed_at=now,
    )
    snapshot = FactSnapshot(
        organization_id=org_id,
        target_id=subject_id,
        as_of=now,
        facts=(fact1, fact2),
        snapshot_hash="b" * 64,
    )

    policy = Policy(
        policy_id=policy_id,
        organization_id=org_id,
        code="POL_CONFLITO",
        name="Pol de Teste",
        description="Teste",
        version=1,
        status=PolicyStatus.PUBLISHED,
    )
    rule = Rule(
        rule_id=rule_id,
        policy_id=policy_id,
        organization_id=org_id,
        code="REGRA_TESTE",
        name="Regra Teste",
        description="Descrição",
        version=1,
        severity=SeverityLevel.INFO,
        normative_source="Fonte",
        required_evidence_types=(),
        conditions=(),
    )

    engine = RuleEvaluationEngine()
    service = PolicyEvaluationService(engine=engine)

    evaluation = service.evaluate_policy(
        policy=policy,
        rules=(rule,),
        snapshot=snapshot,
        purpose="AUDITORIA",
    )

    assert evaluation.outcome == EvaluationOutcome.EVIDENCIA_CONFLITANTE


def test_decision_governance_proposal_override_and_contestation() -> None:
    org_id = OrganizationId(uuid4())
    subject_id = TypedId(entity_type="lote", value=uuid4())
    policy_id = TypedId(entity_type="policy", value=uuid4())
    eval_id = TypedId(entity_type="evaluation", value=uuid4())
    dec_id = TypedId(entity_type="decision", value=uuid4())
    now = datetime.now(UTC)

    snapshot = FactSnapshot(
        organization_id=org_id,
        target_id=subject_id,
        as_of=now,
        facts=(),
        snapshot_hash="c" * 64,
    )

    evaluation = Evaluation(
        evaluation_id=eval_id,
        organization_id=org_id,
        subject_id=subject_id,
        purpose="AUDITORIA",
        policy_id=policy_id,
        policy_version=1,
        fact_snapshot=snapshot,
        rule_results=(),
        outcome=EvaluationOutcome.REVISAO_HUMANA_NECESSARIA,
        evaluated_at=now,
        engine_version=1,
        rule_versions=(),
        evaluation_hash="d" * 64,
    )

    reason = DecisionReason(
        code=DecisionReasonCode.REGRA_INDETERMINADA,
        message="Aguardando validação humana de fiscalização.",
    )
    dec_hash = compute_decision_hash(
        evaluation_hash=evaluation.evaluation_hash,
        policy_id=policy_id,
        policy_version=1,
        subject_id=subject_id,
        purpose="AUDITORIA",
        result=DecisionResult.INDETERMINADA,
        reasons=(reason,),
        engine_version=1,
    )
    original_decision = Decision(
        decision_id=dec_id,
        organization_id=org_id,
        subject_id=subject_id,
        purpose="AUDITORIA",
        policy_id=policy_id,
        policy_version=1,
        evaluation_id=eval_id,
        evaluation_hash=evaluation.evaluation_hash,
        snapshot_hash=snapshot.snapshot_hash,
        result=DecisionResult.INDETERMINADA,
        reasons=(reason,),
        issued_at=now,
        engine_version=1,
        evidence_references=(),
        affected_subjects=(),
        decision_hash=dec_hash,
    )

    service = DecisionGovernanceService()

    # 1. Proposta
    proposal = service.create_proposal(
        evaluation=evaluation,
        proposed_result=DecisionResult.APROVADA_COM_RESTRICOES,
        created_at=now,
    )
    assert proposal.status == GovernanceStatus.PENDENTE
    assert proposal.proposed_result == DecisionResult.APROVADA_COM_RESTRICOES

    # 2. Override
    authority = DecisionAuthorityProfile(
        authority_id=TypedId.new("authority_profile"),
        organization_id=org_id,
        principal_reference=UniversalReference(
            target_id=TypedId.new("user"),
            organization_id=org_id,
            contract_version=1,
        ),
        role_name="FISCAL_AUDITOR_SENIOR",
    )

    override = service.apply_override(
        original_decision=original_decision,
        authority_profile=authority,
        new_result=DecisionResult.APROVADA_COM_RESTRICOES,
        mandatory_reason="Aprovado manualmente mediante análise de documento físico complementar.",
        applied_at=now,
    )
    assert override.original_decision_id == dec_id
    assert override.new_result == DecisionResult.APROVADA_COM_RESTRICOES
    assert "documento físico" in override.mandatory_reason

    # 3. Contestação
    contested_by = UniversalReference(
        target_id=TypedId.new("user"),
        organization_id=org_id,
        contract_version=1,
    )
    contestation = service.file_contestation(
        decision=original_decision,
        contested_by=contested_by,
        grounds_description="Solicito reavaliação devido a nova certidão emitida no mesmo dia.",
        filed_at=now,
    )
    assert contestation.decision_id == dec_id
    assert contestation.status == GovernanceStatus.PENDENTE
