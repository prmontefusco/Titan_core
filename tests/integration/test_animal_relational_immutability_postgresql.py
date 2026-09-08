"""ADR-0076: identidade constitutiva preservada e identificação operacional."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.exc import DBAPIError

from packages.livestock_application.animal_service import AnimalService
from packages.livestock_domain.animal import AnimalSex, IdentifierState, IdentifierType
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_support import in_memory_recorder, operation_context


@pytest.fixture
def animal_connection() -> Iterator[tuple[Connection, OrganizationId, TypedId]]:
    engine = create_engine(os.environ["TITAN_DATABASE_URL"])
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            owner = OrganizationId(uuid4())
            property_id = TypedId.new("rural_property")
            connection.execute(
                text(
                    "INSERT INTO core_identity.organizations "
                    "(organization_id, record_owner_organization_id) VALUES (:id, :id)"
                ),
                {"id": owner.value},
            )
            connection.execute(
                text("SELECT set_config('titan.organization_id', :id, true)"),
                {"id": str(owner.value)},
            )
            connection.execute(
                text(
                    "INSERT INTO core_audit.rural_properties "
                    "(property_id, record_owner_organization_id, code, name, "
                    "municipality, state_code, created_at) "
                    "VALUES (:id, :owner, 'FICTICIA', 'Fazenda ficticia', "
                    "'Cuiaba', 'MT', NOW())"
                ),
                {"id": property_id.value, "owner": owner.value},
            )
            role = f"titan_animal_guard_{uuid4().hex}"
            connection.execute(
                text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOINHERIT NOBYPASSRLS')
            )
            connection.execute(text(f'GRANT USAGE ON SCHEMA core_audit TO "{role}"'))
            connection.execute(
                text(f'GRANT ALL ON core_audit.animals, core_audit.animal_identifiers TO "{role}"')
            )
            # Concessão deliberadamente excessiva e policy temporária: uma falha
            # deve vir do trigger, não de ACL/RLS nem de ausência da linha alvo.
            connection.execute(
                text(
                    "CREATE POLICY animal_guard_test ON core_audit.animals "
                    f'FOR ALL TO "{role}" USING (true) WITH CHECK (true)'
                )
            )
            connection.execute(text(f'SET LOCAL ROLE "{role}"'))
            try:
                yield connection, owner, property_id
            finally:
                # Dados, grants, role e policy são exclusivamente fictícios e
                # pertencem à mesma transação descartável.
                transaction.rollback()
    finally:
        engine.dispose()


def test_identifier_lifecycle_preserves_constitutive_animal_data(
    animal_connection: tuple[Connection, OrganizationId, TypedId],
) -> None:
    connection, owner, property_id = animal_connection
    role = connection.execute(text("SELECT current_user")).scalar_one()
    quoted_role = connection.dialect.identifier_preparer.quote(role)
    connection.execute(text("RESET ROLE"))
    connection.execute(text(f"REVOKE UPDATE ON core_audit.animals FROM {quoted_role}"))
    connection.execute(text(f"GRANT UPDATE (version) ON core_audit.animals TO {quoted_role}"))
    connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    repository = TransactionalAnimalRepository(connection)
    recorder, _ = in_memory_recorder()
    service = AnimalService(repository=repository, recorder=recorder)
    context = operation_context(owner)
    animal = service.register_animal(
        context=context,
        birth_property_id=property_id,
        sex=AnimalSex.MALE,
        breed="Nelore",
    )
    attached = service.attach_identifier(context, animal.animal_id, IdentifierType.EAR_TAG, "F-01")
    deactivated = service.deactivate_identifier(
        context, animal.animal_id, attached.identifiers[0].identifier_id
    )
    loaded = repository.get_by_id(animal.animal_id)
    assert loaded is not None
    assert loaded.version == deactivated.version == animal.version + 2
    assert len(loaded.identifiers) == 1
    assert loaded.identifiers[0].identifier_id == attached.identifiers[0].identifier_id
    assert loaded.identifiers[0].state == IdentifierState.DEACTIVATED
    assert (
        loaded.animal_id,
        loaded.organization_id,
        loaded.birth_property_id,
        loaded.sex,
        loaded.breed,
        loaded.birth_date,
        loaded.birth_outcome,
        loaded.birth_property_source,
        loaded.created_at,
    ) == (
        animal.animal_id,
        animal.organization_id,
        animal.birth_property_id,
        animal.sex,
        animal.breed,
        animal.birth_date,
        animal.birth_outcome,
        animal.birth_property_source,
        animal.created_at,
    )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE core_audit.animals SET animal_id = gen_random_uuid()",
        "UPDATE core_audit.animals SET record_owner_organization_id = gen_random_uuid()",
        "UPDATE core_audit.animals SET birth_property_id = gen_random_uuid()",
        "UPDATE core_audit.animals SET sex = 'FEMALE'",
        "UPDATE core_audit.animals SET breed = 'Alterada'",
        "UPDATE core_audit.animals SET birth_date = DATE '2020-01-01'",
        "UPDATE core_audit.animals SET birth_outcome = 'NATIMORTO'",
        "UPDATE core_audit.animals SET birth_property_source = 'DERIVED_FROM_MATERNAL_STAY'",
        "UPDATE core_audit.animals SET created_at = created_at + INTERVAL '1 day'",
        "UPDATE core_audit.animals SET version = version",
        "UPDATE core_audit.animals SET version = version - 1",
        "UPDATE core_audit.animals SET version = version + 2",
        "DELETE FROM core_audit.animals",
    ],
)
def test_animal_guard_rejects_mutation_even_with_excessive_dml_grants(
    animal_connection: tuple[Connection, OrganizationId, TypedId], statement: str
) -> None:
    connection, owner, property_id = animal_connection
    repository = TransactionalAnimalRepository(connection)
    recorder, _ = in_memory_recorder()
    service = AnimalService(repository=repository, recorder=recorder)
    animal = service.register_animal(
        context=operation_context(owner),
        birth_property_id=property_id,
        sex=AnimalSex.MALE,
        breed="Nelore",
    )
    sql = statement + " WHERE animal_id = :id"
    with pytest.raises(DBAPIError) as failure, connection.begin_nested():
        connection.execute(text(sql), {"id": animal.animal_id.value})
    # Integridade referencial/enum não pode mascarar ausência da proteção.
    assert getattr(failure.value.orig, "sqlstate", None) == "55000"
    assert repository.get_by_id(animal.animal_id) == animal
