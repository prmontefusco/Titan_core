"""Cadastra propriedade e animais fictícios, só para teste manual local.

Diferente de `apps.seed` (que cria Organizations/usuários próprios de
demonstração), este script grava direto na Organization de uso configurada em
`apps/web/.env.local` -- é para quem já está logado e quer ter algo para
buscar/clicar na tela, sem esperar por uma tela de cadastro que ainda não
existe no produto.

Mesma composição de serviço que `apps/api/livestock_animals.py` usa por trás
de `POST /v1/livestock/animals` (repositório + `LivestockEventRecorder`),
sem passar pela API HTTP -- não há como autenticar como o usuário real sem a
senha dele, e não deveria haver.

Uso:
    $env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
    $env:TITAN_SEED_TEST_ORGANIZATION_ID = "9ddb2b8b-2fed-48d4-b5ed-a0d308994dbc"
    $env:TITAN_SEED_TEST_ACTOR_ID = "<user_id de quem aparece como autor>"
    python -m uv run --locked python -m apps.seed_test_livestock_data
"""

import os
from uuid import UUID

from packages.core_infrastructure.persistence import set_local_organization_context
from packages.core_infrastructure.persistence.database import (
    DatabaseSettings,
    create_database_engine,
)
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.livestock_application.animal_service import AnimalService
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_domain.animal import AnimalSex, IdentifierType
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.shared_kernel import OrganizationId, SystemClock, TypedId

CODIGO_PROPRIEDADE = "FAZ-TESTE"


def _obrigatoria(nome: str) -> str:
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise SystemExit(f"Defina {nome} antes de rodar este script.")
    return valor


def main() -> None:
    organization_id = OrganizationId.parse(_obrigatoria("TITAN_SEED_TEST_ORGANIZATION_ID"))
    actor_id = TypedId("user", UUID(_obrigatoria("TITAN_SEED_TEST_ACTOR_ID")))

    engine = create_database_engine(DatabaseSettings.from_environment())
    with engine.begin() as connection:
        set_local_organization_context(connection, organization_id)

        context = LivestockOperationContext.create(
            organization_id=organization_id,
            actor_id=actor_id,
            source_id=TypedId.new("script"),
        )
        recorder = LivestockEventRecorder(
            event_log=DomainEventRepository(connection=connection), clock=SystemClock()
        )

        property_repository = TransactionalRuralPropertyRepository(connection=connection)
        property_service = RuralPropertyService(repository=property_repository, recorder=recorder)
        propriedade = property_repository.get_by_code(organization_id, CODIGO_PROPRIEDADE)
        if propriedade is None:
            propriedade = property_service.register_property(
                context=context,
                code=CODIGO_PROPRIEDADE,
                name="Fazenda de Teste",
                municipality="Uberaba",
                state_code="MG",
            )
            print(f"Propriedade criada: {propriedade.property_id.value} ({CODIGO_PROPRIEDADE})")
        else:
            print(f"Propriedade já existia, reusada: {propriedade.property_id.value}")

        animal_service = AnimalService(
            repository=TransactionalAnimalRepository(connection=connection), recorder=recorder
        )
        novos: list[tuple[AnimalSex, str, IdentifierType, str]] = [
            (AnimalSex.FEMALE, "Nelore", IdentifierType.OFFICIAL_SISBOV, "BR000000000001"),
            (AnimalSex.MALE, "Nelore", IdentifierType.OFFICIAL_SISBOV, "BR000000000002"),
            (AnimalSex.FEMALE, "Girolando", IdentifierType.EAR_TAG, "BR000000000003"),
        ]
        for sex, breed, identifier_type, identifier_value in novos:
            animal = animal_service.register_animal(
                context=context,
                birth_property_id=propriedade.property_id,
                sex=sex,
                breed=breed,
                initial_identifier_type=identifier_type,
                initial_identifier_value=identifier_value,
            )
            print(f"Animal criado: {animal.animal_id.value} ({identifier_value}, {sex.value})")


if __name__ == "__main__":
    main()
