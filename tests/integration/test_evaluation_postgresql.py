"""Testes de integração PostgreSQL com RLS para Evaluations preservadas (Passo 6.5)."""

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
from packages.core_application.policy_service import PolicyService
from packages.core_application.rule_service import RuleService
from packages.core_domain.evaluation import EvaluationOutcome
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.normative import (
    NormativeBasisSnapshot,
    NormativeReferenceSnapshot,
    NormativeSourceClassification,
)
from packages.core_domain.rule import ComparisonOperator, RuleCondition, SeverityLevel
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.shared_kernel import OrganizationId, TypedId


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


def test_evaluation_is_preserved_and_isolated_by_organization(db_connection: Connection) -> None:
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

    policy = policy_service.publish_policy(
        policy_service.create_draft(
            organization_id=org_id_1,
            code="pol-sanitaria",
            name="Política Sanitária",
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
    )

    snapshot = FactSnapshot.create(
        organization_id=org_id_1,
        target_id=subject_id,
        as_of=t0,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": "approved", "emitido_por": "vet-42"},
                observed_at=t0,
            )
        ],
    )

    service = PolicyEvaluationService(engine=RuleEvaluationEngine())
    normative_snapshot = NormativeBasisSnapshot(
        schema_version=1,
        normative_basis_id=TypedId.new("normative_basis"),
        normative_basis_code="TEST-BASIS-A",
        normative_basis_version=1,
        policy_id=policy.policy_id,
        policy_code=policy.code,
        policy_version=policy.version,
        rule_versions=((rule.code, rule.version),),
        purpose="CONFORMIDADE_SANITARIA",
        jurisdiction="TEST-JURISDICTION",
        intended_use="INTERNAL_TEST_ONLY",
        reference_time=t0,
        knowledge_cutoff=t0,
        approved_by="actor:test-reviewer",
        approval_authority="INTERNAL_TEST_AUTHORITY",
        approved_at=t0,
        references=(
            NormativeReferenceSnapshot(
                instrument_code="TEST-INSTRUMENT-A",
                instrument_version="1",
                provision="section-1",
                content_digest="a" * 64,
                digest_algorithm="sha256",
                source_classification=NormativeSourceClassification.INTERNAL_TEST,
            ),
        ),
        limitations=("not-an-official-market-decision",),
    )
    evaluation = service.evaluate_policy(
        policy=policy,
        rules=[rule],
        snapshot=snapshot,
        purpose="CONFORMIDADE_SANITARIA",
        normative_basis_snapshot=normative_snapshot,
    )
    assert evaluation.outcome == EvaluationOutcome.CONDICOES_SATISFEITAS
    evaluation_repo.save(evaluation)

    # O snapshot completo sobrevive ao round-trip, não apenas o hash.
    reloaded = evaluation_repo.get_by_id(evaluation.evaluation_id)
    assert reloaded is not None
    assert reloaded.evaluation_hash == evaluation.evaluation_hash
    assert reloaded.is_reproducible()
    assert reloaded.fact_snapshot.snapshot_hash == snapshot.snapshot_hash
    assert len(reloaded.fact_snapshot.facts) == 1
    assert reloaded.fact_snapshot.facts[0].payload["emitido_por"] == "vet-42"
    assert reloaded.rule_results[0].reason == evaluation.rule_results[0].reason
    assert reloaded.rule_versions == (("rule-atestado", 1),)
    assert reloaded.normative_basis_snapshot == normative_snapshot
    assert reloaded.recompute_context_hash() == evaluation.context_hash

    # Uma avaliação posterior sobre fatos piores não altera a avaliação histórica.
    t1 = t0 + timedelta(days=30)
    snapshot_t1 = FactSnapshot.create(
        organization_id=org_id_1,
        target_id=subject_id,
        as_of=t1,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": "rejected"},
                observed_at=t1,
            )
        ],
    )
    legacy_evaluation = service.evaluate_policy(
        policy=policy,
        rules=[rule],
        snapshot=snapshot_t1,
        purpose="CONFORMIDADE_SANITARIA",
    )
    evaluation_repo.save(legacy_evaluation)
    legacy_reloaded = evaluation_repo.get_by_id(legacy_evaluation.evaluation_id)
    assert legacy_reloaded is not None
    assert legacy_reloaded.normative_basis_snapshot is None
    assert legacy_reloaded.normative_limitations == ("NORMATIVE_BASIS_SNAPSHOT_LEGACY_ABSENT",)

    historico = evaluation_repo.list_by_subject(org_id_1, subject_id)
    assert len(historico) == 2
    assert {e.outcome for e in historico} == {
        EvaluationOutcome.CONDICOES_SATISFEITAS,
        EvaluationOutcome.CONDICOES_NAO_SATISFEITAS,
    }
    antiga = evaluation_repo.get_by_id(evaluation.evaluation_id)
    assert antiga is not None
    assert antiga.outcome == EvaluationOutcome.CONDICOES_SATISFEITAS
    assert antiga.is_reproducible()

    # Isolamento de tenant: o usuario titan e superusuario e ignora RLS, entao a
    # checagem exige um role sem BYPASSRLS.
    role_name = f"titan_test_rls_{uuid4().hex}"
    quoted_role = db_connection.engine.dialect.identifier_preparer.quote(role_name)
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT SELECT ON core_audit.evaluations TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_2.value)},
    )

    repo_2 = TransactionalEvaluationRepository(connection=db_connection)
    assert repo_2.get_by_id(evaluation.evaluation_id) is None
    assert repo_2.list_by_subject(org_id_2, subject_id) == []

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
