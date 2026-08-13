"""Confirma que a credencial administrativa não pode executar runtime."""

import pytest

from packages.core_infrastructure.persistence.database import (
    DatabaseConfigurationError,
    DatabaseSettings,
    assert_runtime_database_role,
    create_database_engine,
)
from tests.livestock_api_support import DATABASE_URL

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada.")


def test_administrative_role_is_refused_for_runtime() -> None:
    assert DATABASE_URL is not None
    engine = create_database_engine(DatabaseSettings(url=DATABASE_URL))
    try:
        with pytest.raises(DatabaseConfigurationError, match="SUPERUSER"):
            assert_runtime_database_role(engine)
    finally:
        engine.dispose()
