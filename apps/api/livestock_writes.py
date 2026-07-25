"""Escrita das entidades que o Marco 10 deixou fora da API (Marco 12).

Propriedade, lote pecuário, veterinário e movimentação existiam no domínio, com
serviço e persistência completos, e nenhuma rota. Só a semeadura e os testes os
alcançavam.

**Não há rota de remoção de animal do lote por DELETE.** Remover fecha a vigência
do vínculo e acrescenta um fato; o vínculo anterior permanece. Um DELETE
prometeria apagar o que o domínio preserva.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from apps.api.livestock_dependencies import (
    ConnectionDependency,
    operation_context,
    require_permission,
    typed_id_or_problem,
)
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_domain import OrganizationContext
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.livestock_application.authorization import (
    ANIMAL_REGISTRAR_SAIDA,
    LOT_CRIAR,
    MOVEMENT_REGISTRAR,
    PROPERTY_CRIAR,
    VETERINARIAN_CRIAR,
)
from packages.livestock_application.event_recorder import LivestockEventRecorder
from packages.livestock_application.exit_service import AnimalExitService
from packages.livestock_application.lot_service import LotService
from packages.livestock_application.movement_service import MovementService
from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_application.veterinarian_service import VeterinarianService
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.exit import ExitType
from packages.livestock_domain.lot import LotType
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.exit_repository import (
    TransactionalAnimalExitRepository,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLivestockLotRepository,
    TransactionalLotMembershipRepository,
)
from packages.livestock_infrastructure.persistence.movement_repository import (
    TransactionalAnimalMovementRepository,
    TransactionalPropertyStayRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
)
from packages.shared_kernel import SystemClock, UniversalReference

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


def _recorder(connection: Connection) -> LivestockEventRecorder:
    return LivestockEventRecorder(
        event_log=DomainEventRepository(connection=connection), clock=SystemClock()
    )


def _conflito(error: Exception) -> DomainProblem:
    return DomainProblem(
        status_code=status.HTTP_409_CONFLICT,
        reason_code="CONFLITO_DE_DOMINIO",
        title="Operação recusada pelo domínio",
        detail=str(error),
    )


def _nao_encontrado(o_que: str) -> DomainProblem:
    return DomainProblem(
        status_code=status.HTTP_404_NOT_FOUND,
        reason_code="RECURSO_NAO_ENCONTRADO",
        title="Recurso não encontrado",
        detail=f"{o_que} não encontrado nesta organização.",
    )


# -- Propriedade rural -------------------------------------------------------


class RegistrarPropriedadeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    municipality: str = Field(min_length=1, max_length=255)
    state_code: str = Field(min_length=2, max_length=2)
    registration_number: str | None = None
    total_area_hectares: float | None = Field(default=None, gt=0)


class PropriedadeCriadaResponse(BaseModel):
    property_id: str
    code: str
    name: str


@router.post(
    "/properties",
    response_model=PropriedadeCriadaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar uma propriedade rural",
    responses=RESPOSTAS_PADRAO,
)
def registrar_propriedade(
    corpo: RegistrarPropriedadeRequest,
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_CRIAR))],
) -> PropriedadeCriadaResponse:
    servico = RuralPropertyService(
        repository=TransactionalRuralPropertyRepository(connection=connection),
        recorder=_recorder(connection),
    )
    try:
        propriedade = servico.register_property(
            context=operation_context(contexto),
            code=corpo.code,
            name=corpo.name,
            municipality=corpo.municipality,
            state_code=corpo.state_code,
            registration_number=corpo.registration_number,
            total_area_hectares=corpo.total_area_hectares,
        )
    except ValueError as error:
        raise _conflito(error) from error

    return PropriedadeCriadaResponse(
        property_id=str(propriedade.property_id.value),
        code=propriedade.code,
        name=propriedade.name,
    )


# -- Lote pecuário -----------------------------------------------------------


class CriarLoteRequest(BaseModel):
    property_id: str
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    lot_type: LotType = LotType.OPERATIONAL


class LoteCriadoResponse(BaseModel):
    lot_id: str
    code: str
    lot_type: str


class MembroDoLoteRequest(BaseModel):
    animal_id: str
    reason: str | None = None


class VinculoResponse(BaseModel):
    membership_id: str
    lot_id: str
    animal_id: str
    valid_from: datetime
    valid_until: datetime | None


def _lote_servico(connection: Connection) -> LotService:
    return LotService(
        lot_repository=TransactionalLivestockLotRepository(connection=connection),
        membership_repository=TransactionalLotMembershipRepository(connection=connection),
        animal_repository=TransactionalAnimalRepository(connection=connection),
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        recorder=_recorder(connection),
    )


@router.post(
    "/lots",
    response_model=LoteCriadoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar um lote de animais",
    responses=RESPOSTAS_PADRAO,
)
def criar_lote(
    corpo: CriarLoteRequest,
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_CRIAR))],
) -> LoteCriadoResponse:
    try:
        lote = _lote_servico(connection).create_lot(
            context=operation_context(contexto),
            property_id=typed_id_or_problem(
                corpo.property_id, entity_type="rural_property", campo="property_id"
            ),
            code=corpo.code,
            name=corpo.name,
            lot_type=corpo.lot_type,
        )
    except KeyError as error:
        raise _nao_encontrado("Propriedade") from error
    except ValueError as error:
        raise _conflito(error) from error

    return LoteCriadoResponse(
        lot_id=str(lote.lot_id.value), code=lote.code, lot_type=lote.lot_type.value
    )


@router.post(
    "/lots/{lot_id}/members",
    response_model=VinculoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Incluir um animal no lote",
    description=(
        "Lotes operacionais são exclusivos: um animal não pode estar em dois ao "
        "mesmo tempo. Lotes sanitários admitem sobreposição."
    ),
    responses=RESPOSTAS_PADRAO,
)
def incluir_no_lote(
    lot_id: str,
    corpo: MembroDoLoteRequest,
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_CRIAR))],
) -> VinculoResponse:
    try:
        vinculo = _lote_servico(connection).add_animal_to_lot(
            operation_context(contexto),
            typed_id_or_problem(lot_id, entity_type="livestock_lot", campo="lot_id"),
            typed_id_or_problem(corpo.animal_id, entity_type="animal", campo="animal_id"),
            reason=corpo.reason,
        )
    except KeyError as error:
        raise _nao_encontrado("Lote ou animal") from error
    except ValueError as error:
        raise _conflito(error) from error

    return VinculoResponse(
        membership_id=str(vinculo.membership_id.value),
        lot_id=str(vinculo.lot_id.value),
        animal_id=str(vinculo.animal_id.value),
        valid_from=vinculo.valid_from,
        valid_until=vinculo.valid_until,
    )


@router.post(
    "/lots/{lot_id}/removals",
    response_model=VinculoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Encerrar a permanência de um animal no lote",
    description=(
        "Fecha a vigência do vínculo e acrescenta um fato. O vínculo anterior "
        "permanece na história — por isso a rota é POST, e não DELETE."
    ),
    responses=RESPOSTAS_PADRAO,
)
def remover_do_lote(
    lot_id: str,
    corpo: MembroDoLoteRequest,
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_CRIAR))],
) -> VinculoResponse:
    try:
        vinculo = _lote_servico(connection).remove_animal_from_lot(
            operation_context(contexto),
            typed_id_or_problem(lot_id, entity_type="livestock_lot", campo="lot_id"),
            typed_id_or_problem(corpo.animal_id, entity_type="animal", campo="animal_id"),
        )
    except KeyError as error:
        raise _nao_encontrado("Lote, animal ou vínculo ativo") from error
    except ValueError as error:
        raise _conflito(error) from error

    return VinculoResponse(
        membership_id=str(vinculo.membership_id.value),
        lot_id=str(vinculo.lot_id.value),
        animal_id=str(vinculo.animal_id.value),
        valid_from=vinculo.valid_from,
        valid_until=vinculo.valid_until,
    )


# -- Veterinário -------------------------------------------------------------


class RegistrarVeterinarioRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    cpf: str = Field(min_length=11, max_length=14)
    council_number: str = Field(min_length=1, max_length=50)
    council_state: str = Field(min_length=2, max_length=2)


class PromoverVeterinarioRequest(BaseModel):
    new_status: VerificationStatus
    evidence_reference: str | None = None


class VeterinarioResponse(BaseModel):
    veterinarian_id: str
    name: str
    verification_status: str


@router.post(
    "/veterinarians",
    response_model=VeterinarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar um veterinário",
    description="O CPF é usado para impedir duplicidade e não é devolvido em consulta.",
    responses=RESPOSTAS_PADRAO,
)
def registrar_veterinario(
    corpo: RegistrarVeterinarioRequest,
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(VETERINARIAN_CRIAR))],
) -> VeterinarioResponse:
    servico = VeterinarianService(
        repository=TransactionalVeterinarianRepository(connection=connection),
        recorder=_recorder(connection),
    )
    try:
        vet = servico.register_veterinarian(
            context=operation_context(contexto),
            name=corpo.name,
            cpf=corpo.cpf,
            council_number=corpo.council_number,
            council_state=corpo.council_state,
        )
    except ValueError as error:
        raise _conflito(error) from error

    return VeterinarioResponse(
        veterinarian_id=str(vet.veterinarian_id.value),
        name=vet.name,
        verification_status=vet.verification_status.value,
    )


@router.post(
    "/veterinarians/{veterinarian_id}/verification",
    response_model=VeterinarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Atualizar a verificação de um veterinário",
    description=(
        "Só quem está DOCUMENTADO ou VERIFICADO_EM_FONTE pode emitir prescrição. "
        "Cada promoção fica registrada com o status que a antecedeu."
    ),
    responses=RESPOSTAS_PADRAO,
)
def atualizar_verificacao(
    veterinarian_id: str,
    corpo: PromoverVeterinarioRequest,
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(VETERINARIAN_CRIAR))],
) -> VeterinarioResponse:
    servico = VeterinarianService(
        repository=TransactionalVeterinarianRepository(connection=connection),
        recorder=_recorder(connection),
    )
    try:
        vet = servico.update_verification_status(
            operation_context(contexto),
            typed_id_or_problem(
                veterinarian_id, entity_type="veterinarian", campo="veterinarian_id"
            ),
            corpo.new_status,
            evidence_reference=corpo.evidence_reference,
        )
    except KeyError as error:
        raise _nao_encontrado("Veterinário") from error
    except ValueError as error:
        raise _conflito(error) from error

    return VeterinarioResponse(
        veterinarian_id=str(vet.veterinarian_id.value),
        name=vet.name,
        verification_status=vet.verification_status.value,
    )


# -- Movimentação ------------------------------------------------------------


class RegistrarMovimentacaoRequest(BaseModel):
    origin_property_id: str
    destination_property_id: str
    movement_time: datetime
    animal_ids: list[str] = Field(min_length=1)
    reason: str | None = None
    evidence_reference: str | None = None


class MovimentacaoResponse(BaseModel):
    movement_id: str
    origin_property_id: str
    destination_property_id: str
    movement_time: datetime
    animal_ids: list[str]


@router.post(
    "/movements",
    response_model=MovimentacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar uma movimentação de animais",
    description=(
        "Uma movimentação é um fato só, ainda que mova muitos animais. As "
        "permanências de cada animal são atualizadas na mesma transação."
    ),
    responses=RESPOSTAS_PADRAO,
)
def registrar_movimentacao(
    corpo: RegistrarMovimentacaoRequest,
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MOVEMENT_REGISTRAR))],
) -> MovimentacaoResponse:
    servico = MovementService(
        movement_repository=TransactionalAnimalMovementRepository(connection=connection),
        stay_repository=TransactionalPropertyStayRepository(connection=connection),
        animal_repository=TransactionalAnimalRepository(connection=connection),
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        recorder=_recorder(connection),
    )
    try:
        movimentacao = servico.register_movement(
            context=operation_context(contexto),
            origin_property_id=typed_id_or_problem(
                corpo.origin_property_id,
                entity_type="rural_property",
                campo="origin_property_id",
            ),
            destination_property_id=typed_id_or_problem(
                corpo.destination_property_id,
                entity_type="rural_property",
                campo="destination_property_id",
            ),
            movement_time=corpo.movement_time,
            animal_ids=tuple(
                typed_id_or_problem(bruto, entity_type="animal", campo="animal_ids")
                for bruto in corpo.animal_ids
            ),
            reason=corpo.reason,
            evidence_reference=corpo.evidence_reference,
        )
    except KeyError as error:
        raise _nao_encontrado("Propriedade ou animal") from error
    except ValueError as error:
        raise _conflito(error) from error

    return MovimentacaoResponse(
        movement_id=str(movimentacao.movement_id.value),
        origin_property_id=str(movimentacao.origin_property_id.value),
        destination_property_id=str(movimentacao.destination_property_id.value),
        movement_time=movimentacao.movement_time,
        animal_ids=[str(a.value) for a in movimentacao.animal_ids],
    )


# -- Saída do rebanho --------------------------------------------------------


class RegistrarSaidaRequest(BaseModel):
    exit_type: ExitType
    occurred_at: datetime
    reason: str | None = Field(default=None, max_length=500)
    destination: str | None = Field(default=None, max_length=255)
    evidence_references: list[str] = Field(default_factory=list)


class SaidaResponse(BaseModel):
    exit_id: str
    animal_id: str
    exit_type: str
    occurred_at: datetime
    reason: str | None
    destination: str | None


@router.post(
    "/animals/{animal_id}/exit",
    response_model=SaidaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar a saída de um animal do rebanho",
    description=(
        "Morte, abate, venda ou transferência definitiva. A saída é terminal: a "
        "segunda tentativa é recusada com 409. Fatos anteriores à data da saída "
        "continuam aceitos — lançar hoje um tratamento da semana passada é "
        "regularização, não contradição."
    ),
    responses=RESPOSTAS_PADRAO,
)
def registrar_saida(
    animal_id: str,
    corpo: RegistrarSaidaRequest,
    connection: ConnectionDependency,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_REGISTRAR_SAIDA))],
) -> SaidaResponse:
    servico = AnimalExitService(
        exit_repository=TransactionalAnimalExitRepository(connection=connection),
        animal_repository=TransactionalAnimalRepository(connection=connection),
        recorder=_recorder(connection),
    )
    try:
        saida = servico.register_exit(
            context=operation_context(contexto),
            animal_id=typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id"),
            exit_type=corpo.exit_type,
            occurred_at=corpo.occurred_at,
            reason=corpo.reason,
            destination=corpo.destination,
            evidence_references=tuple(
                UniversalReference(
                    target_id=typed_id_or_problem(
                        bruto, entity_type="evidence", campo="evidence_references"
                    ),
                    organization_id=contexto.organization_id,
                    contract_version=1,
                )
                for bruto in corpo.evidence_references
            ),
        )
    except KeyError as error:
        raise _nao_encontrado("Animal") from error
    except ValueError as error:
        raise _conflito(error) from error

    return SaidaResponse(
        exit_id=str(saida.exit_id.value),
        animal_id=str(saida.animal_id.value),
        exit_type=saida.exit_type.value,
        occurred_at=saida.occurred_at,
        reason=saida.reason,
        destination=saida.destination,
    )
