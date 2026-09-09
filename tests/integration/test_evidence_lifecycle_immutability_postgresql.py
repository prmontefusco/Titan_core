"""ADR-0076 Parte B: Evidence baseline imutável e ciclo de vida append-only."""

import os
from importlib import import_module
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

migration = import_module(
    "packages.core_infrastructure.persistence.migrations.versions."
    "20260908_0082_preserve_evidence_lifecycle"
)


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


def test_evidence_lifecycle_tables_and_baseline_have_mutation_guards() -> None:
    url = os.environ.get("TITAN_MIGRATION_DATABASE_URL")
    assert url, "Teste exige TITAN_MIGRATION_DATABASE_URL administrativa."
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            triggers = {
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
            }
            for table in (*migration.LIFECYCLE_TABLES, "evidences"):
                assert (table, "reject_historical_mutation") in triggers
            for table in migration.LIFECYCLE_TABLES:
                assert (table, "enforce_evidence_lifecycle") in triggers
    finally:
        engine.dispose()


def test_evidence_baseline_rejects_update_delete_and_truncate() -> None:
    url = os.environ.get("TITAN_MIGRATION_DATABASE_URL")
    assert url, "Teste exige TITAN_MIGRATION_DATABASE_URL administrativa."
    engine = create_engine(url)
    try:
        with engine.connect() as connection, connection.begin():
            owner = uuid4()
            evidence_id = uuid4()
            source_id = uuid4()
            author_id = uuid4()
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
                    "INSERT INTO core_audit.evidences "
                    "(evidence_id, record_owner_organization_id, source_id, source_type, "
                    "source_metadata, author_id, author_org_id, author_contract_version, "
                    "content_hash, registered_at, confidence_tier, confidence_reason, version) "
                    "VALUES (:evidence_id, :owner, :source_id, 'DOCUMENT', '{}'::jsonb, "
                    ":author_id, :owner, 1, decode('01', 'hex'), NOW(), 'DECLARED', "
                    "'fixture ficticia', 1)"
                ),
                {
                    "evidence_id": evidence_id,
                    "owner": owner,
                    "source_id": source_id,
                    "author_id": author_id,
                },
            )
            operations: tuple[tuple[str, dict[str, Any], set[str]], ...] = (
                (
                    "UPDATE core_audit.evidences SET content_hash = decode('02', 'hex') "
                    "WHERE evidence_id = :evidence_id",
                    {"evidence_id": evidence_id},
                    {"55000"},
                ),
                (
                    "DELETE FROM core_audit.evidences WHERE evidence_id = :evidence_id",
                    {"evidence_id": evidence_id},
                    {"55000"},
                ),
                # PostgreSQL can reject TRUNCATE before the trigger because
                # evidences is referenced by lifecycle tables; both outcomes
                # preserve the physical no-truncate guarantee.
                ("TRUNCATE core_audit.evidences", {}, {"55000", "0A000"}),
            )
            for statement, parameters, expected_sqlstates in operations:
                with pytest.raises(DBAPIError) as failure, connection.begin_nested():
                    connection.execute(text(statement), parameters)
                assert _sqlstate(failure.value) in expected_sqlstates
    finally:
        engine.dispose()
