"""Teste de integração PostgreSQL com RLS para `ConfigurationBaseline` (A3)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.asset_domain.configuration import (
    BaselinePosition,
    ConfigurationBaseline,
    ConfigurationRevision,
    ConfigurationView,
    Effectivity,
)
from packages.asset_domain.part import Part, PartIdentity, PartRevision
from packages.asset_infrastructure.persistence.configuration_repository import (
    TransactionalConfigurationBaselineRepository,
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


def test_configuration_baseline_persistence_supersession_and_rls(
    db_connection: Connection,
) -> None:
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
        identity=PartIdentity(part_number="PN-400", description="Bomba", manufacturer="Acme"),
        revisions=(revision,),
    )
    TransactionalPartRepository(connection=db_connection).save(part)

    baseline_repo = TransactionalConfigurationBaselineRepository(connection=db_connection)
    model_ref = TypedId.new("vehicle_model")
    first_baseline = ConfigurationBaseline(
        baseline_id=TypedId.new("configuration_baseline"),
        organization_id=org_1,
        model_ref=model_ref,
        revision=ConfigurationRevision(number=1),
        effectivity=Effectivity(valid_from=datetime(2026, 1, 1, tzinfo=UTC)),
        positions=(
            BaselinePosition(
                position_code="POS-01",
                part_ref=part.part_id,
                part_revision_ref=revision.revision_id,
            ),
        ),
    )
    baseline_repo.save(first_baseline)

    saved = baseline_repo.get_by_id(first_baseline.baseline_id)
    assert saved is not None
    assert saved.model_ref == model_ref
    assert saved.revision.number == 1
    assert saved.revision.supersedes_ref is None
    assert len(saved.positions) == 1
    assert saved.positions[0].position_code == "POS-01"

    second_baseline = ConfigurationBaseline(
        baseline_id=TypedId.new("configuration_baseline"),
        organization_id=org_1,
        model_ref=model_ref,
        revision=ConfigurationRevision(number=2, supersedes_ref=first_baseline.baseline_id),
        effectivity=Effectivity(valid_from=datetime(2026, 6, 1, tzinfo=UTC)),
        positions=(
            BaselinePosition(
                position_code="POS-01",
                part_ref=part.part_id,
                part_revision_ref=revision.revision_id,
            ),
        ),
        view=ConfigurationView.AS_MAINTAINED,
    )
    baseline_repo.save(second_baseline)

    reloaded_second = baseline_repo.get_by_id(second_baseline.baseline_id)
    assert reloaded_second is not None
    assert reloaded_second.revision.supersedes_ref == first_baseline.baseline_id
    assert reloaded_second.view is ConfigurationView.AS_MAINTAINED

    role_name = f"titan_rls_cfg_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    for table in ("configuration_baselines", "configuration_baseline_positions"):
        db_connection.execute(text(f"GRANT ALL ON core_audit.{table} TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )
    baseline_repo_2 = TransactionalConfigurationBaselineRepository(connection=db_connection)
    assert baseline_repo_2.get_by_id(first_baseline.baseline_id) is None
    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
