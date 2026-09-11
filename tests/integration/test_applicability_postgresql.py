"""Teste de integração PostgreSQL com RLS para `Applicability` (A3, Titan Asset)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.asset_domain.applicability import (
    Applicability,
    ApplicabilityState,
    ApplicabilityTarget,
)
from packages.asset_domain.part import Part, PartIdentity, PartRevision
from packages.asset_infrastructure.persistence.applicability_repository import (
    TransactionalApplicabilityRepository,
)
from packages.asset_infrastructure.persistence.part_repository import TransactionalPartRepository
from packages.shared_kernel import OrganizationId, TypedId


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        with conn.begin():
            yield conn


def test_applicability_persistence_withdraw_and_rls(db_connection: Connection) -> None:
    org_1 = OrganizationId(uuid4())
    org_2 = OrganizationId(uuid4())
    db_connection.execute(
        text(
            "INSERT INTO core_identity.organizations "
            "(organization_id, record_owner_organization_id) VALUES (:org1, :org1), (:org2, :org2)"
        ),
        {"org1": org_1.value, "org2": org_2.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_1.value)},
    )

    revision = PartRevision(revision_id=TypedId.new("part_revision"), revision_code="A")
    part = Part(
        part_id=TypedId.new("part"),
        organization_id=org_1,
        identity=PartIdentity(part_number="PN-300", description="Correia", manufacturer="Acme"),
        revisions=(revision,),
    )
    TransactionalPartRepository(connection=db_connection).save(part)

    applicability_repo = TransactionalApplicabilityRepository(connection=db_connection)
    valid_from = datetime(2026, 1, 1, tzinfo=UTC)
    applicability = Applicability(
        applicability_id=TypedId.new("applicability"),
        organization_id=org_1,
        part_ref=part.part_id,
        part_revision_ref=revision.revision_id,
        target=ApplicabilityTarget(
            model_ref=TypedId.new("vehicle_model"),
            variant_ref=None,
            serial_from="1000",
            serial_to=None,
            valid_from=valid_from,
            valid_until=None,
        ),
        evidence_ref=TypedId.new("evidence"),
        asserted_at=valid_from,
        asserted_by=TypedId.new("user"),
    )
    applicability_repo.save(applicability)

    saved = applicability_repo.get_by_id(applicability.applicability_id)
    assert saved is not None
    assert saved.state is ApplicabilityState.ASSERTED
    assert saved.target.serial_from == "1000"
    assert saved.asserted_by == applicability.asserted_by

    withdrawn_at = datetime(2026, 6, 1, tzinfo=UTC)
    withdrawn = saved.withdraw(reason="Substituída por revisão B.", withdrawn_at=withdrawn_at)
    applicability_repo.update(withdrawn)

    reloaded = applicability_repo.get_by_id(applicability.applicability_id)
    assert reloaded is not None
    assert reloaded.state is ApplicabilityState.WITHDRAWN
    assert reloaded.withdrawal_reason == "Substituída por revisão B."
    assert reloaded.version == 2

    role_name = f"titan_rls_app_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.applicability TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )
    applicability_repo_2 = TransactionalApplicabilityRepository(connection=db_connection)
    assert applicability_repo_2.get_by_id(applicability.applicability_id) is None
    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
