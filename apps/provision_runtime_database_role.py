"""Provisiona, de forma idempotente, a credencial PostgreSQL de runtime.

Executar com `TITAN_MIGRATION_DATABASE_URL` configurada. A senha da role de
aplicação nunca é registrada: ela vem de `TITAN_RUNTIME_DATABASE_PASSWORD`.
"""

import os
import re

from sqlalchemy import text

from packages.core_infrastructure.persistence.database import (
    MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE,
    DatabaseConfigurationError,
    DatabaseSettings,
    create_database_engine,
)

_ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise DatabaseConfigurationError(f"{name} não foi definida.")
    return value


def main() -> None:
    role = os.environ.get("TITAN_RUNTIME_DATABASE_ROLE", "titan_app")
    if not _ROLE_PATTERN.fullmatch(role):
        raise DatabaseConfigurationError("TITAN_RUNTIME_DATABASE_ROLE é inválida.")
    password = _required("TITAN_RUNTIME_DATABASE_PASSWORD")
    settings = DatabaseSettings.from_environment(
        variable_name=MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE
    )
    engine = create_database_engine(settings)
    quoted_role = engine.dialect.identifier_preparer.quote(role)
    try:
        with engine.begin() as connection:
            quoted_password = connection.execute(
                text("SELECT quote_literal(:password)"), {"password": password}
            ).scalar_one()
            exists = connection.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}
            ).scalar()
            if exists:
                connection.execute(text(f"ALTER ROLE {quoted_role} LOGIN NOINHERIT NOBYPASSRLS"))
                connection.execute(
                    text(f"ALTER ROLE {quoted_role} NOSUPERUSER NOCREATEDB NOCREATEROLE")
                )
                connection.execute(text(f"ALTER ROLE {quoted_role} PASSWORD {quoted_password}"))
            else:
                connection.execute(
                    text(
                        f"CREATE ROLE {quoted_role} LOGIN NOINHERIT NOSUPERUSER "
                        f"NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {quoted_password}"
                    )
                )
            for schema in ("core_identity", "core_audit"):
                connection.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO {quoted_role}"))
                connection.execute(
                    text(
                        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                        f"IN SCHEMA {schema} TO {quoted_role}"
                    )
                )
                connection.execute(
                    text(
                        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO {quoted_role}"
                    )
                )
                connection.execute(
                    text(
                        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT SELECT, "
                        f"INSERT, UPDATE, DELETE ON TABLES TO {quoted_role}"
                    )
                )
                connection.execute(
                    text(
                        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT USAGE, "
                        f"SELECT ON SEQUENCES TO {quoted_role}"
                    )
                )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
