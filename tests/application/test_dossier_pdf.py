"""Testes para representação PDF verificável do Dossier (Passo 7.8)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.core_application.dossier_service import DossierService
from packages.core_domain.crypto import KeyIdentifier
from packages.core_domain.decision import (
    Decision,
    DecisionReason,
    DecisionReasonCode,
    DecisionResult,
    compute_decision_hash,
)
from packages.core_domain.dossier import Dossier
from packages.core_domain.evaluation import (
    Evaluation,
    EvaluationOutcome,
    RuleResult,
    RuleResultStatus,
    compute_evaluation_hash,
)
from packages.core_domain.facts import FactSnapshot
from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.rule import Rule, SeverityLevel
from packages.core_infrastructure.crypto import SoftwareKeyProvider, SoftwareSigningProvider
from packages.core_infrastructure.pdf import SoftwareDossierPdfAdapter
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@pytest.fixture
def sample_dossier() -> Dossier:
    org_id = OrganizationId(uuid4())
    subject_id = TypedId(entity_type="lote", value=uuid4())
    policy_id = TypedId(entity_type="policy", value=uuid4())
    eval_id = TypedId(entity_type="evaluation", value=uuid4())
    rule_id = TypedId(entity_type="rule", value=uuid4())

    policy = Policy(
        policy_id=policy_id,
        organization_id=org_id,
        code="POL_VACINACAO_2026",
        name="Política de Vacinação Pecuária",
        description="Verifica cobertura vacinal contra aftosa",
        version=1,
        status=PolicyStatus.PUBLISHED,
    )

    rule = Rule(
        rule_id=rule_id,
        policy_id=policy_id,
        organization_id=org_id,
        code="REGRA_AFTOSA_OBRIGATORIA",
        name="Vacinação Aftosa",
        description="Exige comprovante de vacina nos últimos 180 dias",
        version=1,
        severity=SeverityLevel.BLOCKING,
        normative_source="Instrução Normativa MAPA nº 45",
        required_evidence_types=("CERTIDAO_VACINACAO",),
        conditions=(),
    )

    fact_snapshot = FactSnapshot(
        organization_id=org_id,
        target_id=subject_id,
        as_of=datetime.now(UTC),
        facts=(),
        snapshot_hash="a" * 64,
    )

    rule_result = RuleResult(
        result_id=TypedId.new("rule_result"),
        rule_id=rule_id,
        rule_version=1,
        organization_id=org_id,
        subject_id=subject_id,
        status=RuleResultStatus.ATENDIDA,
        severity=SeverityLevel.BLOCKING,
        reason="Comprovante de vacinação válido fornecido.",
        corrective_action="Nenhuma ação necessária.",
        missing_evidence_types=(),
        evaluated_at=datetime.now(UTC),
        snapshot_hash="a" * 64,
        inputs_hash="b" * 64,
        rule_code=rule.code,
    )

    eval_hash = compute_evaluation_hash(
        policy_id=policy_id,
        policy_version=1,
        subject_id=subject_id,
        purpose="AUDITORIA_EXPORTACAO",
        snapshot_hash=fact_snapshot.snapshot_hash,
        rule_results=(rule_result,),
        outcome=EvaluationOutcome.CONDICOES_SATISFEITAS,
        engine_version=1,
    )

    evaluation = Evaluation(
        evaluation_id=eval_id,
        organization_id=org_id,
        subject_id=subject_id,
        purpose="AUDITORIA_EXPORTACAO",
        policy_id=policy_id,
        policy_version=1,
        fact_snapshot=fact_snapshot,
        rule_results=(rule_result,),
        outcome=EvaluationOutcome.CONDICOES_SATISFEITAS,
        evaluated_at=datetime.now(UTC),
        engine_version=1,
        rule_versions=((rule.code, 1),),
        evaluation_hash=eval_hash,
    )

    reason = DecisionReason(
        code=DecisionReasonCode.REGRA_ATENDIDA,
        message="Todas as condições regulatórias foram atendidas.",
    )

    dec_hash = compute_decision_hash(
        evaluation_hash=eval_hash,
        policy_id=policy_id,
        policy_version=1,
        subject_id=subject_id,
        purpose="AUDITORIA_EXPORTACAO",
        result=DecisionResult.APROVADA,
        reasons=(reason,),
        engine_version=1,
    )

    decision = Decision(
        decision_id=TypedId(entity_type="decision", value=uuid4()),
        organization_id=org_id,
        subject_id=subject_id,
        purpose="AUDITORIA_EXPORTACAO",
        policy_id=policy_id,
        policy_version=1,
        evaluation_id=eval_id,
        evaluation_hash=eval_hash,
        snapshot_hash=fact_snapshot.snapshot_hash,
        result=DecisionResult.APROVADA,
        reasons=(reason,),
        issued_at=datetime.now(UTC),
        engine_version=1,
        evidence_references=(),
        affected_subjects=(
            UniversalReference(target_id=subject_id, organization_id=org_id, contract_version=1),
        ),
        decision_hash=dec_hash,
    )

    service = DossierService()
    return service.build(
        decision=decision,
        evaluation=evaluation,
        policy=policy,
        rules=(rule,),
    )


def test_dossier_pdf_generation_unssigned(sample_dossier: Dossier) -> None:
    adapter = SoftwareDossierPdfAdapter()
    service = DossierService(pdf_port=adapter)

    pdf_rep = service.generate_pdf(sample_dossier)

    assert pdf_rep.dossier_id == sample_dossier.dossier_id
    assert pdf_rep.organization_id == sample_dossier.organization_id
    assert pdf_rep.pdf_bytes.startswith(b"%PDF")
    assert pdf_rep.verify_integrity() is True
    assert pdf_rep.signature is None
    assert "titan://verify" in pdf_rep.verification_qr_payload


def test_dossier_pdf_generation_signed(sample_dossier: Dossier) -> None:
    adapter = SoftwareDossierPdfAdapter()
    service = DossierService(pdf_port=adapter)

    key_provider = SoftwareKeyProvider()
    signing_provider = SoftwareSigningProvider(key_provider=key_provider)
    key_id = KeyIdentifier(key_id=TypedId.new("key"), purpose="INSTITUTIONAL_SEAL")

    key_provider.register_key(key_id, b"secret_test_key_for_dossier_pdf_bytes_32")

    pdf_rep = service.generate_pdf(
        sample_dossier,
        signing_provider=signing_provider,
        key_id=key_id,
    )

    assert pdf_rep.pdf_bytes.startswith(b"%PDF")
    assert pdf_rep.verify_integrity() is True
    assert pdf_rep.signature is not None
    assert pdf_rep.signature.key_identifier == key_id

    assert pdf_rep.to_dict()["is_signed"] is True
