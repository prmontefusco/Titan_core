import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from packages.core_domain import Organization
from packages.core_infrastructure.persistence import (
    DomainEventRepository,
    IntegrityCheckpointRepository,
    OrganizationRepository,
    set_local_organization_context,
)
from packages.core_integrity import build_event_chain_entry, build_integrity_checkpoint
from packages.shared_kernel import TypedId
from tests.integration.test_domain_events_postgresql import _event, _reference

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)


def test_checkpoint_is_persisted_with_exact_coverage_and_is_immutable_for_runtime() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    organization = Organization.create()
    aggregate = _reference("registro", organization.organization_id)
    first_event = _event(
        organization_id=organization.organization_id, aggregate=aggregate, version=1
    )
    second_event = _event(
        organization_id=organization.organization_id, aggregate=aggregate, version=2
    )
    first_entry = build_event_chain_entry(first_event, None)
    entries = (first_entry, build_event_chain_entry(second_event, first_entry.current_hash))
    checkpoint = build_integrity_checkpoint(
        checkpoint_id=TypedId.new("integrity_checkpoint"),
        entries=entries,
        observed_at=datetime(2026, 7, 21, 19, 0, tzinfo=UTC),
        producer_reference=_reference("service_identity", organization.organization_id),
        correlation_id=TypedId.new("correlation"),
        causation_id=second_event.event_id,
    )
    role_name = f"titan_checkpoint_runtime_{uuid4().hex}"
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
                        "core_audit.domain_events, core_audit.domain_event_integrity, "
                        "core_audit.integrity_checkpoints, "
                        f"core_audit.integrity_checkpoint_events TO {quoted_role}"
                    )
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
                set_local_organization_context(connection, organization.organization_id)
                OrganizationRepository(connection).add(organization)
                events = DomainEventRepository(connection)
                events.append(first_event)
                events.append(second_event)
                repository = IntegrityCheckpointRepository(connection)
                repository.add(checkpoint)

                assert repository.get(checkpoint.checkpoint_id) == checkpoint

                for statement in (
                    "UPDATE core_audit.integrity_checkpoints SET record_count = 1",
                    "DELETE FROM core_audit.integrity_checkpoints",
                    "TRUNCATE core_audit.integrity_checkpoint_events",
                ):
                    savepoint = connection.begin_nested()
                    with pytest.raises(ProgrammingError):
                        connection.execute(text(statement))
                    savepoint.rollback()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
