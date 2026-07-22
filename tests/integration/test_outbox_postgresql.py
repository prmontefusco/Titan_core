import os
from dataclasses import replace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError

from packages.core_application import EventOutboxService, MessageKind, OutboxMessage
from packages.core_domain import CanonicalPayload, DomainEvent, Organization
from packages.core_infrastructure.persistence import (
    DomainEventRepository,
    OrganizationRepository,
    TransactionalEventOutboxRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.outbox import outbox_messages_table
from packages.shared_kernel import TypedId
from tests.integration.test_domain_events_postgresql import _event, _reference

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada.")


def message_for(event: DomainEvent) -> OutboxMessage:
    return OutboxMessage(
        message_id=TypedId.new("outbox_message"),
        organization_id=event.organization_id,
        kind=MessageKind.DOMAIN_EVENT,
        contract_type="registro.criado",
        contract_version=1,
        actor_reference=event.actor_reference,
        producer_reference=_reference("service_identity", event.organization_id),
        timestamps=event.timestamps,
        correlation_id=event.correlation_id,
        causation_id=event.event_id,
        idempotency_key="operation-12345678",
        payload=CanonicalPayload.from_mapping(
            schema="registro_criado_integracao", version=1, value={"evento": "criado"}
        ),
        classification="PROTECTED",
    )


def test_event_and_outbox_commit_and_rollback_atomically() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    organization = Organization.create()
    aggregate = _reference("registro", organization.organization_id)
    first = _event(organization_id=organization.organization_id, aggregate=aggregate, version=1)
    first_message = message_for(first)

    try:
        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            OrganizationRepository(connection).add(organization)
            EventOutboxService(TransactionalEventOutboxRepository(connection)).append(
                first, first_message
            )

        second = _event(
            organization_id=organization.organization_id, aggregate=aggregate, version=2
        )
        duplicate_message = replace(message_for(second), message_id=first_message.message_id)
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                set_local_organization_context(connection, organization.organization_id)
                EventOutboxService(TransactionalEventOutboxRepository(connection)).append(
                    second, duplicate_message
                )

        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            assert DomainEventRepository(connection).list_versions(aggregate) == (1,)
            assert (
                connection.execute(
                    select(func.count()).select_from(outbox_messages_table)
                ).scalar_one()
                == 1
            )
    finally:
        engine.dispose()
