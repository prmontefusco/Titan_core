import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from packages.core_domain import CanonicalPayload, DomainEvent, Organization
from packages.core_infrastructure.persistence import (
    DomainEventRepository,
    EventAppendConflict,
    OrganizationRepository,
    set_local_organization_context,
)
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)


def _reference(
    entity_type: str, organization_id: OrganizationId, *, identifier: TypedId | None = None
) -> UniversalReference:
    return UniversalReference(
        target_id=identifier or TypedId.new(entity_type),
        organization_id=organization_id,
        contract_version=1,
    )


def _event(
    *, organization_id: OrganizationId, aggregate: UniversalReference, version: int
) -> DomainEvent:
    return DomainEvent(
        event_id=TypedId.new("domain_event"),
        organization_id=organization_id,
        aggregate_reference=aggregate,
        aggregate_version=version,
        event_type="registro_criado",
        event_version=1,
        timestamps=RecordTimestamps(
            occurred_at=datetime(2026, 7, 21, 12, version, tzinfo=UTC),
            recorded_at=datetime(2026, 7, 21, 13, version, tzinfo=UTC),
        ),
        actor_reference=_reference("actor", organization_id),
        source_reference=_reference("source", organization_id),
        correlation_id=TypedId.new("correlation"),
        causation_id=None,
        payload=CanonicalPayload.from_mapping(
            schema="registro_criado_payload",
            version=1,
            value={"versao": version},
        ),
    )


def test_event_store_orders_versions_rejects_gaps_and_isolates_organizations() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    first_organization = Organization.create()
    second_organization = Organization.create()
    aggregate_id = TypedId.new("registro")
    first_aggregate = _reference(
        "registro", first_organization.organization_id, identifier=aggregate_id
    )
    second_aggregate = _reference(
        "registro", second_organization.organization_id, identifier=aggregate_id
    )
    role_name = f"titan_event_isolation_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role_name)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(
                    text(
                        f"CREATE ROLE {quoted_role} "
                        "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
                connection.execute(
                    text(f"GRANT USAGE ON SCHEMA core_identity, core_audit TO {quoted_role}")
                )
                connection.execute(
                    text(
                        f"GRANT SELECT, INSERT ON core_identity.organizations, "
                        f"core_audit.domain_events, core_audit.domain_event_integrity "
                        f"TO {quoted_role}"
                    )
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
                organizations = OrganizationRepository(connection)
                set_local_organization_context(connection, first_organization.organization_id)
                organizations.add(first_organization)
                events = DomainEventRepository(connection)
                events.append(
                    _event(
                        organization_id=first_organization.organization_id,
                        aggregate=first_aggregate,
                        version=1,
                    )
                )
                events.append(
                    _event(
                        organization_id=first_organization.organization_id,
                        aggregate=first_aggregate,
                        version=2,
                    )
                )
                with pytest.raises(EventAppendConflict, match="VERSAO_DE_AGREGADO_CONFLITANTE"):
                    events.append(
                        _event(
                            organization_id=first_organization.organization_id,
                            aggregate=first_aggregate,
                            version=4,
                        )
                    )
                assert [
                    item.aggregate_version for item in events.list_for_aggregate(first_aggregate)
                ] == [1, 2]
                stored_chain = events.list_for_aggregate(first_aggregate)
                assert stored_chain[0].previous_hash is None
                assert stored_chain[0].current_hash == stored_chain[1].previous_hash
                assert stored_chain[1].current_hash is not None

                set_local_organization_context(connection, second_organization.organization_id)
                organizations.add(second_organization)
                assert events.list_for_aggregate(first_aggregate) == ()
                events.append(
                    _event(
                        organization_id=second_organization.organization_id,
                        aggregate=second_aggregate,
                        version=1,
                    )
                )
                assert [
                    item.aggregate_version for item in events.list_for_aggregate(second_aggregate)
                ] == [1]
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_runtime_role_cannot_update_delete_or_truncate_events() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_event_runtime_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role_name)
    organization = Organization.create()
    aggregate = _reference("registro", organization.organization_id)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                set_local_organization_context(connection, organization.organization_id)
                OrganizationRepository(connection).add(organization)
                connection.execute(
                    text(
                        f"CREATE ROLE {quoted_role} "
                        "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
                connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
                connection.execute(
                    text(
                        f"GRANT SELECT, INSERT ON core_audit.domain_events, "
                        f"core_audit.domain_event_integrity TO {quoted_role}"
                    )
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
                DomainEventRepository(connection).append(
                    _event(
                        organization_id=organization.organization_id,
                        aggregate=aggregate,
                        version=1,
                    )
                )
                for statement in (
                    "UPDATE core_audit.domain_events SET event_version = 2",
                    "DELETE FROM core_audit.domain_events",
                    "TRUNCATE core_audit.domain_events",
                    "UPDATE core_audit.domain_event_integrity SET hash_profile_version = 2",
                    "DELETE FROM core_audit.domain_event_integrity",
                    "TRUNCATE core_audit.domain_event_integrity",
                ):
                    savepoint = connection.begin_nested()
                    with pytest.raises(ProgrammingError):
                        connection.execute(text(statement))
                    savepoint.rollback()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
