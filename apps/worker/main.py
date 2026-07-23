"""Ponto de entrada do executável Worker assíncrono do Titan (ADR-0038)."""

import signal
import sys
import time
from typing import Any

from sqlalchemy import create_engine

from apps.worker.config import WorkerSettings
from packages.core_application import (
    ConsumerReceipt,
    IncomingMessageEnvelope,
    OutboxReconciliationService,
    ProcessingOutcome,
)
from packages.core_infrastructure.persistence.inbox import TransactionalInboxRepository
from packages.core_infrastructure.persistence.outbox import (
    TransactionalOutboxReconciliationRepository,
)
from packages.core_infrastructure.rabbitmq_consumer import RabbitMQPikaConsumer


class DefaultWorkerHandler:
    def handle(
        self, envelope: IncomingMessageEnvelope
    ) -> tuple[ProcessingOutcome, str | None, str | None]:
        return (
            ProcessingOutcome.SUCCESS,
            f"effect:{envelope.message_id.value}",
            f"decision:{envelope.semantic_operation_id.value}",
        )


def run_reconciliation(settings: WorkerSettings) -> None:
    engine = create_engine(settings.db_url, pool_pre_ping=True)
    with engine.connect() as connection:
        with connection.begin():
            repo = TransactionalOutboxReconciliationRepository(connection=connection)
            service = OutboxReconciliationService(repository=repo)
            report = service.run()
            if report.released_claims_count > 0:
                print(
                    f"[Worker {settings.worker_id}] Reconciliação executada: "
                    f"{report.released_claims_count} claims expirados liberados."
                )


def run_worker() -> None:
    settings = WorkerSettings.from_env()

    engine = create_engine(settings.db_url, pool_pre_ping=True)
    consumer = RabbitMQPikaConsumer(
        connection_url=settings.rabbitmq_url,
        queue_name=settings.queue_name,
        consumer_id=settings.worker_id,
        prefetch_count=1,
    )
    handler = DefaultWorkerHandler()

    def _shutdown_handler(signum: int, frame: Any) -> None:
        print(f"[Worker {settings.worker_id}] Recebido sinal {signum}. Iniciando shutdown...")
        consumer.stop_consuming()
        print(f"[Worker {settings.worker_id}] Encerramento concluído.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    def _on_message(envelope: IncomingMessageEnvelope) -> ConsumerReceipt:
        with engine.connect() as connection:
            with connection.begin():
                repo = TransactionalInboxRepository(
                    connection=connection, consumer_id=settings.worker_id
                )
                return repo.process_message(envelope=envelope, handler=handler)

    print(f"[Worker {settings.worker_id}] Iniciado. Escutando a fila '{settings.queue_name}'...")

    # Executa reconciliação inicial
    try:
        run_reconciliation(settings)
    except Exception as err:
        print(f"[Worker {settings.worker_id}] Reconciliação inicial ignorada: {err}")

    try:
        consumer.start_consuming(_on_message)
    except Exception as err:
        print(f"[Worker {settings.worker_id}] Erro de execução: {err}")
        time.sleep(1)


if __name__ == "__main__":
    run_worker()
