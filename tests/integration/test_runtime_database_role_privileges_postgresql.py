"""ADR-0076: reprovisionamento remove ACLs antigas sem reabrir histórico."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from apps.provision_runtime_database_role import main


def test_reprovisioning_restricts_existing_role_and_default_privileges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = os.environ.get("TITAN_MIGRATION_DATABASE_URL")
    assert url, "Provisionamento exige TITAN_MIGRATION_DATABASE_URL administrativa."
    engine = create_engine(url)
    role = f"test_runtime_{uuid4().hex}"
    monkeypatch.setenv("TITAN_RUNTIME_DATABASE_ROLE", role)
    monkeypatch.setenv("TITAN_RUNTIME_DATABASE_PASSWORD", uuid4().hex)
    try:
        with engine.begin() as connection:
            connection.execute(text(f"CREATE ROLE {role} NOLOGIN"))
            for schema in ("core_identity", "core_audit", "core_messaging"):
                connection.execute(text(f"GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO {role}"))
                connection.execute(
                    text(
                        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON TABLES TO {role}"
                    )
                )
            connection.execute(
                text(f"GRANT UPDATE (content_hash) ON core_audit.evidences TO {role}")
            )
        for _ in range(2):
            main()
            with engine.connect() as connection, connection.begin():
                for table in ("domain_events", "treatment_applications", "animal_movements"):
                    for operation in ("UPDATE", "DELETE", "TRUNCATE"):
                        assert not connection.execute(
                            text("SELECT has_table_privilege(:role, :table, :operation)"),
                            {"role": role, "table": f"core_audit.{table}", "operation": operation},
                        ).scalar_one()
                    for operation in ("SELECT", "INSERT"):
                        assert connection.execute(
                            text("SELECT has_table_privilege(:role, :table, :operation)"),
                            {"role": role, "table": f"core_audit.{table}", "operation": operation},
                        ).scalar_one()
                for table, column, expected in (
                    ("animals", "version", True),
                    ("animals", "sex", False),
                    ("idempotency_records", "status", True),
                    ("idempotency_records", "intent_digest", False),
                    ("evidences", "content_hash", False),
                ):
                    assert (
                        connection.execute(
                            text("SELECT has_column_privilege(:role, :table, :column, 'UPDATE')"),
                            {"role": role, "table": f"core_audit.{table}", "column": column},
                        ).scalar_one()
                        is expected
                    )
                for table in ("reference_projection", "property_stays", "animal_identifiers"):
                    assert connection.execute(
                        text("SELECT has_table_privilege(:role, :table, 'DELETE')"),
                        {"role": role, "table": f"core_audit.{table}"},
                    ).scalar_one()
                for table in (
                    "inbox_messages",
                    "inbox_delivery_attempts",
                    "inbox_conflicts",
                    "untrusted_message_quarantine",
                ):
                    for operation in ("SELECT", "INSERT"):
                        assert connection.execute(
                            text("SELECT has_table_privilege(:role, :table, :operation)"),
                            {
                                "role": role,
                                "table": f"core_messaging.{table}",
                                "operation": operation,
                            },
                        ).scalar_one()
                    for operation in ("DELETE", "TRUNCATE"):
                        assert not connection.execute(
                            text("SELECT has_table_privilege(:role, :table, :operation)"),
                            {
                                "role": role,
                                "table": f"core_messaging.{table}",
                                "operation": operation,
                            },
                        ).scalar_one()
                for table, column, expected in (
                    ("inbox_messages", "status", True),
                    ("inbox_messages", "attempt_number", True),
                    ("inbox_messages", "semantic_message_digest", False),
                    ("inbox_delivery_attempts", "handling_result", False),
                    ("untrusted_message_quarantine", "rejection_reason_code", False),
                ):
                    assert (
                        connection.execute(
                            text("SELECT has_column_privilege(:role, :table, :column, 'UPDATE')"),
                            {"role": role, "table": f"core_messaging.{table}", "column": column},
                        ).scalar_one()
                        is expected
                    )
                for schema in ("core_identity", "core_audit", "core_messaging"):
                    # A tabela é criada e revertida nesta transação: prova defaults reais.
                    table = f"{schema}.acl_probe_{uuid4().hex}"
                    connection.execute(text(f"CREATE TABLE {table} (value integer)"))
                    for operation in ("UPDATE", "DELETE", "TRUNCATE"):
                        assert not connection.execute(
                            text("SELECT has_table_privilege(:role, :table, :operation)"),
                            {"role": role, "table": table, "operation": operation},
                        ).scalar_one()
                    connection.execute(text(f"DROP TABLE {table}"))
                connection.execute(text(f"SET LOCAL ROLE {role}"))
                # Locks pessimistas existentes continuam disponíveis sem abrir
                # UPDATE real: as colunas de identidade têm grant mínimo e os
                # triggers da ADR-0076 recusam qualquer mutação.
                for statement in (
                    "SELECT message_id FROM core_audit.outbox_messages WHERE false FOR UPDATE",
                    "SELECT event_id FROM core_audit.transformation_events WHERE false FOR UPDATE",
                    "SELECT item_id FROM core_audit.traceable_items WHERE false FOR UPDATE",
                    "SELECT animal_id FROM core_audit.animals WHERE false FOR UPDATE",
                ):
                    connection.execute(text(statement))
                for statement in (
                    "UPDATE core_audit.domain_events SET event_id = event_id WHERE false",
                    "DELETE FROM core_audit.domain_events WHERE false",
                    "TRUNCATE core_audit.shared_policy_access_log",
                ):
                    with pytest.raises(DBAPIError) as error, connection.begin_nested():
                        connection.execute(text(statement))
                    assert getattr(error.value.orig, "sqlstate", None) == "42501"
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP OWNED BY {role}"))
            connection.execute(text(f"DROP ROLE IF EXISTS {role}"))
        engine.dispose()
