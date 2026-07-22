from dataclasses import dataclass, field

import pika  # type: ignore[import-untyped]

from packages.core_application import (
    BrokerPublicationStatus,
    ClaimedOutboxMessage,
    MessageKind,
    OutboxMessage,
)
from packages.core_domain import CanonicalPayload, DomainEvent
from packages.core_infrastructure.rabbitmq import RabbitMqOutboxPublisher, RabbitMqPublisherSettings
from packages.shared_kernel import TypedId
from tests.core_domain.test_domain_event import valid_event


@dataclass
class FakeChannel:
    publish_result: bool | None = True
    publish_error: Exception | None = None
    confirms_enabled: bool = False
    declared_exchange: str | None = None
    published: list[dict[str, object]] = field(default_factory=list)

    def confirm_delivery(self) -> None:
        self.confirms_enabled = True

    def exchange_declare(self, *, exchange: str, exchange_type: str, durable: bool) -> None:
        assert durable is True
        assert exchange_type == "topic"
        self.declared_exchange = exchange

    def basic_publish(
        self,
        *,
        exchange: str,
        routing_key: str,
        body: bytes,
        properties: object,
        mandatory: bool,
    ) -> bool | None:
        if self.publish_error is not None:
            raise self.publish_error
        self.published.append(
            {
                "exchange": exchange,
                "routing_key": routing_key,
                "body": body,
                "properties": properties,
                "mandatory": mandatory,
            }
        )
        return self.publish_result


@dataclass
class FakeConnection:
    channel_instance: FakeChannel
    closed: bool = False

    def channel(self) -> FakeChannel:
        return self.channel_instance

    def close(self) -> None:
        self.closed = True


def _claimed() -> ClaimedOutboxMessage:
    event = valid_event()
    return ClaimedOutboxMessage(
        message=_message_for(event),
        claim_token=TypedId.new("outbox_publication_claim"),
    )


def _message_for(event: DomainEvent) -> OutboxMessage:
    return OutboxMessage(
        message_id=TypedId.new("outbox_message"),
        organization_id=event.organization_id,
        kind=MessageKind.DOMAIN_EVENT,
        contract_type="registro.criado",
        contract_version=1,
        actor_reference=event.actor_reference,
        producer_reference=event.actor_reference,
        timestamps=event.timestamps,
        correlation_id=event.correlation_id,
        causation_id=event.event_id,
        idempotency_key="operation-12345678",
        payload=CanonicalPayload.from_mapping(
            schema="registro_criado_integracao", version=1, value={"evento": "criado"}
        ),
        classification="PROTECTED",
    )


def _publisher(connection: FakeConnection) -> RabbitMqOutboxPublisher:
    return RabbitMqOutboxPublisher(
        settings=RabbitMqPublisherSettings(
            amqp_url="amqp://titan:senha-local@localhost:5672/titan"
        ),
        connection_factory=lambda: connection,
    )


def test_rabbitmq_publisher_uses_confirms_and_persistent_message() -> None:
    channel = FakeChannel()
    connection = FakeConnection(channel)
    claimed = _claimed()

    result = _publisher(connection).publish(claimed)

    assert result.status is BrokerPublicationStatus.ACEITA_PELO_BROKER
    assert channel.confirms_enabled is True
    assert connection.closed is True
    published = channel.published[0]
    assert published["exchange"] == "titan.outbox"
    assert published["routing_key"] == "core.outbox"
    assert published["body"] == claimed.message.payload.canonical_bytes
    assert published["mandatory"] is True
    properties = published["properties"]
    assert isinstance(properties, pika.BasicProperties)
    assert properties.delivery_mode == 2
    assert properties.message_id == str(claimed.message.message_id.value)
    assert properties.headers["message_kind"] == claimed.message.kind.value


def test_rabbitmq_unroutable_is_not_reported_as_broker_accepted() -> None:
    channel = FakeChannel(publish_error=pika.exceptions.UnroutableError([]))
    connection = FakeConnection(channel)

    result = _publisher(connection).publish(_claimed())

    assert result.status is BrokerPublicationStatus.REJEITADA_PELO_BROKER
    assert result.reason == "UnroutableError"
    assert connection.closed is True


def test_rabbitmq_transport_error_preserves_unknown_outcome() -> None:
    channel = FakeChannel(publish_error=pika.exceptions.AMQPConnectionError("lost"))
    connection = FakeConnection(channel)

    result = _publisher(connection).publish(_claimed())

    assert result.status is BrokerPublicationStatus.RESULTADO_DESCONHECIDO
    assert result.reason == "AMQPConnectionError"
    assert connection.closed is True
