"""Endpoint-prova da fundação HTTP da vertical (Passo 10.4a).

`POST /v1/livestock/animals` foi escolhido por ser simples o bastante para provar
o encanamento sem envolver motor de regras, avaliação, decisão ou dossiê. O que
ele demonstra é a travessia inteira: autenticação, contexto organizacional,
permissão, serviço de aplicação, transação, RLS, repositório e PostgreSQL.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from apps.api.livestock_dependencies import (
    ConnectionDependency,
    operation_context,
    require_permission,
    typed_id_or_problem,
)
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_application.event_log import DomainEventLog
from packages.core_domain import OrganizationContext
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.livestock_application.animal_service import AnimalService
from packages.livestock_application.authorization import ANIMAL_CRIAR
from packages.livestock_application.event_recorder import LivestockEventRecorder
from packages.livestock_domain.animal import AnimalSex, IdentifierType
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.shared_kernel import SystemClock

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


class RegistrarAnimalRequest(BaseModel):
    birth_property_id: str = Field(description="Identificador da propriedade de nascimento.")
    sex: AnimalSex
    breed: str | None = None
    birth_date: date | None = None
    initial_identifier_type: IdentifierType | None = None
    initial_identifier_value: str | None = Field(default=None, max_length=64)


class AnimalRegistradoResponse(BaseModel):
    animal_id: str
    organization_id: str
    sex: AnimalSex
    breed: str | None
    identifiers: list[str]


@router.post(
    "/animals",
    response_model=AnimalRegistradoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar um animal",
    responses=RESPOSTAS_PADRAO,
)
def registrar_animal(
    corpo: RegistrarAnimalRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_CRIAR))],
    connection: ConnectionDependency,
) -> AnimalRegistradoResponse:
    event_log: DomainEventLog = DomainEventRepository(connection=connection)
    servico = AnimalService(
        repository=TransactionalAnimalRepository(connection=connection),
        recorder=LivestockEventRecorder(event_log=event_log, clock=SystemClock()),
    )

    try:
        animal = servico.register_animal(
            context=operation_context(contexto),
            birth_property_id=typed_id_or_problem(
                corpo.birth_property_id,
                entity_type="rural_property",
                campo="birth_property_id",
            ),
            sex=corpo.sex,
            breed=corpo.breed,
            birth_date=corpo.birth_date,
            initial_identifier_type=corpo.initial_identifier_type,
            initial_identifier_value=corpo.initial_identifier_value,
        )
    except ValueError as error:
        # Duplicidade de identificador oficial é conflito de domínio, não erro do
        # servidor nem entrada malformada: o cliente mandou algo válido que o
        # estado atual recusa.
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operação recusada pelo domínio",
            detail=str(error),
        ) from error

    return AnimalRegistradoResponse(
        animal_id=str(animal.animal_id.value),
        organization_id=str(animal.organization_id.value),
        sex=animal.sex,
        breed=animal.breed,
        identifiers=[tag.identifier_value for tag in animal.identifiers],
    )
