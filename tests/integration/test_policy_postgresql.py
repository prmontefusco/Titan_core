"""Testes de integração PostgreSQL com RLS para a Gestão de Políticas Versionadas (Passo 6.1)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.policy_service import PolicyService
from packages.core_domain.policy import PolicyStatus
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
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


def test_policy_versioning_lifecycle_and_rls(db_connection: Connection) -> None:
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

    # 2. Configura contexto RLS para org_1
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_1.value)},
    )

    repo_1 = TransactionalPolicyRepository(connection=db_connection)
    service_1 = PolicyService(repository=repo_1)

    # 3. Cria rascunho da política v1
    v1_draft = service_1.create_draft(
        organization_id=org_id_1,
        code="pol-sanidade",
        name="Política de Sanidade Animal",
        description="Regras v1 de sanidade",
    )
    assert v1_draft.version == 1
    assert v1_draft.status == PolicyStatus.DRAFT

    # Tentar criar segundo rascunho com o mesmo codigo lança erro
    with pytest.raises(ValueError, match="Já existe uma política com o código"):
        service_1.create_draft(
            organization_id=org_id_1,
            code="pol-sanidade",
            name="Duplicada",
        )

    # 4. Publica versão 1
    t0 = datetime.now(UTC) - timedelta(hours=2)
    v1_published = service_1.publish_policy(v1_draft.policy_id, published_at=t0)
    assert v1_published.status == PolicyStatus.PUBLISHED

    # Busca a política ativa na data t0
    active_at_t0 = service_1.get_active_policy_at(org_id_1, "pol-sanidade", t0)
    assert active_at_t0 is not None
    assert active_at_t0.version == 1

    # 5. Cria versão 2 e publica
    v2_draft = service_1.create_next_version(v1_published.policy_id, name="Política de Sanidade v2")
    assert v2_draft.version == 2
    assert v2_draft.status == PolicyStatus.DRAFT

    t1 = datetime.now(UTC)
    v2_published = service_1.publish_policy(v2_draft.policy_id, published_at=t1)
    assert v2_published.status == PolicyStatus.PUBLISHED

    # Verifica se a v1 foi marcada como SUPERSEDED automaticamente no repositório
    v1_check = repo_1.get_by_code_and_version(org_id_1, "pol-sanidade", 1)
    assert v1_check is not None
    assert v1_check.status == PolicyStatus.SUPERSEDED

    # Busca a política ativa na data atual t1 (deve retornar v2)
    active_at_t1 = service_1.get_active_policy_at(org_id_1, "pol-sanidade", t1)
    assert active_at_t1 is not None
    assert active_at_t1.version == 2

    # 6. Isolamento de tenant via RLS (org_2 nao enxerga as politicas da org_1)
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_2.value)},
    )

    repo_2 = TransactionalPolicyRepository(connection=db_connection)
    service_2 = PolicyService(repository=repo_2)

    unseen_policy = service_2.get_active_policy_at(org_id_2, "pol-sanidade", t1)
    assert unseen_policy is None
