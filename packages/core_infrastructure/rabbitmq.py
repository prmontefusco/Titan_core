"""Adapter RabbitMQ para publicar mensagens da Transactional Outbox."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast

import pika  # type: ignore[import-untyped]

from packages.core_application import (
    BrokerPublicationResult,
    BrokerPublicationStatus,
    ClaimedOutboxMessage,
)


class RabbitMqChannel(Protocol):
    def confirm_delivery(self) -> None: ...

    def exchange_declare(
        self,
        *,
        exchange: str,
        exchange_type: str,
        durable: bool,
    ) -> Any: ...

    def basic_publish(
        self,
        *,
        exchange: str,
        routing_key: str,
        body: bytes,
        properties: Any,
        mandatory: bool,
    ) -> bool | None: ...


class RabbitMqConnection(Protocol):
    def channel(self) -> RabbitMqChannel: ...

    def close(self) -> None: ...


type RabbitMqConnectionFactory = Callable[[], RabbitMqConnection]


@dataclass(frozen=True, slots=True)
class RabbitMqPublisherSettings:
    amqp_url: str
    exchange: str = "titan.outbox"
    routing_key: str = "core.outbox"
    exchange_type: str = "topic"
    mandatory: bool = True

    def __post_init__(self) -> None:
        if not self.amqp_url:
            raise ValueError("amqp_url deve ser informada.")
        if not self.exchange:
            raise ValueError("exchange deve ser informado.")
        if not self.routing_key:
            raise ValueError("routing_key deve ser informado.")
        if self.exchange_type not in {"direct", "topic", "fanout"}:
            raise ValueError("exchange_type nao suportado.")


@dataclass(frozen=True, slots=True)
class RabbitMqOutboxPublisher:
    settings: RabbitMqPublisherSettings
    connection_factory: RabbitMqConnectionFactory | None = None

    def publish(self, claimed_message: ClaimedOutboxMessage) -> BrokerPublicationResult:
        connection: RabbitMqConnection | None = None
        try:
            connection = self._connect()
            channel = connection.channel()
            channel.confirm_delivery()
            channel.exchange_declare(
                exchange=self.settings.exchange,
                exchange_type=self.settings.exchange_type,
                durable=True,
            )
            accepted = channel.basic_publish(
                exchange=self.settings.exchange,
                routing_key=self.settings.routing_key,
                body=claimed_message.message.payload.canonical_bytes,
                properties=_properties_for(claimed_message),
                mandatory=self.settings.mandatory,
            )
        except (pika.exceptions.UnroutableError, pika.exceptions.NackError) as error:
            return BrokerPublicationResult(
                status=BrokerPublicationStatus.REJEITADA_PELO_BROKER,
                reason=error.__class__.__name__,
            )
        except pika.exceptions.AMQPError as error:
            return BrokerPublicationResult(
                status=BrokerPublicationStatus.RESULTADO_DESCONHECIDO,
                reason=error.__class__.__name__,
            )
        finally:
            if connection is not None:
                connection.close()

        if accepted is False:
            return BrokerPublicationResult(
                status=BrokerPublicationStatus.RESULTADO_DESCONHECIDO,
                reason="confirmacao_nao_positiva",
            )
        return BrokerPublicationResult(status=BrokerPublicationStatus.ACEITA_PELO_BROKER)

    def _connect(self) -> RabbitMqConnection:
        if self.connection_factory is not None:
            return self.connection_factory()
        return cast(
            RabbitMqConnection,
            pika.BlockingConnection(pika.URLParameters(self.settings.amqp_url)),
        )


def _properties_for(claimed_message: ClaimedOutboxMessage) -> Any:
    message = claimed_message.message
    return pika.BasicProperties(
        app_id="titan",
        content_type="application/titan-canonical-json",
        delivery_mode=2,
        message_id=str(message.message_id.value),
        correlation_id=str(message.correlation_id.value),
        type=message.contract_type,
        headers={
            "organization_id": str(message.organization_id.value),
            "message_kind": message.kind.value,
            "contract_version": message.contract_version,
            "payload_schema": message.payload.schema,
            "payload_version": message.payload.version,
            "causation_id": str(message.causation_id.value),
            "classification": message.classification,
        },
    )
