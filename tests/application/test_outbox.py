from dataclasses import dataclass, field

import pytest

from packages.core_application import EventOutboxService, MessageKind, OutboxMessage
from packages.core_domain import CanonicalPayload, DomainEvent
from packages.shared_kernel import TypedId
from tests.core_domain.test_domain_event import reference, valid_event


def message_for(event: DomainEvent) -> OutboxMessage:
    return OutboxMessage(
        message_id=TypedId.new("outbox_message"),
        organization_id=event.organization_id,
        kind=MessageKind.DOMAIN_EVENT,
        contract_type="registro.criado",
        contract_version=1,
        actor_reference=event.actor_reference,
        producer_reference=reference("service_identity", event.organization_id),
        timestamps=event.timestamps,
        correlation_id=event.correlation_id,
        causation_id=event.event_id,
        idempotency_key="operation-12345678",
        payload=CanonicalPayload.from_mapping(
            schema="registro_criado_integracao", version=1, value={"evento": "criado"}
        ),
        classification="PROTECTED",
    )


@dataclass
class InMemoryWriter:
    pairs: list[tuple[DomainEvent, OutboxMessage]] = field(default_factory=list)

    def append(self, event: DomainEvent, message: OutboxMessage) -> None:
        self.pairs.append((event, message))


def test_service_writes_event_and_message_as_one_pair() -> None:
    event = valid_event()
    message = message_for(event)
    writer = InMemoryWriter()

    EventOutboxService(writer).append(event, message)

    assert writer.pairs == [(event, message)]


def test_service_rejects_message_caused_by_another_event() -> None:
    event = valid_event()
    message = message_for(event)
    divergent = OutboxMessage(
        message_id=message.message_id,
        organization_id=message.organization_id,
        kind=message.kind,
        contract_type=message.contract_type,
        contract_version=message.contract_version,
        actor_reference=message.actor_reference,
        producer_reference=message.producer_reference,
        timestamps=message.timestamps,
        correlation_id=message.correlation_id,
        causation_id=TypedId.new("domain_event"),
        idempotency_key=message.idempotency_key,
        payload=message.payload,
        classification=message.classification,
    )
    with pytest.raises(ValueError, match="causada"):
        EventOutboxService(InMemoryWriter()).append(event, divergent)
