"""Integracao PostgreSQL para persistencia da governanca de decisao (ADR-0054)."""

import os
from datetime import UTC, datetime

from sqlalchemy import create_engine, text

from packages.core_application.decision_governance_service import DecisionGovernanceService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.decision_governance import DecisionAuthorityProfile, ReviewConclusion
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.policy import Policy
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.core_infrastructure.persistence.decision_governance import (
    TransactionalDecisionAuthorityProfileRepository,
    TransactionalDecisionGovernanceRepository,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _db_url() -> str:
    return os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )


def _authority(org_id: OrganizationId, purpose: str) -> DecisionAuthorityProfile:
    return DecisionAuthorityProfile(
        authority_id=TypedId.new("authority_profile"),
        organization_id=org_id,
        principal_reference=UniversalReference(
            target_id=TypedId.new("user"),
            organization_id=org_id,
            contract_version=1,
        ),
        role_name="AUDITOR_SENIOR",
        purpose=purpose,
        emission_method=DecisionEmissionMethod.HUMAN,
        approvals_required=0,
    )


def _evaluation(org_id: OrganizationId) -> tuple[Policy, Rule, object]:
    instant = datetime.now(UTC)
    policy = Policy.create_draft(
        organization_id=org_id,
        code="pol-governanca",
        name="Politica de Governanca",
    ).publish()
    rule = Rule.create(
        policy_id=policy.policy_id,
        organization_id=org_id,
        code="rule-revisao",
        name="Regra com revisao",
        severity=SeverityLevel.BLOCKING,
        conditions=(
            RuleCondition(
                fact_type="sanitary.attestation",
                payload_key="result",
                operator=ComparisonOperator.EQUALS,
                expected_value="approved",
            ),
        ),
        corrective_action="Revisar documentacao.",
    )
    snapshot = FactSnapshot.create(
        organization_id=org_id,
        target_id=TypedId.new("batch"),
        as_of=instant,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": "rejected"},
                observed_at=instant,
            )
        ],
    )
    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy,
        rules=[rule],
        snapshot=snapshot,
        purpose="CONFORMIDADE_SANITARIA",
    )
    return policy, rule, evaluation


def test_governance_roundtrip_postgresql() -> None:
    engine = create_engine(_db_url(), pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            with conn.begin():
                org_id = OrganizationId.new()
                conn.execute(
                    text(
                        """
                        INSERT INTO core_identity.organizations
                        (organization_id, record_owner_organization_id)
                        VALUES (:org_id, :org_id)
                        """
                    ),
                    {"org_id": org_id.value},
                )
                conn.execute(
                    text("SELECT set_config('titan.organization_id', :org_id, true)"),
                    {"org_id": str(org_id.value)},
                )

                _, _, evaluation = _evaluation(org_id)
                authority = _authority(org_id, evaluation.purpose)
                TransactionalDecisionAuthorityProfileRepository(conn).save(authority)

                repo = TransactionalDecisionGovernanceRepository(conn)
                service = DecisionGovernanceService(repository=repo)
                proposal = service.create_proposal(evaluation=evaluation)
                review = service.record_review(
                    proposal=proposal,
                    reviewer_reference=UniversalReference(
                        target_id=TypedId.new("user"),
                        organization_id=org_id,
                        contract_version=1,
                    ),
                    reviewer_authority=authority,
                    conclusion=ReviewConclusion.APROVA,
                    reasoning="Revisao presencial concluida.",
                )
                contestation = service.file_contestation(
                    decision=service.emit_after_approval(
                        evaluation=evaluation,
                        proposal=proposal,
                        review=review,
                        authority_profile=authority,
                    ),
                    contested_by=UniversalReference(
                        target_id=TypedId.new("user"),
                        organization_id=org_id,
                        contract_version=1,
                    ),
                    grounds_description="Contestacao protocolada.",
                )

                recarregada = repo.get_proposal(proposal.proposal_id)
                revisao_recarregada = repo.get_review(review.review_id)
                revisoes_da_proposta = repo.list_reviews_by_proposal(proposal.proposal_id)
                contestacao_recarregada = repo.get_contestation(contestation.contestation_id)

                assert recarregada is not None
                assert recarregada.evaluation_hash == proposal.evaluation_hash
                assert revisao_recarregada is not None
                assert revisao_recarregada.reasoning == review.reasoning
                assert len(revisoes_da_proposta) == 1
                assert revisoes_da_proposta[0].review_id == review.review_id
                assert contestacao_recarregada is not None
                assert contestacao_recarregada.grounds_description == (
                    contestation.grounds_description
                )
    finally:
        engine.dispose()
