"""Integração PostgreSQL para Dossier autocontido (Passo 7.5).

Valida o exigido pelo plano: recalcular o hash e compreender a decisão a partir
apenas do documento, sem consultar o banco.
"""

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.decision_service import DecisionService
from packages.core_application.dossier_service import DossierService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.policy_service import PolicyService
from packages.core_application.rule_service import RuleService
from packages.core_domain.dossier import compute_dossier_hash
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.rule import ComparisonOperator, RuleCondition, SeverityLevel
from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
from packages.core_infrastructure.persistence.dossier import TransactionalDossierRepository
from packages.core_infrastructure.persistence.evaluation import (
    TransactionalEvaluationRepository,
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


def test_dossier_survives_roundtrip_and_verifies_offline(db_connection: Connection) -> None:
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
    dossier_repo = TransactionalDossierRepository(connection=db_connection)

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

    snapshot = FactSnapshot.create(
        organization_id=org_id_1,
        target_id=subject_id,
        as_of=t0,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": "rejected"},
                observed_at=t0,
                source_reference=UniversalReference(
                    target_id=TypedId.new("evidence"),
                    organization_id=org_id_1,
                    contract_version=1,
                ),
            )
        ],
    )
    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="CONFORMIDADE_SANITARIA"
    )
    TransactionalEvaluationRepository(connection=db_connection).save(evaluation)

    decision = DecisionService().decide(evaluation)
    TransactionalDecisionRepository(connection=db_connection).save(decision)

    dossier = DossierService(repository=dossier_repo).build_and_store(
        decision=decision, evaluation=evaluation, policy=policy, rules=[rule]
    )

    # Round-trip preserva o documento e o hash continua conferindo.
    recarregado = dossier_repo.get_by_id(dossier.dossier_id)
    assert recarregado is not None
    assert recarregado.dossier_hash == dossier.dossier_hash
    assert recarregado.verify()

    # Verificação totalmente offline: exportar o JSON e recalcular sem tocar no banco.
    exportado = json.loads(json.dumps(recarregado.document))
    assert compute_dossier_hash(exportado) == dossier.dossier_hash

    # Compreender a decisão só com o documento exportado.
    condicao = exportado["rules"][0]["conditions"][0]
    fato = next(f for f in exportado["facts"]["facts"] if f["fact_type"] == condicao["fact_type"])
    assert fato["payload"][condicao["payload_key"]] != condicao["expected_value"]
    assert exportado["decision"]["result"] == "rejeitada"
    assert exportado["decision"]["reasons"][0]["corrective_action"]
    assert exportado["policy"]["version"] == policy.version

    # Adulterar qualquer parte do documento quebra a verificação.
    adulterado = json.loads(json.dumps(exportado))
    adulterado["decision"]["result"] = "aprovada"
    assert compute_dossier_hash(adulterado) != dossier.dossier_hash

    # Isolamento: o usuario titan e superusuario e ignora RLS.
    role_name = f"titan_test_rls_{uuid4().hex}"
    quoted_role = db_connection.engine.dialect.identifier_preparer.quote(role_name)
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT SELECT ON core_audit.dossiers TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_2.value)},
    )

    repo_2 = TransactionalDossierRepository(connection=db_connection)
    assert repo_2.get_by_id(dossier.dossier_id) is None
    assert repo_2.list_by_subject(org_id_2, subject_id) == []

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
