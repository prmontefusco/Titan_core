"""Ambiente Alembic do PostgreSQL autoritativo do Titan."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import MetaData

from packages.core_infrastructure.persistence import (
    DatabaseSettings,
    create_database_engine,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = MetaData()


def run_migrations_offline() -> None:
    """Gera SQL sem estabelecer conexão."""

    settings = DatabaseSettings.from_environment()
    context.configure(
        url=settings.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrations em uma transação PostgreSQL."""

    settings = DatabaseSettings.from_environment()
    engine = create_database_engine(settings)

    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
