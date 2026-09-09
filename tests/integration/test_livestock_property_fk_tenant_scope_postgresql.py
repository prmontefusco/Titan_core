"""ADR-0077: FKs de propriedade carregam Organization para evitar vínculo cruzado."""

import os
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


def test_property_references_reject_cross_organization_ids() -> None:
    url = os.environ.get("TITAN_MIGRATION_DATABASE_URL")
    assert url, "Teste exige TITAN_MIGRATION_DATABASE_URL administrativa."
    engine = create_engine(url)
    try:
        with engine.connect() as connection, connection.begin():
            org_a = uuid4()
            org_b = uuid4()
            property_a = uuid4()
            property_b = uuid4()
            animal_b = uuid4()
            movement_b = uuid4()

            connection.execute(
                text(
                    "INSERT INTO core_identity.organizations "
                    "(organization_id, record_owner_organization_id) "
                    "VALUES (:org_a, :org_a), (:org_b, :org_b)"
                ),
                {"org_a": org_a, "org_b": org_b},
            )
            connection.execute(
                text(
                    "INSERT INTO core_audit.rural_properties "
                    "(property_id, record_owner_organization_id, code, name, municipality, "
                    "state_code, created_at) VALUES "
                    "(:property_a, :org_a, 'FK-A', 'Fazenda A', 'Cuiaba', 'MT', NOW()), "
                    "(:property_b, :org_b, 'FK-B', 'Fazenda B', 'Cuiaba', 'MT', NOW())"
                ),
                {
                    "property_a": property_a,
                    "property_b": property_b,
                    "org_a": org_a,
                    "org_b": org_b,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO core_audit.animals "
                    "(animal_id, record_owner_organization_id, birth_property_id, sex, "
                    "created_at) VALUES (:animal_b, :org_b, :property_b, 'MALE', NOW())"
                ),
                {"animal_b": animal_b, "org_b": org_b, "property_b": property_b},
            )
            connection.execute(
                text("SELECT set_config('titan.organization_id', :org_b, true)"),
                {"org_b": str(org_b)},
            )

            attempts: tuple[tuple[str, dict[str, Any]], ...] = (
                (
                    "INSERT INTO core_audit.animals "
                    "(animal_id, record_owner_organization_id, birth_property_id, sex, "
                    "created_at) VALUES (gen_random_uuid(), :org_b, :property_a, "
                    "'FEMALE', NOW())",
                    {},
                ),
                (
                    "INSERT INTO core_audit.animal_movements "
                    "(movement_id, record_owner_organization_id, origin_property_id, "
                    "destination_property_id, movement_time, created_at) VALUES "
                    "(:movement_b, :org_b, :property_a, :property_b, NOW(), NOW())",
                    {"movement_b": movement_b},
                ),
                (
                    "INSERT INTO core_audit.property_stays "
                    "(stay_id, record_owner_organization_id, animal_id, property_id, "
                    "start_time, status) VALUES "
                    "(gen_random_uuid(), :org_b, :animal_b, :property_a, NOW(), 'ACTIVE')",
                    {"animal_b": animal_b},
                ),
                (
                    "INSERT INTO core_audit.livestock_lots "
                    "(lot_id, record_owner_organization_id, property_id, code, name, "
                    "lot_type, status, created_at) VALUES "
                    "(gen_random_uuid(), :org_b, :property_a, 'LOT-FK', 'Lote FK', "
                    "'OPERATIONAL', 'ACTIVE', NOW())",
                    {},
                ),
            )
            for statement, parameters in attempts:
                with pytest.raises(DBAPIError) as failure, connection.begin_nested():
                    connection.execute(
                        text(statement),
                        {"org_b": org_b, "property_a": property_a, "property_b": property_b}
                        | parameters,
                    )
                assert _sqlstate(failure.value) == "23503"
    finally:
        engine.dispose()
