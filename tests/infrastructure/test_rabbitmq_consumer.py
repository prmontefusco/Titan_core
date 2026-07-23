"""Testes unitarios do adapter consumidor RabbitMQ (ADR-0038)."""

from unittest.mock import MagicMock, patch

from packages.core_infrastructure.rabbitmq_consumer import RabbitMQPikaConsumer


@patch("packages.core_infrastructure.rabbitmq_consumer.pika.BlockingConnection")
def test_rabbitmq_consumer_connection(mock_pika_conn: MagicMock) -> None:
    mock_conn_instance = MagicMock()
    mock_channel = MagicMock()
    mock_conn_instance.channel.return_value = mock_channel
    mock_pika_conn.return_value = mock_conn_instance

    consumer = RabbitMQPikaConsumer(
        connection_url="amqp://titan:titan@localhost:5672/titan",
        queue_name="titan.outbox",
    )
    consumer.connect()

    mock_channel.basic_qos.assert_called_once_with(prefetch_count=1)
