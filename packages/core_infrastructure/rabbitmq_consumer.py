"""Adapter RabbitMQ Pika para consumo de mensagens (ADR-0038)."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pika  # type: ignore[import-untyped]
from pika.adapters.blocking_connection import BlockingChannel  # type: ignore[import-untyped]
from pika.spec import Basic, BasicProperties  # type: ignore[import-untyped]

from packages.core_application import (
    AuthorizationEvaluationMode,
    AuthorizationReference,
    ConsumerReceipt,
    IncomingMessageEnvelope,
    MessageKind,
)
from packages.core_domain import CanonicalPayload
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference


def envelope_from_json_bytes(raw_bytes: bytes) -> IncomingMessageEnvelope:
    data = json.loads(raw_bytes.decode("utf-8"))
    organization_id = OrganizationId(data["organization_id"])

    auth_ref = None
    if data.get("auth_reference"):
        auth_data = data["auth_reference"]
        auth_ref = AuthorizationReference(
            decision_reference=auth_data["decision_reference"],
            policy_version=auth_data["policy_version"],
            accepted_at=datetime_from_iso(auth_data["accepted_at"]),
            accepting_service_identity=auth_data["accepting_service_identity"],
            context_digest=bytes.fromhex(auth_data["context_digest_hex"]),
        )

    return IncomingMessageEnvelope(
        message_id=TypedId(entity_type="outbox_message", value=data["message_id"]),
        organization_id=organization_id,
        kind=MessageKind(data["kind"]),
        contract_type=data["contract_type"],
        contract_version=int(data["contract_version"]),
        semantic_operation_id=TypedId(entity_type="operation", value=data["semantic_operation_id"]),
        actor_reference=UniversalReference(
            target_id=TypedId(entity_type=data["actor_type"], value=data["actor_id"]),
            organization_id=organization_id,
            contract_version=1,
        ),
        producer_reference=UniversalReference(
            target_id=TypedId(entity_type=data["producer_type"], value=data["producer_id"]),
            organization_id=organization_id,
            contract_version=1,
        ),
        timestamps=RecordTimestamps(
            occurred_at=datetime_from_iso(data["occurred_at"]),
            recorded_at=datetime_from_iso(data["recorded_at"]),
        ),
        correlation_id=TypedId(entity_type="correlation", value=data["correlation_id"]),
        causation_id=TypedId(entity_type="domain_event", value=data["causation_id"]),
        auth_evaluation_mode=AuthorizationEvaluationMode(data["auth_evaluation_mode"]),
        purpose=data["purpose"],
        auth_reference=auth_ref,
        payload=_payload_from_stored_bytes(
            schema=data["payload_schema"],
            version=int(data["payload_version"]),
            canonical_bytes=bytes.fromhex(data["payload_canonical_hex"]),
        ),
        classification=data.get("classification", "PROTECTED"),
    )


def _payload_from_stored_bytes(
    *, schema: str, version: int, canonical_bytes: bytes
) -> CanonicalPayload:
    payload = object.__new__(CanonicalPayload)
    object.__setattr__(payload, "schema", schema)
    object.__setattr__(payload, "version", version)
    object.__setattr__(payload, "canonical_bytes", canonical_bytes)
    return payload


def datetime_from_iso(iso_str: str) -> Any:
    from datetime import datetime

    return datetime.fromisoformat(iso_str)


@dataclass
class RabbitMQPikaConsumer:
    connection_url: str
    queue_name: str
    consumer_id: str = "worker_default"
    prefetch_count: int = 1

    _connection: pika.BlockingConnection | None = None
    _channel: BlockingChannel | None = None
    _consumer_tag: str | None = None
    _is_draining: bool = False

    def connect(self) -> None:
        params = pika.URLParameters(self.connection_url)
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        self._channel.basic_qos(prefetch_count=self.prefetch_count)

    def start_consuming(
        self,
        on_message_callback: Callable[[IncomingMessageEnvelope], ConsumerReceipt],
    ) -> None:
        if self._channel is None or self._connection is None:
            self.connect()

        assert self._channel is not None

        def _on_amqp_message(
            channel: BlockingChannel,
            method: Basic.Deliver,
            properties: BasicProperties,
            body: bytes,
        ) -> None:
            if self._is_draining:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return

            try:
                envelope = envelope_from_json_bytes(body)
                _receipt = on_message_callback(envelope)

                channel.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                # Falha inesperada de deserializacao ou transporte -> requeue sem ACK
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        self._consumer_tag = self._channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=_on_amqp_message,
            auto_ack=False,
        )
        self._channel.start_consuming()

    def stop_consuming(self) -> None:
        self._is_draining = True
        if self._channel and self._consumer_tag and self._channel.is_open:
            self._channel.basic_cancel(self._consumer_tag)
            self._channel.stop_consuming()
        if self._connection and self._connection.is_open:
            self._connection.close()
