"""Teste de integração PostgreSQL com RLS para `Part`/`InterchangeabilityGroup` (A3)."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.asset_domain.part import (
    InterchangeabilityGroup,
    Part,
    PartIdentity,
    PartLifecycleState,
    PartRevision,
)
from packages.asset_infrastructure.persistence.part_repository import (
    TransactionalInterchangeabilityGroupRepository,
    TransactionalPartRepository,
)
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


def test_part_persistence_with_revisions_and_supersession(db_connection: Connection) -> None:
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

    part_repo = TransactionalPartRepository(connection=db_connection)
    revision_a = PartRevision(revision_id=TypedId.new("part_revision"), revision_code="A")
    part = Part(
        part_id=TypedId.new("part"),
        organization_id=org_1,
        identity=PartIdentity(
            part_number="PN-100",
            description="Retentor hidráulico",
            manufacturer="Acme",
            external_classifications=("HAZMAT", "CRITICAL"),
        ),
        revisions=(revision_a,),
    )
    part_repo.save(part)

    saved = part_repo.get_by_id(part.part_id)
    assert saved is not None
    assert saved.identity.part_number == "PN-100"
    assert saved.identity.external_classifications == ("HAZMAT", "CRITICAL")
    assert len(saved.revisions) == 1
    assert saved.revisions[0].revision_code == "A"

    revision_b = PartRevision(revision_id=TypedId.new("part_revision"), revision_code="B")
    part_with_b = saved.add_revision(revision_b)
    superseded = part_with_b.supersede_revision(
        predecessor_revision_id=revision_a.revision_id,
        successor_revision_id=revision_b.revision_id,
        reason="Retentor A descontinuado pelo fabricante.",
    )
    part_repo.update(superseded)

    reloaded = part_repo.get_by_id(part.part_id)
    assert reloaded is not None
    assert len(reloaded.revisions) == 2
    assert len(reloaded.supersessions) == 1
    predecessor = next(r for r in reloaded.revisions if r.revision_id == revision_a.revision_id)
    assert predecessor.lifecycle_state is PartLifecycleState.SUPERSEDED

    # RLS: role sem BYPASSRLS em outra Organization não enxerga a peça.
    role_name = f"titan_rls_part_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    for table in ("parts", "part_revisions", "part_supersessions", "interchangeability_groups"):
        db_connection.execute(text(f"GRANT ALL ON core_audit.{table} TO {quoted_role}"))
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )
    part_repo_2 = TransactionalPartRepository(connection=db_connection)
    assert part_repo_2.get_by_id(part.part_id) is None
    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))


def test_interchangeability_group_persistence(db_connection: Connection) -> None:
    org = OrganizationId(uuid4())
    db_connection.execute(
        text(
            "INSERT INTO core_identity.organizations "
            "(organization_id, record_owner_organization_id) VALUES (:org, :org)"
        ),
        {"org": org.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org.value)},
    )

    part_repo = TransactionalPartRepository(connection=db_connection)
    revision_1 = PartRevision(revision_id=TypedId.new("part_revision"), revision_code="A")
    revision_2 = PartRevision(revision_id=TypedId.new("part_revision"), revision_code="A-ALT")
    part_1 = Part(
        part_id=TypedId.new("part"),
        organization_id=org,
        identity=PartIdentity(part_number="PN-200", description="Filtro", manufacturer="Acme"),
        revisions=(revision_1,),
    )
    part_2 = Part(
        part_id=TypedId.new("part"),
        organization_id=org,
        identity=PartIdentity(part_number="PN-201", description="Filtro alt.", manufacturer="Acme"),
        revisions=(revision_2,),
    )
    part_repo.save(part_1)
    part_repo.save(part_2)

    group_repo = TransactionalInterchangeabilityGroupRepository(connection=db_connection)
    group = InterchangeabilityGroup(
        group_id=TypedId.new("interchangeability_group"),
        organization_id=org,
        member_part_revisions=(revision_1.revision_id, revision_2.revision_id),
    )
    group_repo.save(group)

    saved_group = group_repo.get_by_id(group.group_id)
    assert saved_group is not None
    assert saved_group.member_part_revisions == (revision_1.revision_id, revision_2.revision_id)
    assert saved_group.interchanges_with(revision_1.revision_id) == (revision_2.revision_id,)

    updated_part_1 = part_1.join_interchangeability_group(group.group_id)
    part_repo.update(updated_part_1)
    reloaded_part_1 = part_repo.get_by_id(part_1.part_id)
    assert reloaded_part_1 is not None
    assert reloaded_part_1.interchangeability_group_ref == group.group_id
