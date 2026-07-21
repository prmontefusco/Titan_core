import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine

from packages.core_application import CorrectionService
from packages.core_domain import ChangeKind, Organization
from packages.core_infrastructure.persistence import (
    DomainEventRepository,
    OrganizationRepository,
    set_local_organization_context,
)
from packages.shared_kernel import TypedId
from tests.integration.test_domain_events_postgresql import _event, _reference

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)


def test_persisted_timeline_preserves_original_and_appends_correction() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    organization = Organization.create()
    aggregate = _reference("registro", organization.organization_id)
    original = _event(
        organization_id=organization.organization_id,
        aggregate=aggregate,
        version=1,
    )

    try:
        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            OrganizationRepository(connection).add(organization)
            repository = DomainEventRepository(connection)
            repository.append(original)
            original_snapshot = repository.list_for_aggregate(aggregate)[0]

            correction = CorrectionService(repository).correct(
                correction_event_id=TypedId.new("domain_event"),
                original=original,
                aggregate_version=2,
                change_kind=ChangeKind.CORRECAO_DE_ERRO,
                justification="Informação original incorreta.",
                new_content={"versao": 2},
                corrected_at=datetime(2026, 7, 21, 22, 0, tzinfo=UTC),
                actor_reference=_reference("actor", organization.organization_id),
                source_reference=_reference("source", organization.organization_id),
                correlation_id=TypedId.new("correlation"),
            )

            timeline = repository.list_for_aggregate(aggregate)
            assert [item.event_type for item in timeline] == [
                "registro_criado",
                "registro_corrigido",
            ]
            assert timeline[0] == original_snapshot
            assert timeline[1].causation_id == original.event_id
            assert timeline[1].previous_hash == timeline[0].current_hash
            assert correction.event.aggregate_version == 2
    finally:
        engine.dispose()
