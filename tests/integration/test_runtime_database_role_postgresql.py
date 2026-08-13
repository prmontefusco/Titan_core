"""Confirma que credenciais administrativa e de runtime não são intercambiáveis."""

import os

import pytest

from packages.core_infrastructure.persistence.database import (
    MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE,
    DatabaseConfigurationError,
    DatabaseSettings,
    assert_runtime_database_role,
    create_database_engine,
)
from tests.livestock_api_support import DATABASE_URL

MIGRATION_DATABASE_URL = os.environ.get(MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE)
pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not MIGRATION_DATABASE_URL,
    reason="URLs de runtime e migration não configuradas.",
)


def test_administrative_role_is_refused_for_runtime() -> None:
    assert MIGRATION_DATABASE_URL is not None
    engine = create_database_engine(DatabaseSettings(url=MIGRATION_DATABASE_URL))
    try:
        with pytest.raises(DatabaseConfigurationError, match="SUPERUSER"):
            assert_runtime_database_role(engine)
    finally:
        engine.dispose()
