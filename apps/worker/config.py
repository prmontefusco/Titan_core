"""Configurações e variáveis de ambiente para o Worker assíncrono do Titan."""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    db_url: str
    rabbitmq_url: str
    queue_name: str
    worker_id: str
    reconciliation_interval_seconds: int

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        return cls(
            db_url=os.getenv(
                "TITAN_DATABASE_URL",
                "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
            ),
            rabbitmq_url=os.getenv(
                "TITAN_RABBITMQ_URL",
                "amqp://titan:titan_rabbitmq_local_dev_password@127.0.0.1:5672/titan",
            ),
            queue_name=os.getenv("TITAN_WORKER_QUEUE", "titan.outbox"),
            worker_id=os.getenv("TITAN_WORKER_ID", "worker-1"),
            reconciliation_interval_seconds=int(
                os.getenv("TITAN_WORKER_RECONCILIATION_INTERVAL", "60")
            ),
        )
