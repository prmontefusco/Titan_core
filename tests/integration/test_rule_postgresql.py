"""Testes de integração PostgreSQL com RLS para Gestão de Regras Versionadas (Passo 6.2)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.policy_service import PolicyService
from packages.core_application.rule_service import RuleService
from packages.core_domain.rule import ComparisonOperator, RuleCondition, SeverityLevel
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.shared_kernel import OrganizationId


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


def test_rule_persistence_versioning_and_rls(db_connection: Connection) -> None:
    org_id_1 = OrganizationId.new()
    org_id_2 = OrganizationId.new()

    # 1. Cadastra as organizacoes
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES
                (:id1, :id1),
                (:id2, :id2)
            """
        ),
        {
            "id1": org_id_1.value,
            "id2": org_id_2.value,
        },
    )

    # Contexto RLS para org_1
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_1.value)},
    )

    policy_repo = TransactionalPolicyRepository(connection=db_connection)
    policy_service = PolicyService(repository=policy_repo)

    rule_repo = TransactionalRuleRepository(connection=db_connection)
    rule_service = RuleService(repository=rule_repo)

    # 2. Cria politica base
    policy = policy_service.create_draft(
        organization_id=org_id_1,
        code="pol-sanitaria-lotes",
        name="Política de Sanidade dos Lotes",
    )

    # 3. Cria Regra v1 para a política
    t0 = datetime.now(UTC) - timedelta(hours=1)
    t1 = t0 + timedelta(days=365)
    r1 = rule_service.create_rule(
        policy_id=policy.policy_id,
        organization_id=org_id_1,
        code="rule-exame-brucelose",
        name="Exame de Brucelose Obrigatório",
        description="Atestado de imunização contra Brucelose",
        severity=SeverityLevel.BLOCKING,
        required_evidence_types=("laudo_laboratorial",),
        conditions=(
            RuleCondition(
                fact_type="laudo_laboratorial",
                payload_key="resultado",
                operator=ComparisonOperator.IN,
                expected_value=["negativo", "nao_reagente"],
                description="Laudo deve ser negativo para Brucelose",
            ),
        ),
        valid_from=t0,
        valid_to=t1,
    )
    assert r1.version == 1

    # As condições declarativas sobrevivem ao round-trip no PostgreSQL
    reloaded = rule_repo.get_by_id(r1.rule_id)
    assert reloaded is not None
    assert reloaded.conditions == r1.conditions
    assert reloaded.conditions[0].operator is ComparisonOperator.IN
    assert reloaded.conditions[0].expected_value == ("negativo", "nao_reagente")

    # Tentar criar duplicada v1 lança ValueError
    with pytest.raises(ValueError, match="Já existe uma regra com o código"):
        rule_service.create_rule(
            policy_id=policy.policy_id,
            organization_id=org_id_1,
            code="rule-exame-brucelose",
            name="Duplicada",
        )

    # Busca regras ativas na data t0
    active_rules_t0 = rule_service.list_active_rules_for_policy_at(org_id_1, policy.policy_id, t0)
    assert len(active_rules_t0) == 1
    assert active_rules_t0[0].code == "rule-exame-brucelose"

    # 4. Versionamento de regra (v2)
    r2 = rule_service.create_next_version(
        r1.rule_id, name="Exame de Brucelose Obrigatório v2", severity=SeverityLevel.CRITICAL
    )
    assert r2.version == 2

    # 5. Isolamento de tenant via RLS (org_2 nao enxerga as regras da org_1)
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_2.value)},
    )

    rule_repo_2 = TransactionalRuleRepository(connection=db_connection)
    rule_service_2 = RuleService(repository=rule_repo_2)

    unseen_rules = rule_service_2.list_active_rules_for_policy_at(org_id_2, policy.policy_id, t0)
    assert len(unseen_rules) == 0
