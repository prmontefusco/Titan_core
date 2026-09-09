"""Testes de integracao PostgreSQL real para quarentena e replay de mensagens (Passo 4.9C)."""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.inbox import (
    InboxQuarantineService,
    ReplayRequest,
)
from packages.core_infrastructure.persistence.inbox import (
    TransactionalInboxQuarantineRepository,
    TransactionalInboxRepository,
)
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


def test_inbox_quarantine_postgresql_list_and_replay_flow(
    db_connection: Connection,
) -> None:
    org_id = OrganizationId.new()
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:org_id, :org_id)
            """
        ),
        {"org_id": org_id.value},
    )

    # 1. Grava uma mensagem na quarentena pre-tenant
    inbox_repo = TransactionalInboxRepository(
        connection=db_connection, consumer_id="quarantine_worker"
    )
    quarantine_receipt = inbox_repo.record_untrusted_quarantine(
        envelope_bytes=b'{"corrupted": true}',
        alleged_producer="service_test",
        alleged_org=str(org_id.value),
        reason_code="INVALID_SIGNATURE",
    )
    assert quarantine_receipt.handling_outcome.value == "QUARANTINED"

    # 2. Inspeciona a quarentena via InboxQuarantineService
    quarantine_repo = TransactionalInboxQuarantineRepository(connection=db_connection)
    service = InboxQuarantineService(repository=quarantine_repo)

    records = service.list_quarantined(limit=10)
    assert len(records) >= 1
    target_record = records[0]
    assert target_record.reason_code == "INVALID_SIGNATURE"

    # 3. Dispara o replay autorizado por operador humano
    operator_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )

    request = ReplayRequest(
        quarantine_id=target_record.quarantine_id,
        operator_actor_reference=operator_ref,
        reason="Assinatura revalidada pelo operador de seguranca",
    )

    replay_result = service.replay(request)

    assert replay_result.status == "REQUEUED"
    assert replay_result.quarantine_id == target_record.quarantine_id


def test_inbox_quarantine_replay_rejects_cross_organization_operator(
    db_connection: Connection,
) -> None:
    org_id = OrganizationId.new()
    other_org_id = OrganizationId.new()
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:org_a, :org_a), (:org_b, :org_b)
            """
        ),
        {"org_a": org_id.value, "org_b": other_org_id.value},
    )

    inbox_repo = TransactionalInboxRepository(
        connection=db_connection, consumer_id="quarantine_worker"
    )
    inbox_repo.record_untrusted_quarantine(
        envelope_bytes=b'{"corrupted": true}',
        alleged_producer="service_test",
        alleged_org=str(org_id.value),
        reason_code="INVALID_SIGNATURE",
    )

    service = InboxQuarantineService(
        repository=TransactionalInboxQuarantineRepository(connection=db_connection)
    )
    record = service.list_quarantined(limit=1)[0]
    operator_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=other_org_id,
        contract_version=1,
    )

    result = service.replay(
        ReplayRequest(
            quarantine_id=record.quarantine_id,
            operator_actor_reference=operator_ref,
            reason="Tentativa cruzada",
        )
    )

    assert result.status == "FORBIDDEN"


def test_untrusted_quarantine_rls_hides_other_organization_records(
    db_connection: Connection,
) -> None:
    org_id = OrganizationId.new()
    other_org_id = OrganizationId.new()
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:org_a, :org_a), (:org_b, :org_b)
            """
        ),
        {"org_a": org_id.value, "org_b": other_org_id.value},
    )
    inbox_repo = TransactionalInboxRepository(
        connection=db_connection, consumer_id="quarantine_worker"
    )
    inbox_repo.record_untrusted_quarantine(
        envelope_bytes=b'{"corrupted": true}',
        alleged_producer="service_test",
        alleged_org=str(org_id.value),
        reason_code="INVALID_SIGNATURE",
    )
    quarantine_id = db_connection.execute(
        text(
            """
            SELECT quarantine_id
            FROM core_messaging.untrusted_message_quarantine
            WHERE record_owner_organization_id = :org_id
            """
        ),
        {"org_id": org_id.value},
    ).scalar_one()
    role_name = f"titan_quarantine_rls_{TypedId.new('role').value.hex[:12]}"
    quoted_role = db_connection.dialect.identifier_preparer.quote(role_name)
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_messaging TO {quoted_role}"))
    db_connection.execute(
        text(f"GRANT SELECT ON core_messaging.untrusted_message_quarantine TO {quoted_role}")
    )
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(other_org_id.value)},
    )

    visible = db_connection.execute(
        text(
            """
            SELECT count(*)
            FROM core_messaging.untrusted_message_quarantine
            WHERE quarantine_id = :quarantine_id
            """
        ),
        {"quarantine_id": quarantine_id},
    ).scalar_one()

    assert visible == 0


def test_permissions_and_untrusted_quarantine_have_rls_enabled(
    db_connection: Connection,
) -> None:
    rows = db_connection.execute(
        text(
            """
            SELECT n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE (n.nspname, c.relname) IN (
                ('core_identity', 'permissions'),
                ('core_messaging', 'untrusted_message_quarantine')
            )
            """
        )
    ).all()

    assert {
        (row.nspname, row.relname): (row.relrowsecurity, row.relforcerowsecurity) for row in rows
    } == {
        ("core_identity", "permissions"): (True, True),
        ("core_messaging", "untrusted_message_quarantine"): (True, True),
    }
