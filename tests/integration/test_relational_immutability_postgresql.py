"""ADR-0076: guards físicos dos registros históricos da Parte A."""

import os
from importlib import import_module
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

migration = import_module(
    "packages.core_infrastructure.persistence.migrations.versions."
    "20260908_0081_harden_relational_immutability"
)


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


def test_every_declared_historical_table_has_mutation_and_truncate_guards() -> None:
    url = os.environ.get("TITAN_MIGRATION_DATABASE_URL")
    assert url, "Teste exige TITAN_MIGRATION_DATABASE_URL administrativa."
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            # TRUNCATE triggers are absent from information_schema.triggers;
            # pg_trigger is authoritative for the complete catalog.
            triggers = [
                (row.table_name, row.function_name)
                for row in connection.execute(
                    text(
                        "SELECT c.relname AS table_name, p.proname AS function_name "
                        "FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "JOIN pg_proc p ON p.oid = t.tgfoid "
                        "WHERE n.nspname = 'core_audit' AND NOT t.tgisinternal"
                    )
                )
            ]
            for table in migration.IMMUTABLE_TABLES:
                matching = [item for item in triggers if item[0] == table]
                assert matching.count((table, "reject_historical_mutation")) == 2
    finally:
        engine.dispose()


def test_guard_rejects_update_delete_and_truncate_even_for_migration_role() -> None:
    url = os.environ.get("TITAN_MIGRATION_DATABASE_URL")
    assert url, "Teste exige TITAN_MIGRATION_DATABASE_URL administrativa."
    engine = create_engine(url)
    try:
        with engine.connect() as connection, connection.begin():
            owner = uuid4()
            property_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO core_identity.organizations "
                    "(organization_id, record_owner_organization_id) VALUES (:owner, :owner)"
                ),
                {"owner": owner},
            )
            connection.execute(
                text("SELECT set_config('titan.organization_id', :owner, true)"),
                {"owner": str(owner)},
            )
            connection.execute(
                text(
                    "INSERT INTO core_audit.rural_properties "
                    "(property_id, record_owner_organization_id, code, name, municipality, "
                    "state_code, created_at) VALUES "
                    "(:property_id, :owner, 'IMMUTABLE', 'Ficticia', 'Cuiaba', 'MT', NOW())"
                ),
                {"property_id": property_id, "owner": owner},
            )
            for statement, parameters in (
                (
                    "UPDATE core_audit.rural_properties SET name = 'Alterada' "
                    "WHERE property_id = :property_id",
                    {"property_id": property_id},
                ),
                (
                    "DELETE FROM core_audit.rural_properties WHERE property_id = :property_id",
                    {"property_id": property_id},
                ),
                ("TRUNCATE core_audit.shared_policy_access_log", {}),
            ):
                with pytest.raises(DBAPIError) as failure, connection.begin_nested():
                    connection.execute(text(statement), parameters)
                assert _sqlstate(failure.value) == "55000"
            assert (
                connection.execute(
                    text(
                        "SELECT name FROM core_audit.rural_properties "
                        "WHERE property_id = :property_id"
                    ),
                    {"property_id": property_id},
                ).scalar_one()
                == "Ficticia"
            )
    finally:
        engine.dispose()
