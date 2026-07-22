import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine

from packages.core_application import OptimisticConcurrencyConflict
from packages.core_domain import Organization
from packages.core_infrastructure.persistence import (
    DomainEventRepository,
    OrganizationRepository,
    set_local_organization_context,
)
from tests.integration.test_domain_events_postgresql import _event, _reference

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)


def test_two_concurrent_changes_accept_one_and_reject_the_stale_version() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    organization = Organization.create()
    aggregate = _reference("registro", organization.organization_id)
    barrier = Barrier(2)

    try:
        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            OrganizationRepository(connection).add(organization)
            DomainEventRepository(connection).append(
                _event(
                    organization_id=organization.organization_id,
                    aggregate=aggregate,
                    version=1,
                )
            )

        def append_competing_change() -> str:
            try:
                with engine.begin() as connection:
                    set_local_organization_context(connection, organization.organization_id)
                    barrier.wait(timeout=5)
                    DomainEventRepository(connection).append(
                        _event(
                            organization_id=organization.organization_id,
                            aggregate=aggregate,
                            version=2,
                        )
                    )
                return "ACEITA"
            except OptimisticConcurrencyConflict as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: append_competing_change(), range(2)))

        assert sorted(results) == ["ACEITA", "VERSAO_DE_AGREGADO_CONFLITANTE"]
        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            timeline = DomainEventRepository(connection).list_for_aggregate(aggregate)
            assert [event.aggregate_version for event in timeline] == [1, 2]
    finally:
        engine.dispose()
