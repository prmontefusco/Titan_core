"""Testes unitarios para configuracao do Worker (Passo 4.9D)."""

import os
from unittest.mock import patch

import pytest

from apps.worker.config import WorkerSettings
from packages.core_infrastructure.persistence.database import DatabaseConfigurationError


def test_worker_settings_requires_runtime_database_url() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(DatabaseConfigurationError, match="TITAN_DATABASE_URL"):
            WorkerSettings.from_env()


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
