"""Teste de integração PostgreSQL com RLS para `SLIContract` (A3, Titan Asset)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.asset_domain.sustainment_contract import (
    SLA,
    ContractScope,
    ContractVersion,
    CoverageLine,
    KnownValidInterval,
    ServiceLimits,
    SLIContract,
)
from packages.asset_infrastructure.persistence.sustainment_contract_repository import (
    TransactionalSLIContractRepository,
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


def test_sli_contract_persistence_amendment_and_rls(db_connection: Connection) -> None:
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

    repo = TransactionalSLIContractRepository(connection=db_connection)
    part_ref = TypedId.new("part")
    version_1 = ContractVersion(
        version_no=1,
        effective=KnownValidInterval(
            valid_from=datetime(2026, 1, 1, tzinfo=UTC),
            known_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        coverage_lines=(
            CoverageLine(
                scope=ContractScope.VEHICLE,
                scope_value="VEH-001",
                covered_services=("PREVENTIVE", "CORRECTIVE"),
                excluded_parts=(part_ref,),
            ),
        ),
        response_sla=SLA(
            duration=timedelta(hours=4),
            clock_start_event="failure_reported",
            clock_stop_event="technician_dispatched",
        ),
        availability_target_percentage=Decimal("95.5"),
        service_limits=ServiceLimits(max_services_per_period=2, period_days=30),
    )
    contract = SLIContract(
        contract_id=TypedId.new("sli_contract"),
        organization_id=org_1,
        customer_ref=TypedId.new("customer"),
        versions=(version_1,),
    )
    repo.save(contract)

    saved = repo.get_by_id(contract.contract_id)
    assert saved is not None
    assert len(saved.versions) == 1
    assert saved.versions[0].response_sla is not None
    assert saved.versions[0].response_sla.duration == timedelta(hours=4)
    assert saved.versions[0].availability_target_percentage == Decimal("95.5")
    assert saved.versions[0].coverage_lines[0].excluded_parts == (part_ref,)
    assert saved.versions[0].service_limits == ServiceLimits(
        max_services_per_period=2, period_days=30
    )

    # Cenário E (constituição §41): contrato emendado depois que uma WO já
    # abriu — resolução histórica não muda.
    opened_at = datetime(2026, 3, 1, tzinfo=UTC)
    resolved_before_amendment = saved.resolve_version_at(opened_at)
    assert resolved_before_amendment is not None
    assert resolved_before_amendment.version_no == 1

    version_2 = version_1.__class__(
        version_no=2,
        effective=KnownValidInterval(
            valid_from=datetime(2026, 6, 1, tzinfo=UTC),
            known_at=datetime(2026, 6, 1, tzinfo=UTC),
        ),
        coverage_lines=version_1.coverage_lines,
        amendment_ref=TypedId.new("contract_amendment"),
    )
    amended = saved.issue_version(version_2)
    repo.update(amended)

    reloaded = repo.get_by_id(contract.contract_id)
    assert reloaded is not None
    assert len(reloaded.versions) == 2
    assert reloaded.current_version_no == 2

    resolved_after_amendment = reloaded.resolve_version_at(opened_at)
    assert resolved_after_amendment is not None
    assert resolved_after_amendment.version_no == 1

    resolved_now = reloaded.resolve_version_at(datetime(2026, 7, 1, tzinfo=UTC))
    assert resolved_now is not None
    assert resolved_now.version_no == 2
    assert resolved_now.amendment_ref == version_2.amendment_ref

    role_name = f"titan_rls_sli_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    for table in ("sli_contracts", "contract_versions", "contract_version_coverage_lines"):
        db_connection.execute(text(f"GRANT ALL ON core_audit.{table} TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )
    repo_2 = TransactionalSLIContractRepository(connection=db_connection)
    assert repo_2.get_by_id(contract.contract_id) is None
    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
