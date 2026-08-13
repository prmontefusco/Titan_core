import pytest
from sqlalchemy import Engine

from packages.core_infrastructure.persistence import (
    DatabaseConfigurationError,
    DatabaseSettings,
    create_database_engine,
)
from packages.core_infrastructure.persistence.database import (
    MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE,
)


def test_database_url_is_required() -> None:
    with pytest.raises(DatabaseConfigurationError, match="TITAN_DATABASE_URL"):
        DatabaseSettings.from_environment({})


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///titan.db",
        "postgresql+psycopg2://titan:secret@localhost/titan",
        "não-é-uma-url",
    ],
)
def test_database_url_rejects_unsupported_connection(url: str) -> None:
    with pytest.raises(DatabaseConfigurationError):
        DatabaseSettings.from_environment({"TITAN_DATABASE_URL": url})


def test_database_settings_do_not_expose_credentials_in_repr() -> None:
    settings = DatabaseSettings.from_environment(
        {"TITAN_DATABASE_URL": "postgresql+psycopg://titan:segredo@localhost/titan"}
    )

    assert "segredo" not in repr(settings)
    assert "titan" not in repr(settings)


def test_database_settings_can_require_the_migration_url() -> None:
    with pytest.raises(
        DatabaseConfigurationError, match=MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE
    ):
        DatabaseSettings.from_environment(
            {}, variable_name=MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE
        )


def test_engine_uses_psycopg_and_pre_ping() -> None:
    settings = DatabaseSettings.from_environment(
        {"TITAN_DATABASE_URL": "postgresql+psycopg://titan:segredo@localhost/titan"}
    )

    engine = create_database_engine(settings)

    assert isinstance(engine, Engine)
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    assert engine.pool._pre_ping is True
    engine.dispose()
