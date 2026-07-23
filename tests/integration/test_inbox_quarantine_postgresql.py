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
