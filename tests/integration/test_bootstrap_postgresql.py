import os
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, select

from packages.core_infrastructure.bootstrap import (
    BootstrapOutcome,
    BootstrapResult,
    BootstrapSettings,
    apply_minimum_bootstrap,
    bootstrap_receipts_table,
)
from packages.core_infrastructure.persistence.authorization import permissions_table, roles_table
from packages.core_infrastructure.persistence.memberships import memberships_table
from packages.core_infrastructure.persistence.organizations import organizations_table
from packages.shared_kernel import OrganizationId

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)


def test_minimum_bootstrap_is_idempotent_and_creates_no_authorization_profile() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    settings = BootstrapSettings(
        operator_organization_id=OrganizationId(UUID("10000000-0000-4000-8000-000000000001")),
        authority_actor_id=UUID("10000000-0000-4000-8000-000000000002"),
        environment="TESTE",
    )

    try:
        with engine.connect() as connection:
            authorization_counts_before = tuple(
                connection.execute(select(func.count()).select_from(table)).scalar_one()
                for table in (memberships_table, roles_table, permissions_table)
            )
        first = apply_minimum_bootstrap(engine, settings)
        second = apply_minimum_bootstrap(engine, settings)

        assert first in {
            BootstrapOutcome(BootstrapResult.APLICADO, settings.operator_organization_id),
            BootstrapOutcome(BootstrapResult.JA_APLICADO, settings.operator_organization_id),
        }
        assert second == BootstrapOutcome(
            BootstrapResult.JA_APLICADO, settings.operator_organization_id
        )
        with engine.connect() as connection:
            assert (
                connection.execute(
                    select(func.count())
                    .select_from(organizations_table)
                    .where(
                        organizations_table.c.organization_id
                        == settings.operator_organization_id.value
                    )
                ).scalar_one()
                == 1
            )
            authorization_counts_after = tuple(
                connection.execute(select(func.count()).select_from(table)).scalar_one()
                for table in (memberships_table, roles_table, permissions_table)
            )
            assert authorization_counts_after == authorization_counts_before
            assert (
                connection.execute(
                    select(func.count())
                    .select_from(bootstrap_receipts_table)
                    .where(
                        bootstrap_receipts_table.c.record_owner_organization_id
                        == settings.operator_organization_id.value
                    )
                ).scalar_one()
                == 1
            )
    finally:
        engine.dispose()
