"""PostgreSQL tests for Commercial Passport property population resolution."""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text

from packages.core_domain import Organization
from packages.core_infrastructure.persistence import (
    OrganizationRepository,
    set_local_organization_context,
)
from packages.livestock_application.commercial_passport import (
    CommercialOpportunity,
    CommercialOpportunityKind,
    CommercialPassportContext,
)
from packages.livestock_infrastructure.persistence.commercial_passport import (
    TransactionalPropertyCommercialPassportReadinessPipeline,
)
from packages.shared_kernel import TypedId

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL nao configurada para teste PostgreSQL.",
)

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


def test_commercial_passport_population_uses_property_stays_at_reference_time() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                organization = Organization.create()
                set_local_organization_context(connection, organization.organization_id)
                OrganizationRepository(connection).add(organization)

                target_property = _insert_property(connection, organization.organization_id.value)
                origin_property = _insert_property(connection, organization.organization_id.value)
                other_property = _insert_property(connection, organization.organization_id.value)

                born_at_target_without_stays = _insert_animal(
                    connection,
                    organization.organization_id.value,
                    target_property,
                    created_at=NOW - timedelta(days=30),
                )
                transferred_in = _insert_animal(
                    connection,
                    organization.organization_id.value,
                    origin_property,
                    created_at=NOW - timedelta(days=30),
                )
                transferred_out = _insert_animal(
                    connection,
                    organization.organization_id.value,
                    target_property,
                    created_at=NOW - timedelta(days=30),
                )
                known_after_cutoff = _insert_animal(
                    connection,
                    organization.organization_id.value,
                    origin_property,
                    created_at=NOW - timedelta(days=30),
                )

                _insert_stay(
                    connection,
                    organization_id=organization.organization_id.value,
                    animal_id=transferred_in,
                    property_id=target_property,
                    start_time=NOW - timedelta(days=2),
                    end_time=None,
                    source_movement_id=_insert_movement(
                        connection,
                        organization_id=organization.organization_id.value,
                        origin_property_id=origin_property,
                        destination_property_id=target_property,
                        animal_id=transferred_in,
                        movement_time=NOW - timedelta(days=2),
                        created_at=NOW - timedelta(days=2),
                    ),
                )
                _insert_stay(
                    connection,
                    organization_id=organization.organization_id.value,
                    animal_id=transferred_out,
                    property_id=target_property,
                    start_time=NOW - timedelta(days=20),
                    end_time=NOW - timedelta(days=1),
                    source_movement_id=None,
                )
                _insert_stay(
                    connection,
                    organization_id=organization.organization_id.value,
                    animal_id=transferred_out,
                    property_id=other_property,
                    start_time=NOW - timedelta(days=1),
                    end_time=None,
                    source_movement_id=_insert_movement(
                        connection,
                        organization_id=organization.organization_id.value,
                        origin_property_id=target_property,
                        destination_property_id=other_property,
                        animal_id=transferred_out,
                        movement_time=NOW - timedelta(days=1),
                        created_at=NOW - timedelta(days=1),
                    ),
                )
                _insert_stay(
                    connection,
                    organization_id=organization.organization_id.value,
                    animal_id=known_after_cutoff,
                    property_id=target_property,
                    start_time=NOW - timedelta(days=2),
                    end_time=None,
                    source_movement_id=_insert_movement(
                        connection,
                        organization_id=organization.organization_id.value,
                        origin_property_id=origin_property,
                        destination_property_id=target_property,
                        animal_id=known_after_cutoff,
                        movement_time=NOW - timedelta(days=2),
                        created_at=NOW + timedelta(days=1),
                    ),
                )

                pipeline = TransactionalPropertyCommercialPassportReadinessPipeline(
                    connection=connection,
                    opportunity=_opportunity(),
                )
                context = CommercialPassportContext(
                    organization_id=organization.organization_id,
                    property_id=TypedId("rural_property", target_property),
                    reference_time=NOW,
                    knowledge_cutoff=NOW,
                    evaluated_at=NOW,
                )

                assert set(pipeline._active_animals_for_property(context)) == {
                    TypedId("animal", born_at_target_without_stays),
                    TypedId("animal", transferred_in),
                }
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def _opportunity() -> CommercialOpportunity:
    return CommercialOpportunity(
        code="commercial-passport-population-test",
        kind=CommercialOpportunityKind.MARKET,
        name="Commercial Passport Population Test",
        purpose="commercial-passport-population-test",
        policy_id=TypedId.new("policy"),
        policy_version=1,
    )


def _insert_property(connection: object, organization_id: UUID) -> UUID:
    property_id = uuid4()
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.rural_properties (
                property_id, record_owner_organization_id, code, name,
                municipality, state_code, created_at
            ) VALUES (
                :property_id, :organization_id, :code,
                'Commercial Passport Population Property', 'Campo Grande', 'MS', :created_at
            )
            """
        ),
        {
            "property_id": property_id,
            "organization_id": organization_id,
            "code": f"CP-POP-{uuid4().hex}",
            "created_at": NOW - timedelta(days=60),
        },
    )
    return property_id


def _insert_animal(
    connection: object,
    organization_id: UUID,
    property_id: UUID,
    *,
    created_at: datetime,
) -> UUID:
    animal_id = uuid4()
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.animals (
                animal_id,
                record_owner_organization_id,
                birth_property_id,
                sex,
                breed,
                birth_date,
                birth_outcome,
                birth_property_source,
                version,
                created_at
            ) VALUES (
                :animal_id,
                :organization_id,
                :property_id,
                'MALE',
                'Nelore',
                NULL,
                'NASCIDO_VIVO',
                'DECLARED',
                1,
                :created_at
            )
            """
        ),
        {
            "animal_id": animal_id,
            "organization_id": organization_id,
            "property_id": property_id,
            "created_at": created_at,
        },
    )
    return animal_id


def _insert_movement(
    connection: object,
    *,
    organization_id: UUID,
    origin_property_id: UUID,
    destination_property_id: UUID,
    animal_id: UUID,
    movement_time: datetime,
    created_at: datetime,
) -> UUID:
    movement_id = uuid4()
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.animal_movements (
                movement_id,
                record_owner_organization_id,
                origin_property_id,
                destination_property_id,
                movement_time,
                reason,
                evidence_reference,
                created_at
            ) VALUES (
                :movement_id,
                :organization_id,
                :origin_property_id,
                :destination_property_id,
                :movement_time,
                'commercial-passport-population-test',
                NULL,
                :created_at
            )
            """
        ),
        {
            "movement_id": movement_id,
            "organization_id": organization_id,
            "origin_property_id": origin_property_id,
            "destination_property_id": destination_property_id,
            "movement_time": movement_time,
            "created_at": created_at,
        },
    )
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.animal_movement_items (
                movement_id,
                animal_id,
                record_owner_organization_id
            ) VALUES (
                :movement_id,
                :animal_id,
                :organization_id
            )
            """
        ),
        {
            "movement_id": movement_id,
            "animal_id": animal_id,
            "organization_id": organization_id,
        },
    )
    return movement_id


def _insert_stay(
    connection: object,
    *,
    organization_id: UUID,
    animal_id: UUID,
    property_id: UUID,
    start_time: datetime,
    end_time: datetime | None,
    source_movement_id: UUID | None,
) -> None:
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.property_stays (
                stay_id,
                record_owner_organization_id,
                animal_id,
                property_id,
                start_time,
                end_time,
                status,
                source_movement_id
            ) VALUES (
                :stay_id,
                :organization_id,
                :animal_id,
                :property_id,
                :start_time,
                :end_time,
                :status,
                :source_movement_id
            )
            """
        ),
        {
            "stay_id": uuid4(),
            "organization_id": organization_id,
            "animal_id": animal_id,
            "property_id": property_id,
            "start_time": start_time,
            "end_time": end_time,
            "status": "ACTIVE" if end_time is None else "CLOSED",
            "source_movement_id": source_movement_id,
        },
    )
