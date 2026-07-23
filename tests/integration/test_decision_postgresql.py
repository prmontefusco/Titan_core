"""Testes de integração PostgreSQL com RLS para Decisions explicáveis (Passo 6.6)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.exc import IntegrityError

from packages.core_application.decision_service import DecisionService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.policy_service import PolicyService
from packages.core_application.rule_service import RuleService
from packages.core_domain.decision import DecisionReasonCode, DecisionResult
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.rule import ComparisonOperator, RuleCondition, SeverityLevel
from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        with conn.begin():
            yield conn


def test_decision_is_preserved_explainable_and_isolated(db_connection: Connection) -> None:
    org_id_1 = OrganizationId.new()
    org_id_2 = OrganizationId.new()
    subject_id = TypedId.new("batch")
    t0 = datetime.now(UTC)

    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations
            (organization_id, record_owner_organization_id)
            VALUES (:id1, :id1), (:id2, :id2)
            """
        ),
        {"id1": org_id_1.value, "id2": org_id_2.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_1.value)},
    )

    policy_service = PolicyService(repository=TransactionalPolicyRepository(db_connection))
    rule_service = RuleService(repository=TransactionalRuleRepository(db_connection))
    evaluation_repo = TransactionalEvaluationRepository(connection=db_connection)
    decision_repo = TransactionalDecisionRepository(connection=db_connection)

    policy = policy_service.publish_policy(
        policy_service.create_draft(
            organization_id=org_id_1, code="pol-sanitaria", name="Política Sanitária"
        ).policy_id
    )
    rule = rule_service.create_rule(
        policy_id=policy.policy_id,
        organization_id=org_id_1,
        code="rule-atestado",
        name="Atestado aprovado",
        severity=SeverityLevel.BLOCKING,
        conditions=(
            RuleCondition(
                fact_type="sanitary.attestation",
                payload_key="result",
                operator=ComparisonOperator.EQUALS,
                expected_value="approved",
            ),
        ),
        corrective_action="Reemitir o atestado sanitário.",
    )

    evidence_ref = UniversalReference(
        target_id=TypedId.new("evidence"), organization_id=org_id_1, contract_version=1
    )
    snapshot = FactSnapshot.create(
        organization_id=org_id_1,
        target_id=subject_id,
        as_of=t0,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": "rejected"},
                observed_at=t0,
                source_reference=evidence_ref,
            )
        ],
    )

    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="CONFORMIDADE_SANITARIA"
    )
    evaluation_repo.save(evaluation)

    decision = DecisionService().decide(evaluation)
    assert decision.result == DecisionResult.REJEITADA
    decision_repo.save(decision)

    reloaded = decision_repo.get_by_id(decision.decision_id)
    assert reloaded is not None
    assert reloaded.decision_hash == decision.decision_hash
    assert reloaded.is_reproducible()
    assert reloaded.result == DecisionResult.REJEITADA
    assert reloaded.corrective_actions == ("Reemitir o atestado sanitário.",)
    assert reloaded.evidence_references == (evidence_ref,)
    razoes = reloaded.reasons_by_code(DecisionReasonCode.REGRA_NAO_ATENDIDA)
    assert razoes[0].rule_code == "rule-atestado"
    assert razoes[0].severity == SeverityLevel.BLOCKING

    # A decisão é reconstruível a partir da Evaluation preservada no banco.
    evaluation_do_banco = evaluation_repo.get_by_id(evaluation.evaluation_id)
    assert evaluation_do_banco is not None
    reconstruida = DecisionService().decide(evaluation_do_banco)
    assert reconstruida.decision_hash == decision.decision_hash
    assert reconstruida.result == decision.result

    # Nem por SQL direto se grava conclusão sem justificativa.
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO core_audit.decisions (
                        decision_id, record_owner_organization_id, evaluation_id,
                        evaluation_hash, policy_id, policy_version, subject_entity_type,
                        subject_id, purpose, result, engine_version, issued_at,
                        snapshot_hash, decision_hash, reasons
                    ) VALUES (
                        :did, :org, :eid, 'h', :pid, 1, 'batch', :sid, 'X',
                        'aprovada', 1, now(), 'h', 'h', '[]'::jsonb
                    )
                    """
                ),
                {
                    "did": uuid4(),
                    "org": org_id_1.value,
                    "eid": evaluation.evaluation_id.value,
                    "pid": policy.policy_id.value,
                    "sid": subject_id.value,
                },
            )

    # Isolamento de tenant: o usuario titan e superusuario e ignora RLS.
    role_name = f"titan_test_rls_{uuid4().hex}"
    quoted_role = db_connection.engine.dialect.identifier_preparer.quote(role_name)
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT SELECT ON core_audit.decisions TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_2.value)},
    )

    repo_2 = TransactionalDecisionRepository(connection=db_connection)
    assert repo_2.get_by_id(decision.decision_id) is None
    assert repo_2.list_by_subject(org_id_2, subject_id) == []

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
