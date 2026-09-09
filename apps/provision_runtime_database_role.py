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

# ADR-0076: colunas utilizadas pelos repositórios de estado operacional.
_AUDIT_UPDATE_COLUMNS = {
    "animals": "version",
    "authorization_grants": "status, revoked_at, revoked_by, revocation_reason",
    "entity_type_requests": "status, decided_at, decided_by_actor_id, decision_reason",
    "idempotency_records": "status, result_schema, result_version, result_canonical_bytes",
    "key_registry": "state, expires_at, revoked_at, revocation_reason, version",
    "livestock_lots": "name, lot_type, status",
    "lot_memberships": "valid_until, reason",
    "nonconformities": (
        "severity, status, affected_from, affected_until, responsible_reference, due_date, "
        "corrective_action, correction_evidence_references, reevaluation_id, closed_at, "
        "closure_note, transitions"
    ),
    "outbox_publication_state": (
        "status, claim_token, publisher_id, claimed_at, lease_expires_at, attempt_count, "
        "last_attempt_at, broker_accepted_at, last_result_at, last_reason"
    ),
    # PostgreSQL exige algum privilégio UPDATE para SELECT ... FOR UPDATE.
    # Apenas a coluna de identidade é concedida; triggers da ADR-0076 recusam
    # qualquer UPDATE real nessas tabelas históricas.
    "outbox_messages": "message_id",
    "policies": "name, description, status, valid_from, valid_to, published_at",
    "property_stays": "end_time, status",
    "relations": (
        "valid_until, confidence_tier, confidence_reason, evidence_references, "
        "relation_metadata, metadata_version"
    ),
    "rule_adoptions": (
        "rule_version_id, adopted_by_target_type, adopted_by_target_id, "
        "adopted_by_organization_id, adopted_by_contract_version, adopted_at, reason, status"
    ),
    "rules": (
        "name, description, severity, normative_source, required_evidence_types, conditions, "
        "justification, corrective_action, valid_from, valid_to"
    ),
    "shared_decisions": "status, review_decision, review_content, reviewed_at, reviewed_by",
    "synchronization_batches": (
        "attempts, state, examined_count, counts, gaps, limitations, processed_at"
    ),
    "traceable_items": "item_id",
    "transformation_events": "event_id",
    "veterinarians": "name, verification_status, evidence_reference",
}
_AUDIT_DELETE_TABLES = ("reference_projection", "property_stays", "animal_identifiers")
_MESSAGING_UPDATE_COLUMNS = {
    "inbox_messages": (
        "status, available_at, attempt_number, completed_at, completion_result_code, "
        "effect_reference, decision_reference, result_digest"
    ),
}


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
            for schema in ("core_identity", "core_audit", "core_messaging"):
                connection.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO {quoted_role}"))
                # Retira também concessões antigas; GRANT restrito sozinho não as reduz.
                connection.execute(
                    text(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {quoted_role}")
                )
                # Privilégios por coluna sobrevivem à revogação no nível da tabela.
                columns_by_table = connection.execute(
                    text(
                        "SELECT table_name, string_agg(quote_ident(column_name), ', ') AS columns "
                        "FROM information_schema.columns WHERE table_schema = :schema "
                        "GROUP BY table_name"
                    ),
                    {"schema": schema},
                )
                for table_name, columns in columns_by_table:
                    quoted_table = engine.dialect.identifier_preparer.quote(table_name)
                    connection.execute(
                        text(
                            f"REVOKE ALL ({columns}) ON {schema}.{quoted_table} FROM {quoted_role}"
                        )
                    )
                connection.execute(
                    text(f"GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA {schema} TO {quoted_role}")
                )
                connection.execute(
                    text(
                        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO {quoted_role}"
                    )
                )
                connection.execute(
                    text(
                        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL "
                        f"ON TABLES FROM {quoted_role}"
                    )
                )
                connection.execute(
                    text(
                        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT SELECT, "
                        f"INSERT ON TABLES TO {quoted_role}"
                    )
                )
                connection.execute(
                    text(
                        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT USAGE, "
                        f"SELECT ON SEQUENCES TO {quoted_role}"
                    )
                )
            for table, columns in _AUDIT_UPDATE_COLUMNS.items():
                connection.execute(
                    text(f"GRANT UPDATE ({columns}) ON core_audit.{table} TO {quoted_role}")
                )
            for table in _AUDIT_DELETE_TABLES:
                connection.execute(text(f"GRANT DELETE ON core_audit.{table} TO {quoted_role}"))
            for table, columns in _MESSAGING_UPDATE_COLUMNS.items():
                connection.execute(
                    text(f"GRANT UPDATE ({columns}) ON core_messaging.{table} TO {quoted_role}")
                )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
