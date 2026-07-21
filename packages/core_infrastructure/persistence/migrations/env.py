"""Ambiente Alembic do PostgreSQL autoritativo do Titan."""

from collections.abc import MutableMapping
from logging.config import fileConfig
from typing import Literal

from alembic import context

from packages.core_infrastructure.persistence import (
    DatabaseSettings,
    create_database_engine,
)
from packages.core_infrastructure.persistence.memberships import memberships_table
from packages.core_infrastructure.persistence.organizations import (
    CORE_IDENTITY_SCHEMA,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = memberships_table.metadata


def include_managed_schema(
    name: str | None,
    type_: Literal[
        "schema",
        "table",
        "column",
        "index",
        "unique_constraint",
        "foreign_key_constraint",
    ],
    parent_names: MutableMapping[
        Literal["schema_name", "table_name", "schema_qualified_table_name"],
        str | None,
    ],
) -> bool:
    """Limita autogeração aos schemas que pertencem ao Titan."""
    if type_ == "schema":
        return name == CORE_IDENTITY_SCHEMA
    if type_ == "table":
        return parent_names.get("schema_name") == CORE_IDENTITY_SCHEMA
    return True


def run_migrations_offline() -> None:
    """Gera SQL sem estabelecer conexão."""

    settings = DatabaseSettings.from_environment()
    context.configure(
        url=settings.url,
        target_metadata=target_metadata,
        include_name=include_managed_schema,
        include_schemas=True,
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
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_name=include_managed_schema,
                include_schemas=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
