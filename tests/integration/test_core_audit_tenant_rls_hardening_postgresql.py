"""PostgreSQL/RLS regression tests for protected core_audit tenant tables."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from packages.core_domain import Organization
from packages.core_infrastructure.persistence import (
    OrganizationRepository,
    set_local_organization_context,
)

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL nao configurada para teste PostgreSQL.",
)

PROTECTED_TABLES = (
    "authorization_grants",
    "decision_proposals",
    "decision_reviews",
    "decision_overrides",
    "decision_contestations",
    "establishment_qualifications",
)


def test_core_audit_known_tenant_tables_have_rls_enabled_and_forced() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        c.relname,
                        c.relrowsecurity,
                        c.relforcerowsecurity
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'core_audit'
                      AND c.relname = ANY(:tables)
                    """
                ),
                {"tables": list(PROTECTED_TABLES)},
            ).fetchall()
    finally:
        engine.dispose()

    by_table = {row[0]: (row[1], row[2]) for row in rows}
    assert set(by_table) == set(PROTECTED_TABLES)
    assert all(enabled and forced for enabled, forced in by_table.values())


def test_authorization_grants_rls_is_bilateral_read_and_owner_write_only() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_authorization_grants_rls_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role_name)
    now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                owner = Organization.create()
                beneficiary = Organization.create()
                third_party = Organization.create()
                for organization in (owner, beneficiary, third_party):
                    set_local_organization_context(connection, organization.organization_id)
                    OrganizationRepository(connection).add(organization)

                policy_id = uuid4()
                grant_id = uuid4()
                _insert_policy(
                    connection,
                    policy_id=policy_id,
                    organization_id=owner.organization_id.value,
                    now=now,
                )
                _insert_authorization_grant(
                    connection,
                    grant_id=grant_id,
                    owner_organization_id=owner.organization_id.value,
                    beneficiary_organization_id=beneficiary.organization_id.value,
                    policy_id=policy_id,
                    now=now,
                )

                connection.execute(
                    text(
                        f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
                connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
                connection.execute(
                    text(
                        "GRANT SELECT, INSERT, UPDATE, DELETE "
                        "ON core_audit.authorization_grants "
                        f"TO {quoted_role}"
                    )
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                set_local_organization_context(connection, beneficiary.organization_id)
                assert _visible_grant_count(connection, grant_id) == 1
                assert _revoke_grant_count(connection, grant_id) == 0
                assert _delete_grant_count(connection, grant_id) == 0

                set_local_organization_context(connection, third_party.organization_id)
                assert _visible_grant_count(connection, grant_id) == 0
                assert _revoke_grant_count(connection, grant_id) == 0
                assert _delete_grant_count(connection, grant_id) == 0

                set_local_organization_context(connection, owner.organization_id)
                assert _visible_grant_count(connection, grant_id) == 1
                assert _revoke_grant_count(connection, grant_id) == 1
                assert _delete_grant_count(connection, grant_id) == 0
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def _insert_policy(
    connection: object,
    *,
    policy_id: object,
    organization_id: object,
    now: datetime,
) -> None:
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.policies (
                policy_id,
                record_owner_organization_id,
                code,
                name,
                description,
                version,
                status,
                valid_from,
                valid_to,
                created_at,
                published_at
            ) VALUES (
                :policy_id,
                :organization_id,
                :code,
                'Authorization Grant RLS Test Policy',
                'Synthetic policy only for authorization grant RLS test.',
                1,
                'PUBLISHED',
                :valid_from,
                NULL,
                :created_at,
                :published_at
            )
            """
        ),
        {
            "policy_id": policy_id,
            "organization_id": organization_id,
            "code": f"AUTH_GRANT_RLS_TEST_{uuid4().hex}",
            "valid_from": now,
            "created_at": now,
            "published_at": now,
        },
    )


def _insert_authorization_grant(
    connection: object,
    *,
    grant_id: object,
    owner_organization_id: object,
    beneficiary_organization_id: object,
    policy_id: object,
    now: datetime,
) -> None:
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.authorization_grants (
                grant_id,
                owner_organization_id,
                beneficiary_organization_id,
                policy_id,
                policy_version_id,
                access_purpose,
                field_scope_profile,
                valid_from,
                valid_until,
                status,
                created_at,
                created_by,
                record_owner_organization_id
            ) VALUES (
                :grant_id,
                :owner_organization_id,
                :beneficiary_organization_id,
                :policy_id,
                :policy_version_id,
                'AUTOAVALIACAO_CONTRATUAL_FORNECEDOR',
                'CONTRATO_MINIMO',
                :valid_from,
                :valid_until,
                'ATIVO',
                :created_at,
                'authorization-grants-rls-test',
                :owner_organization_id
            )
            """
        ),
        {
            "grant_id": grant_id,
            "owner_organization_id": owner_organization_id,
            "beneficiary_organization_id": beneficiary_organization_id,
            "policy_id": policy_id,
            "policy_version_id": uuid4(),
            "valid_from": now - timedelta(days=1),
            "valid_until": now + timedelta(days=30),
            "created_at": now,
        },
    )


def _visible_grant_count(connection: object, grant_id: object) -> int:
    count = connection.execute(  # type: ignore[attr-defined]
        text(
            """
            SELECT count(*)
            FROM core_audit.authorization_grants
            WHERE grant_id = :grant_id
            """
        ),
        {"grant_id": grant_id},
    ).scalar_one()
    return int(count)


def _revoke_grant_count(connection: object, grant_id: object) -> int:
    result = connection.execute(  # type: ignore[attr-defined]
        text(
            """
            UPDATE core_audit.authorization_grants
            SET status = 'REVOGADO', revoked_at = NOW(), revoked_by = 'rls-test'
            WHERE grant_id = :grant_id
            """
        ),
        {"grant_id": grant_id},
    )
    return int(result.rowcount)


def _delete_grant_count(connection: object, grant_id: object) -> int:
    result = connection.execute(  # type: ignore[attr-defined]
        text(
            """
            DELETE FROM core_audit.authorization_grants
            WHERE grant_id = :grant_id
            """
        ),
        {"grant_id": grant_id},
    )
    return int(result.rowcount)
