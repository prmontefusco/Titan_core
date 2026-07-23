"""Integração PostgreSQL para o ciclo completo de NonConformity (Passo 7.3).

Percorre a validação do plano: abrir por falha de regra, corrigir, reavaliar e
encerrar, navegando até os fatos e evidências que justificam o caso.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.nonconformity_service import NonConformityService
from packages.core_application.policy_service import PolicyService
from packages.core_application.rule_service import RuleService
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.nonconformity import NonConformityOrigin, NonConformityStatus
from packages.core_domain.rule import ComparisonOperator, RuleCondition, SeverityLevel
from packages.core_infrastructure.persistence.evaluation import (
    TransactionalEvaluationRepository,
)
from packages.core_infrastructure.persistence.nonconformity import (
    TransactionalNonConformityRepository,
)
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


def _snapshot(
    org_id: OrganizationId, subject_id: TypedId, as_of: datetime, resultado: str
) -> FactSnapshot:
    return FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=as_of,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": resultado},
                observed_at=as_of,
            )
        ],
    )


def test_open_correct_reevaluate_and_close(db_connection: Connection) -> None:
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
    nc_repo = TransactionalNonConformityRepository(connection=db_connection)
    nc_service = NonConformityService(repository=nc_repo)

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

    evaluator = PolicyEvaluationService(engine=RuleEvaluationEngine())

    # 1. Avaliação reprova e abre a não conformidade.
    reprovada = evaluator.evaluate_policy(
        policy=policy,
        rules=[rule],
        snapshot=_snapshot(org_id_1, subject_id, t0, "rejected"),
        purpose="CONFORMIDADE_SANITARIA",
    )
    evaluation_repo.save(reprovada)

    abertas = nc_service.open_from_evaluation(reprovada)
    assert len(abertas) == 1
    nc = abertas[0]
    assert nc.origin is NonConformityOrigin.REGRA_NAO_ATENDIDA
    assert nc.severity is SeverityLevel.BLOCKING
    assert nc.corrective_action == "Reemitir o atestado sanitário."

    # A origem aponta para a Evaluation: é o fio que leva aos fatos e evidências.
    assert nc.origin_reference is not None
    assert nc.origin_reference.target_id == reprovada.evaluation_id
    origem = evaluation_repo.get_by_id(nc.origin_reference.target_id)
    assert origem is not None
    assert origem.fact_snapshot.facts[0].payload["result"] == "rejected"

    # 2. Classificar, atribuir e corrigir.
    nc = nc_service.classify(nc.nonconformity_id, t0 + timedelta(hours=1))
    nc = nc_service.assign(
        nc.nonconformity_id,
        responsible_reference=UniversalReference(
            target_id=TypedId.new("user"), organization_id=org_id_1, contract_version=1
        ),
        due_date=t0 + timedelta(days=7),
        occurred_at=t0 + timedelta(hours=2),
    )
    nc = nc_service.start_correction(nc.nonconformity_id, t0 + timedelta(hours=3))
    nc = nc_service.submit_for_reevaluation(
        nc.nonconformity_id,
        correction_evidence_references=[
            UniversalReference(
                target_id=TypedId.new("evidence"),
                organization_id=org_id_1,
                contract_version=1,
            )
        ],
        occurred_at=t0 + timedelta(days=1),
    )
    assert nc.status is NonConformityStatus.PRONTA_PARA_REAVALIACAO

    # 3. Reavaliação que ainda reprova devolve o caso à correção.
    ainda_reprovada = evaluator.evaluate_policy(
        policy=policy,
        rules=[rule],
        snapshot=_snapshot(org_id_1, subject_id, t0 + timedelta(days=1), "rejected"),
        purpose="REAVALIACAO",
    )
    evaluation_repo.save(ainda_reprovada)
    nc = nc_service.close_with_reevaluation(
        nc.nonconformity_id, ainda_reprovada, t0 + timedelta(days=1, hours=1)
    )
    assert nc.status is NonConformityStatus.EM_CORRECAO
    assert not nc.is_closed

    # 4. Nova correção e reavaliação aprovada encerram o caso.
    nc = nc_service.submit_for_reevaluation(
        nc.nonconformity_id,
        correction_evidence_references=[
            UniversalReference(
                target_id=TypedId.new("evidence"),
                organization_id=org_id_1,
                contract_version=1,
            )
        ],
        occurred_at=t0 + timedelta(days=2),
    )
    aprovada = evaluator.evaluate_policy(
        policy=policy,
        rules=[rule],
        snapshot=_snapshot(org_id_1, subject_id, t0 + timedelta(days=2), "approved"),
        purpose="REAVALIACAO",
    )
    evaluation_repo.save(aprovada)
    nc = nc_service.close_with_reevaluation(
        nc.nonconformity_id, aprovada, t0 + timedelta(days=2, hours=1)
    )

    assert nc.is_closed
    assert nc.reevaluation_id == aprovada.evaluation_id

    # 5. O histórico inteiro sobreviveu, incluindo a reavaliação rejeitada.
    recarregada = nc_repo.get_by_id(nc.nonconformity_id)
    assert recarregada is not None
    percurso = [t.to_status for t in recarregada.history()]
    assert percurso.count(NonConformityStatus.EM_CORRECAO) == 2
    assert percurso.count(NonConformityStatus.PRONTA_PARA_REAVALIACAO) == 2
    assert percurso[-1] is NonConformityStatus.ENCERRADA
    assert len(recarregada.correction_evidence_references) == 2

    # Encerrada some da lista de pendências, mas continua consultável.
    assert nc_repo.list_open(org_id_1) == []
    assert len(nc_repo.list_by_subject(org_id_1, subject_id)) == 1

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
    db_connection.execute(text(f"GRANT SELECT ON core_audit.nonconformities TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_2.value)},
    )

    repo_2 = TransactionalNonConformityRepository(connection=db_connection)
    assert repo_2.get_by_id(nc.nonconformity_id) is None
    assert repo_2.list_by_subject(org_id_2, subject_id) == []

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))


def test_only_failing_rule_results_open_nonconformities(db_connection: Connection) -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    t0 = datetime.now(UTC)

    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations
            (organization_id, record_owner_organization_id)
            VALUES (:id, :id)
            """
        ),
        {"id": org_id.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id.value)},
    )

    policy_service = PolicyService(repository=TransactionalPolicyRepository(db_connection))
    rule_service = RuleService(repository=TransactionalRuleRepository(db_connection))
    nc_repo = TransactionalNonConformityRepository(connection=db_connection)
    nc_service = NonConformityService(repository=nc_repo)

    policy = policy_service.publish_policy(
        policy_service.create_draft(
            organization_id=org_id, code="pol-ok", name="Política"
        ).policy_id
    )
    rule = rule_service.create_rule(
        policy_id=policy.policy_id,
        organization_id=org_id,
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
    )

    aprovada = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy,
        rules=[rule],
        snapshot=_snapshot(org_id, subject_id, t0, "approved"),
        purpose="CONFORMIDADE",
    )

    # Conformidade não gera pendência: tratar o que não falhou viraria ruído.
    assert nc_service.open_from_evaluation(aprovada) == []
    assert nc_repo.list_open(org_id) == []
