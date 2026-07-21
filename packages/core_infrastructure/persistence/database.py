"""Configuração mínima da conexão PostgreSQL do Titan."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

DATABASE_URL_ENVIRONMENT_VARIABLE = "TITAN_DATABASE_URL"


class DatabaseConfigurationError(ValueError):
    """Indica configuração ausente ou incompatível do banco autoritativo."""


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Configuração externa da conexão, com credencial omitida da representação."""

    url: str = field(repr=False)

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "DatabaseSettings":
        source = os.environ if environment is None else environment
        value = source.get(DATABASE_URL_ENVIRONMENT_VARIABLE)

        if not value:
            raise DatabaseConfigurationError(
                f"{DATABASE_URL_ENVIRONMENT_VARIABLE} não foi definida."
            )

        try:
            parsed_url = make_url(value)
        except ArgumentError as error:
            raise DatabaseConfigurationError(
                f"{DATABASE_URL_ENVIRONMENT_VARIABLE} possui formato inválido."
            ) from error

        if parsed_url.get_backend_name() != "postgresql":
            raise DatabaseConfigurationError("A conexão autoritativa deve usar PostgreSQL.")

        if parsed_url.get_driver_name() != "psycopg":
            raise DatabaseConfigurationError("A conexão PostgreSQL deve declarar o driver psycopg.")

        return cls(url=value)


def create_database_engine(settings: DatabaseSettings) -> Engine:
    """Cria o pool sem abrir conexão antecipadamente."""

    return create_engine(settings.url, pool_pre_ping=True)


def check_database_connection(engine: Engine) -> None:
    """Confirma que o banco aceita uma consulta técnica mínima."""

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
