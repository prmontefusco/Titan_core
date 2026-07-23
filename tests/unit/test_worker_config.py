"""Testes unitarios para configuracao do Worker (Passo 4.9D)."""

import os
from unittest.mock import patch

from apps.worker.config import WorkerSettings


def test_worker_settings_default_values() -> None:
    with patch.dict(os.environ, {}, clear=True):
        settings = WorkerSettings.from_env()
        assert "postgresql+psycopg://" in settings.db_url
        assert "amqp://" in settings.rabbitmq_url
        assert settings.queue_name == "titan.outbox"
        assert settings.worker_id == "worker-1"
        assert settings.reconciliation_interval_seconds == 60


def test_worker_settings_custom_values() -> None:
    custom_env = {
        "TITAN_DATABASE_URL": "postgresql+psycopg://user:pass@localhost:5432/db",
        "TITAN_RABBITMQ_URL": "amqp://user:pass@localhost:5672/vhost",
        "TITAN_WORKER_QUEUE": "custom.queue",
        "TITAN_WORKER_ID": "worker-custom",
        "TITAN_WORKER_RECONCILIATION_INTERVAL": "120",
    }
    with patch.dict(os.environ, custom_env, clear=True):
        settings = WorkerSettings.from_env()
        assert settings.db_url == "postgresql+psycopg://user:pass@localhost:5432/db"
        assert settings.rabbitmq_url == "amqp://user:pass@localhost:5672/vhost"
        assert settings.queue_name == "custom.queue"
        assert settings.worker_id == "worker-custom"
        assert settings.reconciliation_interval_seconds == 120
