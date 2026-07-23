"""Testes de integração PostgreSQL para o registro e gestão de chaves sob RLS (Passo 5.5)."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from packages.core_application.crypto import KeyManagementService
from packages.core_domain.crypto import KeyState
from packages.core_infrastructure.persistence.crypto import TransactionalKeyRegistryRepository
from packages.shared_kernel import OrganizationId


@pytest.fixture
def database_engine() -> Iterator[Engine]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


def test_key_management_service_and_repository_with_postgresql_rls(
    database_engine: Engine,
) -> None:
    org_id_1 = OrganizationId(uuid4())
    org_id_2 = OrganizationId(uuid4())

    # 0. Cadastra a organizacao dona das chaves (FK de core_audit.key_registry)
    with database_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO core_identity.organizations
                (organization_id, record_owner_organization_id)
                VALUES (:org_id, :org_id)
                """
            ),
            {"org_id": org_id_1.value},
        )

    # 1. Registra chave para org_1 sob transação e RLS
    with database_engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('titan.organization_id', :org_id, true)"),
            {"org_id": str(org_id_1.value)},
        )
        repo_1 = TransactionalKeyRegistryRepository(connection=conn)
        service_1 = KeyManagementService(registry=repo_1)

        k1 = service_1.register_key(
            organization_id=org_id_1,
            purpose="Assinatura de Documentos",
            public_key_fingerprint="sha256:fingerprint_key_1",
        )
        assert k1.state == KeyState.ACTIVE

        # Consulta chave ativa
        active = service_1.get_active_key(org_id_1, "Assinatura de Documentos")
        assert active is not None
        assert active.key_identifier.key_id == k1.key_identifier.key_id

    # 2. Registra nova chave para o mesmo propósito na org_1 -> a chave anterior é rotacionada
    with database_engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('titan.organization_id', :org_id, true)"),
            {"org_id": str(org_id_1.value)},
        )
        repo_1 = TransactionalKeyRegistryRepository(connection=conn)
        service_1 = KeyManagementService(registry=repo_1)

        k2 = service_1.register_key(
            organization_id=org_id_1,
            purpose="Assinatura de Documentos",
            public_key_fingerprint="sha256:fingerprint_key_2",
        )
        assert k2.state == KeyState.ACTIVE

        # A chave k1 agora deve estar no estado ROTATED
        old_k1 = service_1.get_key(k1.key_identifier.key_id)
        assert old_k1 is not None
        assert old_k1.state == KeyState.ROTATED

    # 3. Revoga a chave k2
    with database_engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('titan.organization_id', :org_id, true)"),
            {"org_id": str(org_id_1.value)},
        )
        repo_1 = TransactionalKeyRegistryRepository(connection=conn)
        service_1 = KeyManagementService(registry=repo_1)

        revoked_k2 = service_1.revoke_key(
            key_id=k2.key_identifier.key_id,
            reason="Vazamento de credencial em auditoria",
        )
        assert revoked_k2.state == KeyState.REVOKED
        assert revoked_k2.revocation_reason == "Vazamento de credencial em auditoria"

    # 4. Verifica isolamento de tenant via RLS com org_2
    # O usuario titan e superusuario e ignora RLS; a checagem exige um role sem BYPASSRLS.
    with database_engine.begin() as conn:
        role_name = f"titan_test_rls_{uuid4().hex}"
        quoted_role = database_engine.dialect.identifier_preparer.quote(role_name)
        conn.execute(
            text(
                f"CREATE ROLE {quoted_role} "
                "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
            )
        )
        conn.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
        conn.execute(text(f"GRANT SELECT ON core_audit.key_registry TO {quoted_role}"))
        conn.execute(text(f"SET LOCAL ROLE {quoted_role}"))
        conn.execute(
            text("SELECT set_config('titan.organization_id', :org_id, true)"),
            {"org_id": str(org_id_2.value)},
        )
        repo_2 = TransactionalKeyRegistryRepository(connection=conn)
        service_2 = KeyManagementService(registry=repo_2)

        # org_2 não deve enxergar a chave k1 da org_1 devido ao RLS
        unseen_k1 = service_2.get_key(k1.key_identifier.key_id)
        assert unseen_k1 is None

        # org_2 não possui chave ativa para o propósito
        active_org_2 = service_2.get_active_key(org_id_2, "Assinatura de Documentos")
        assert active_org_2 is None

        conn.execute(text("RESET ROLE"))
        conn.execute(text(f"DROP OWNED BY {quoted_role}"))
        conn.execute(text(f"DROP ROLE {quoted_role}"))
