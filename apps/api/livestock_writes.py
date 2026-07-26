"""Escrita das entidades que o Marco 10 deixou fora da API (Marco 12).

Propriedade, lote pecuário, veterinário e movimentação existiam no domínio, com
serviço e persistência completos, e nenhuma rota. Só a semeadura e os testes os
alcançavam.

**Não há rota de remoção de animal do lote por DELETE.** Remover fecha a vigência
do vínculo e acrescenta um fato; o vínculo anterior permanece. Um DELETE
prometeria apagar o que o domínio preserva.
"""

import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from apps.api.geodata_dependencies import car_lookup_opcional
from apps.api.livestock_dependencies import (
    ConnectionDependency,
    operation_context,
    require_permission,
    typed_id_or_problem,
)
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_application.relation_service import RelationService
from packages.core_domain import OrganizationContext
from packages.core_domain.evidence import ConfidenceTier
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.core_infrastructure.persistence.relations import TransactionalRelationRepository
from packages.livestock_application.authorization import (
    ANIMAL_REGISTRAR_GENEALOGIA,
    ANIMAL_REGISTRAR_SAIDA,
    LOT_CRIAR,
    MOVEMENT_REGISTRAR,
    PROPERTY_CRIAR,
    PROPERTY_REGISTRAR_GEOMETRIA,
    REPRODUCTION_REGISTRAR,
    VETERINARIAN_CRIAR,
)
from packages.livestock_application.event_recorder import LivestockEventRecorder
from packages.livestock_application.exit_service import AnimalExitService
from packages.livestock_application.external_counterparty_service import ExternalCounterpartyService
from packages.livestock_application.geometry_service import PropertyGeometryService
from packages.livestock_application.imported_fact_service import ImportedLivestockFactService
from packages.livestock_application.lot_service import LotService
from packages.livestock_application.movement_service import MovementService
from packages.livestock_application.parentage_service import ParentageService
from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_application.reproduction_service import (
    CriaDeclarada,
    ReproductionService,
    StayBasedPropertyReader,
)
from packages.livestock_application.transfer_artifact_service import (
    ReceivedTransferArtifactService,
)
from packages.livestock_application.veterinarian_service import VeterinarianService
from packages.livestock_domain.animal import AnimalSex, BirthOutcome, VerificationStatus
from packages.livestock_domain.exit import ExitType
from packages.livestock_domain.external_counterparty import CounterpartyType
from packages.livestock_domain.geometry import (
    CAMADA_PERIMETRO,
    SRID_CANONICO,
    GeometrySource,
)
from packages.livestock_domain.lot import LotType
from packages.livestock_domain.parentage import (
    ROLE_BY_RELATION_TYPE,
    ParentageConfidence,
    ParentageRole,
    confidence_from_tier,
)
from packages.livestock_domain.reproduction import GestationalAgeBasis
from packages.livestock_infrastructure.geodata import (
    CarNaoEncontrado,
    GeodataIndisponivel,
    GeodataNaoConfigurado,
)
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.exit_repository import (
    TransactionalAnimalExitRepository,
)
from packages.livestock_infrastructure.persistence.external_counterparty_repository import (
    TransactionalExternalCounterpartyRepository,
)
from packages.livestock_infrastructure.persistence.geometry_repository import (
    TransactionalPropertyGeometryRepository,
)
from packages.livestock_infrastructure.persistence.imported_fact_repository import (
    TransactionalImportedLivestockFactRepository,
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
from packages.livestock_infrastructure.persistence.reproduction_repository import (
    TransactionalReproductiveEventRepository,
)
from packages.livestock_infrastructure.persistence.transfer_artifact_repository import (
    TransactionalReceivedTransferArtifactRepository,
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
    contexto: Annotated[OrganizationContext, Depends(require_permission(PROPERTY_CRIAR))],
    connection: ConnectionDependency,
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
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_CRIAR))],
    connection: ConnectionDependency,
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
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_CRIAR))],
    connection: ConnectionDependency,
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
    contexto: Annotated[OrganizationContext, Depends(require_permission(LOT_CRIAR))],
    connection: ConnectionDependency,
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
    contexto: Annotated[OrganizationContext, Depends(require_permission(VETERINARIAN_CRIAR))],
    connection: ConnectionDependency,
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
    contexto: Annotated[OrganizationContext, Depends(require_permission(VETERINARIAN_CRIAR))],
    connection: ConnectionDependency,
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
    contexto: Annotated[OrganizationContext, Depends(require_permission(MOVEMENT_REGISTRAR))],
    connection: ConnectionDependency,
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


class RegistrarContraparteExternaRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    counterparty_type: CounterpartyType
    identifiers: list[str] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=500)
    evidence_references: list[str] = Field(default_factory=list)


class ContraparteExternaResponse(BaseModel):
    counterparty_id: str
    name: str
    counterparty_type: str
    identifiers: list[str]
    notes: str | None


def _contraparte_response(contraparte: Any) -> ContraparteExternaResponse:
    return ContraparteExternaResponse(
        counterparty_id=str(contraparte.counterparty_id.value),
        name=contraparte.name,
        counterparty_type=contraparte.counterparty_type.value,
        identifiers=list(contraparte.identifiers),
        notes=contraparte.notes,
    )


@router.post(
    "/external-counterparties",
    response_model=ContraparteExternaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar uma contraparte externa local",
    responses=RESPOSTAS_PADRAO,
)
def registrar_contraparte_externa(
    corpo: RegistrarContraparteExternaRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_REGISTRAR_SAIDA))],
    connection: ConnectionDependency,
) -> ContraparteExternaResponse:
    servico = ExternalCounterpartyService(
        repository=TransactionalExternalCounterpartyRepository(connection=connection),
        recorder=_recorder(connection),
    )
    try:
        contraparte = servico.register_counterparty(
            context=operation_context(contexto),
            name=corpo.name,
            counterparty_type=corpo.counterparty_type,
            identifiers=tuple(corpo.identifiers),
            notes=corpo.notes,
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
    except ValueError as error:
        raise _conflito(error) from error

    return _contraparte_response(contraparte)


class RegistrarSaidaRequest(BaseModel):
    exit_type: ExitType
    occurred_at: datetime
    reason: str | None = Field(default=None, max_length=500)
    destination: str | None = Field(default=None, max_length=255)
    destination_counterparty_id: str | None = None
    evidence_references: list[str] = Field(default_factory=list)


class SaidaResponse(BaseModel):
    exit_id: str
    animal_id: str
    exit_type: str
    occurred_at: datetime
    reason: str | None
    destination: str | None
    destination_counterparty_id: str | None


class RegistrarArtefatoTransferenciaRequest(BaseModel):
    source_counterparty_id: str
    bundle_digest: str = Field(min_length=1, max_length=128)
    bundle_issued_at: datetime
    transfer_effective_at: datetime
    coverage_known_from: datetime | None = None
    coverage_known_until: datetime | None = None
    issuer_name: str | None = Field(default=None, max_length=255)


class LacunaTransferenciaResponse(BaseModel):
    code: str
    starts_at: datetime | None
    ends_at: datetime | None
    description: str


class CoberturaTransferenciaResponse(BaseModel):
    known_from: datetime | None
    known_until: datetime | None
    gaps: list[LacunaTransferenciaResponse]


class ArtefatoTransferenciaResponse(BaseModel):
    artifact_id: str
    animal_id: str
    source_counterparty_id: str
    bundle_digest: str
    bundle_issued_at: datetime
    transfer_effective_at: datetime
    issuer_name: str | None
    coverage: CoberturaTransferenciaResponse


class RegistrarFatoImportadoRequest(BaseModel):
    source_artifact_id: str
    fact_type: str = Field(min_length=1, max_length=120)
    occurred_at: datetime
    asserted_by: str = Field(min_length=1, max_length=255)
    confidence_tier: ConfidenceTier
    payload: dict[str, Any] = Field(default_factory=dict)


class FatoImportadoResponse(BaseModel):
    imported_fact_id: str
    animal_id: str
    source_artifact_id: str
    fact_type: str
    occurred_at: datetime
    asserted_by: str
    received_by: str
    origin: str
    confidence_tier: str
    payload: dict[str, Any]
    imported_at: datetime


def _artefato_transferencia_response(artefato: Any) -> ArtefatoTransferenciaResponse:
    return ArtefatoTransferenciaResponse(
        artifact_id=str(artefato.artifact_id.value),
        animal_id=str(artefato.animal_id.value),
        source_counterparty_id=str(artefato.source_counterparty_id.value),
        bundle_digest=artefato.bundle_digest,
        bundle_issued_at=artefato.bundle_issued_at,
        transfer_effective_at=artefato.transfer_effective_at,
        issuer_name=artefato.issuer_name,
        coverage=CoberturaTransferenciaResponse(
            known_from=artefato.coverage.known_from,
            known_until=artefato.coverage.known_until,
            gaps=[
                LacunaTransferenciaResponse(
                    code=gap.code.value,
                    starts_at=gap.starts_at,
                    ends_at=gap.ends_at,
                    description=gap.description,
                )
                for gap in artefato.coverage.gaps
            ],
        ),
    )


def _fato_importado_response(fato: Any) -> FatoImportadoResponse:
    return FatoImportadoResponse(
        imported_fact_id=str(fato.imported_fact_id.value),
        animal_id=str(fato.animal_id.value),
        source_artifact_id=str(fato.source_artifact_id.value),
        fact_type=fato.fact_type,
        occurred_at=fato.occurred_at,
        asserted_by=fato.asserted_by,
        received_by=str(fato.received_by.value),
        origin=fato.origin.value,
        confidence_tier=fato.confidence_tier.value,
        payload=dict(fato.payload),
        imported_at=fato.imported_at,
    )


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
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_REGISTRAR_SAIDA))],
    connection: ConnectionDependency,
) -> SaidaResponse:
    servico = AnimalExitService(
        exit_repository=TransactionalAnimalExitRepository(connection=connection),
        animal_repository=TransactionalAnimalRepository(connection=connection),
        recorder=_recorder(connection),
        counterparty_repository=TransactionalExternalCounterpartyRepository(connection=connection),
    )
    try:
        saida = servico.register_exit(
            context=operation_context(contexto),
            animal_id=typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id"),
            exit_type=corpo.exit_type,
            occurred_at=corpo.occurred_at,
            reason=corpo.reason,
            destination=corpo.destination,
            destination_counterparty_id=(
                None
                if corpo.destination_counterparty_id is None
                else typed_id_or_problem(
                    corpo.destination_counterparty_id,
                    entity_type="external_counterparty",
                    campo="destination_counterparty_id",
                )
            ),
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
        raise _nao_encontrado("Animal ou contraparte") from error
    except ValueError as error:
        raise _conflito(error) from error

    return SaidaResponse(
        exit_id=str(saida.exit_id.value),
        animal_id=str(saida.animal_id.value),
        exit_type=saida.exit_type.value,
        occurred_at=saida.occurred_at,
        reason=saida.reason,
        destination=saida.destination,
        destination_counterparty_id=(
            None
            if saida.destination_counterparty_id is None
            else str(saida.destination_counterparty_id.value)
        ),
    )


@router.post(
    "/animals/{animal_id}/received-transfer-artifacts",
    response_model=ArtefatoTransferenciaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar artefato recebido de transferência de custódia",
    responses=RESPOSTAS_PADRAO,
)
def registrar_artefato_transferencia(
    animal_id: str,
    corpo: RegistrarArtefatoTransferenciaRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_REGISTRAR_SAIDA))],
    connection: ConnectionDependency,
) -> ArtefatoTransferenciaResponse:
    servico = ReceivedTransferArtifactService(
        repository=TransactionalReceivedTransferArtifactRepository(connection=connection),
        animal_repository=TransactionalAnimalRepository(connection=connection),
        counterparty_repository=TransactionalExternalCounterpartyRepository(connection=connection),
        recorder=_recorder(connection),
    )
    try:
        artefato = servico.register_received_artifact(
            context=operation_context(contexto),
            animal_id=typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id"),
            source_counterparty_id=typed_id_or_problem(
                corpo.source_counterparty_id,
                entity_type="external_counterparty",
                campo="source_counterparty_id",
            ),
            bundle_digest=corpo.bundle_digest,
            bundle_issued_at=corpo.bundle_issued_at,
            transfer_effective_at=corpo.transfer_effective_at,
            coverage_known_from=corpo.coverage_known_from,
            coverage_known_until=corpo.coverage_known_until,
            issuer_name=corpo.issuer_name,
        )
    except KeyError as error:
        raise _nao_encontrado("Animal ou contraparte") from error
    except ValueError as error:
        raise _conflito(error) from error

    return _artefato_transferencia_response(artefato)


@router.post(
    "/animals/{animal_id}/imported-facts",
    response_model=FatoImportadoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar fato importado de artefato recebido",
    responses=RESPOSTAS_PADRAO,
)
def registrar_fato_importado(
    animal_id: str,
    corpo: RegistrarFatoImportadoRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ANIMAL_REGISTRAR_SAIDA))],
    connection: ConnectionDependency,
) -> FatoImportadoResponse:
    servico = ImportedLivestockFactService(
        repository=TransactionalImportedLivestockFactRepository(connection=connection),
        artifact_repository=TransactionalReceivedTransferArtifactRepository(connection=connection),
        animal_repository=TransactionalAnimalRepository(connection=connection),
        recorder=_recorder(connection),
    )
    try:
        fato = servico.record_imported_fact(
            context=operation_context(contexto),
            animal_id=typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id"),
            source_artifact_id=typed_id_or_problem(
                corpo.source_artifact_id,
                entity_type="received_transfer_artifact",
                campo="source_artifact_id",
            ),
            fact_type=corpo.fact_type,
            occurred_at=corpo.occurred_at,
            asserted_by=corpo.asserted_by,
            confidence_tier=corpo.confidence_tier,
            payload=corpo.payload,
        )
    except KeyError as error:
        raise _nao_encontrado("Animal ou artefato") from error
    except ValueError as error:
        raise _conflito(error) from error

    return _fato_importado_response(fato)


# -- Genealogia --------------------------------------------------------------


class RegistrarMaternidadeRequest(BaseModel):
    genetic_mother_id: str = Field(description="A doadora do óvulo, que define a linhagem.")
    occurred_at: datetime
    confidence: ParentageConfidence
    gestational_mother_id: str | None = Field(
        default=None,
        description=(
            "A receptora, quando houver transferência de embrião. Ausente, entende-se "
            "que a doadora também gestou — e as duas relações são gravadas assim mesmo, "
            "porque ausência se declara e não se infere."
        ),
    )
    confidence_reason: str | None = Field(default=None, max_length=500)


class RegistrarPaternidadeRequest(BaseModel):
    father_id: str
    occurred_at: datetime
    confidence: ParentageConfidence
    confidence_reason: str | None = Field(default=None, max_length=500)


class ParentescoResponse(BaseModel):
    relation_id: str
    offspring_id: str
    parent_id: str
    role: str
    confidence: str
    confidence_reason: str


def _parentesco(relacao: Any) -> ParentescoResponse:
    return ParentescoResponse(
        relation_id=str(relacao.relation_id.value),
        offspring_id=str(relacao.target_reference.target_id.value),
        parent_id=str(relacao.source_reference.target_id.value),
        role=ROLE_BY_RELATION_TYPE[relacao.relation_type].value,
        confidence=str(confidence_from_tier(relacao.confidence.tier)),
        confidence_reason=relacao.confidence.reason,
    )


def _parentage_service(connection: Connection) -> ParentageService:
    return ParentageService(
        relation_service=RelationService(
            repository=TransactionalRelationRepository(connection=connection)
        ),
        animal_repository=TransactionalAnimalRepository(connection=connection),
        recorder=_recorder(connection),
    )


@router.post(
    "/animals/{animal_id}/maternity",
    response_model=list[ParentescoResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Registrar a maternidade de um animal",
    description=(
        "Grava **duas** relações: a maternidade genética e a gestacional. Sem "
        "transferência de embrião as duas apontam para a mesma vaca, e ainda assim "
        "as duas são registradas — deixar a gestacional implícita obrigaria toda "
        "consulta futura a inferir. A árvore genealógica sobe pela genética; a "
        "receptora responde pelo histórico reprodutivo."
    ),
    responses=RESPOSTAS_PADRAO,
)
def registrar_maternidade(
    animal_id: str,
    corpo: RegistrarMaternidadeRequest,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(ANIMAL_REGISTRAR_GENEALOGIA))
    ],
    connection: ConnectionDependency,
) -> list[ParentescoResponse]:
    try:
        genetica, gestacional = _parentage_service(connection).register_maternity(
            context=operation_context(contexto),
            offspring_id=typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id"),
            genetic_mother_id=typed_id_or_problem(
                corpo.genetic_mother_id, entity_type="animal", campo="genetic_mother_id"
            ),
            gestational_mother_id=(
                None
                if corpo.gestational_mother_id is None
                else typed_id_or_problem(
                    corpo.gestational_mother_id,
                    entity_type="animal",
                    campo="gestational_mother_id",
                )
            ),
            occurred_at=corpo.occurred_at,
            confidence=corpo.confidence,
            confidence_reason=corpo.confidence_reason,
        )
    except KeyError as error:
        raise _nao_encontrado("Animal") from error
    except ValueError as error:
        raise _conflito(error) from error

    return [_parentesco(genetica), _parentesco(gestacional)]


@router.post(
    "/animals/{animal_id}/paternity",
    response_model=ParentescoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar a paternidade de um animal",
    description=(
        "O pai é opcional e admite mais de um vínculo simultâneo — é o caso do "
        "touro do lote, em que a monta natural teve vários reprodutores e a "
        "paternidade só se resolve por exame de DNA. Vários pais só são aceitos "
        "quando **todos** os vínculos são DECLARADO: admitir um segundo ao lado de "
        "um vínculo documentado transformaria prova em palpite."
    ),
    responses=RESPOSTAS_PADRAO,
)
def registrar_paternidade(
    animal_id: str,
    corpo: RegistrarPaternidadeRequest,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(ANIMAL_REGISTRAR_GENEALOGIA))
    ],
    connection: ConnectionDependency,
) -> ParentescoResponse:
    try:
        relacao = _parentage_service(connection).register_parentage(
            context=operation_context(contexto),
            offspring_id=typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id"),
            parent_id=typed_id_or_problem(corpo.father_id, entity_type="animal", campo="father_id"),
            role=ParentageRole.PAI,
            occurred_at=corpo.occurred_at,
            confidence=corpo.confidence,
            confidence_reason=corpo.confidence_reason,
        )
    except KeyError as error:
        raise _nao_encontrado("Animal") from error
    except ValueError as error:
        raise _conflito(error) from error

    return _parentesco(relacao)


# -- Reprodução --------------------------------------------------------------


class CriaRequest(BaseModel):
    outcome: BirthOutcome
    sex: AnimalSex = AnimalSex.UNKNOWN
    breed: str | None = Field(default=None, max_length=100)


class RegistrarPartoRequest(BaseModel):
    dam_id: str = Field(description="A mãe. Quem pare é fêmea.")
    occurred_at: datetime
    offspring: list[CriaRequest] = Field(min_length=1)
    sire_id: str | None = None
    birth_property_id: str | None = Field(
        default=None,
        description=(
            "Só é usada quando a permanência da mãe não for determinável. Se houver "
            "permanência conhecida e ela divergir desta, o registro é recusado — a "
            "contradição precisa ser corrigida conscientemente."
        ),
    )
    confidence: ParentageConfidence = ParentageConfidence.DECLARADO
    gestational_age_days: int | None = Field(default=None, gt=0)
    gestational_age_basis: GestationalAgeBasis = GestationalAgeBasis.UNKNOWN
    notes: str | None = Field(default=None, max_length=1000)


class RegistrarAbortoRequest(BaseModel):
    dam_id: str
    occurred_at: datetime
    gestational_age_days: int | None = Field(default=None, gt=0)
    gestational_age_basis: GestationalAgeBasis = GestationalAgeBasis.UNKNOWN
    notes: str | None = Field(default=None, max_length=1000)


class CriaResponse(BaseModel):
    animal_id: str
    outcome: str
    sex: str
    birth_property_id: str | None
    birth_property_source: str


class EventoReprodutivoResponse(BaseModel):
    event_id: str
    dam_id: str
    sire_id: str | None
    event_type: str
    occurred_at: datetime
    gestational_age_days: int | None
    gestational_age_basis: str
    offspring: list[CriaResponse]


def _reproduction_service(connection: Connection) -> ReproductionService:
    return ReproductionService(
        event_repository=TransactionalReproductiveEventRepository(connection=connection),
        animal_repository=TransactionalAnimalRepository(connection=connection),
        parentage_service=_parentage_service(connection),
        stay_reader=StayBasedPropertyReader(
            stay_repository=TransactionalPropertyStayRepository(connection=connection)
        ),
        recorder=_recorder(connection),
    )


def _evento_reprodutivo(evento: Any, animais: dict[str, Any]) -> EventoReprodutivoResponse:
    return EventoReprodutivoResponse(
        event_id=str(evento.event_id.value),
        dam_id=str(evento.dam_id.value),
        sire_id=None if evento.sire_id is None else str(evento.sire_id.value),
        event_type=evento.event_type.value,
        occurred_at=evento.occurred_at,
        gestational_age_days=evento.gestational_age_days,
        gestational_age_basis=evento.gestational_age_basis.value,
        offspring=[
            CriaResponse(
                animal_id=str(cria.animal_id.value),
                outcome=cria.outcome.value,
                sex=animais[str(cria.animal_id.value)].sex.value,
                birth_property_id=(
                    None
                    if animais[str(cria.animal_id.value)].birth_property_id is None
                    else str(animais[str(cria.animal_id.value)].birth_property_id.value)
                ),
                birth_property_source=animais[
                    str(cria.animal_id.value)
                ].birth_property_source.value,
            )
            for cria in evento.offspring
        ],
    )


@router.post(
    "/reproductive-events/parturitions",
    response_model=EventoReprodutivoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar um parto",
    description=(
        "Cria o evento, **cada cria** e a linhagem de todas na mesma transação. "
        "Registrar o bezerro e depois declarar de quem ele é deixa uma janela em "
        "que o animal existe sem linhagem.\n\n"
        "O parto gemelar é **um** evento com várias crias, cada qual com o seu "
        "resultado: uma pode nascer viva e a outra ser natimorta, e é o vínculo "
        "obstétrico entre as duas que explica o caso.\n\n"
        "O natimorto é criado como indivíduo rastreável e **não** recebe registro "
        "de saída — `MORTE` afirmaria que nasceu vivo e morreu depois."
    ),
    responses=RESPOSTAS_PADRAO,
)
def registrar_parto(
    corpo: RegistrarPartoRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(REPRODUCTION_REGISTRAR))],
    connection: ConnectionDependency,
) -> EventoReprodutivoResponse:
    try:
        registrado = _reproduction_service(connection).register_parturition(
            context=operation_context(contexto),
            dam_id=typed_id_or_problem(corpo.dam_id, entity_type="animal", campo="dam_id"),
            occurred_at=corpo.occurred_at,
            offspring=tuple(
                CriaDeclarada(outcome=cria.outcome, sex=cria.sex, breed=cria.breed)
                for cria in corpo.offspring
            ),
            sire_id=(
                None
                if corpo.sire_id is None
                else typed_id_or_problem(corpo.sire_id, entity_type="animal", campo="sire_id")
            ),
            birth_property_id=(
                None
                if corpo.birth_property_id is None
                else typed_id_or_problem(
                    corpo.birth_property_id,
                    entity_type="rural_property",
                    campo="birth_property_id",
                )
            ),
            confidence=corpo.confidence,
            gestational_age_days=corpo.gestational_age_days,
            gestational_age_basis=corpo.gestational_age_basis,
            notes=corpo.notes,
        )
    except KeyError as error:
        raise _nao_encontrado("Animal") from error
    except ValueError as error:
        raise _conflito(error) from error

    return _evento_reprodutivo(
        registrado.event, {str(a.animal_id.value): a for a in registrado.animals}
    )


@router.post(
    "/reproductive-events/pregnancy-losses",
    response_model=EventoReprodutivoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar uma perda gestacional",
    description=(
        "O aborto encerra a gestação e **não cria animal**: criar um indivíduo com "
        "estado morto para um produto de gestação sem identidade atribuível seria "
        "fabricar entidade a partir de um fato que não a produziu.\n\n"
        "A idade gestacional é opcional; ausente significa desconhecida, nunca zero. "
        "A classificação em precoce ou tardio é derivada por regra versionada, e "
        "nunca informada como fato primário."
    ),
    responses=RESPOSTAS_PADRAO,
)
def registrar_perda_gestacional(
    corpo: RegistrarAbortoRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(REPRODUCTION_REGISTRAR))],
    connection: ConnectionDependency,
) -> EventoReprodutivoResponse:
    try:
        evento = _reproduction_service(connection).register_pregnancy_loss(
            context=operation_context(contexto),
            dam_id=typed_id_or_problem(corpo.dam_id, entity_type="animal", campo="dam_id"),
            occurred_at=corpo.occurred_at,
            gestational_age_days=corpo.gestational_age_days,
            gestational_age_basis=corpo.gestational_age_basis,
            notes=corpo.notes,
        )
    except KeyError as error:
        raise _nao_encontrado("Animal") from error
    except ValueError as error:
        raise _conflito(error) from error

    return _evento_reprodutivo(evento, {})


# -- Geometria da propriedade ------------------------------------------------


class RegistrarGeometriaRequest(BaseModel):
    source: GeometrySource
    layer: str = Field(
        default=CAMADA_PERIMETRO,
        max_length=60,
        description=(
            "O que esta geometria e: o perimetro do imovel, a reserva legal, uma "
            "APP. Camadas nao sao versoes umas das outras — cada uma tem a sua."
        ),
    )
    srid: int = Field(
        default=SRID_CANONICO,
        gt=0,
        description=(
            "Sistema de referência do material enviado. Coordenada sem SRID conhecido "
            "não localiza nada, e adivinhá-lo produziria interseção falsa. O Titan "
            "transforma para 4326 e preserva o original."
        ),
    )
    geojson: dict[str, Any] = Field(
        description="Polygon ou MultiPolygon. Ponto não é limite de propriedade."
    )
    external_reference: str | None = Field(default=None, max_length=120)
    captured_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class GeometriaResponse(BaseModel):
    geometry_id: str
    property_id: str
    source: str
    layer: str
    srid: int
    source_digest: str
    external_reference: str | None
    version: int
    captured_at: datetime | None
    imported_at: datetime


def _geometria_servico(connection: Connection) -> PropertyGeometryService:
    """O provider é opcional: sem configuração, só a importação do CAR falha."""
    return PropertyGeometryService(
        geometry_repository=TransactionalPropertyGeometryRepository(connection=connection),
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        recorder=_recorder(connection),
        car_lookup=car_lookup_opcional(),
    )


def _geometria(registro: Any) -> GeometriaResponse:
    return GeometriaResponse(
        geometry_id=str(registro.geometry_id.value),
        property_id=str(registro.property_id.value),
        source=registro.source.value,
        layer=registro.layer,
        srid=registro.srid,
        source_digest=registro.source_digest,
        external_reference=registro.external_reference,
        version=registro.version,
        captured_at=registro.captured_at,
        imported_at=registro.imported_at,
    )


@router.post(
    "/properties/{property_id}/geometry",
    response_model=GeometriaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar a geometria de uma propriedade",
    description=(
        "**Nunca substitui.** Cada registro cria uma versão nova, e a anterior "
        "permanece — é ela que faz uma avaliação antiga continuar reproduzível "
        "depois de o CAR ser retificado.\n\n"
        "Geometria topologicamente inválida é **recusada**, com o motivo, e não "
        "reparada em silêncio: reparo é derivado novo, com método e diferenças "
        "declarados.\n\n"
        "A resposta traz o digest do material, e não o polígono — quem quiser o "
        "limite consulta a rota de leitura, que exige permissão própria."
    ),
    responses=RESPOSTAS_PADRAO,
)
def registrar_geometria(
    property_id: str,
    corpo: RegistrarGeometriaRequest,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(PROPERTY_REGISTRAR_GEOMETRIA))
    ],
    connection: ConnectionDependency,
) -> GeometriaResponse:
    try:
        geometria = _geometria_servico(connection).register_geometry(
            context=operation_context(contexto),
            property_id=typed_id_or_problem(
                property_id, entity_type="rural_property", campo="property_id"
            ),
            source=corpo.source,
            source_payload=json.dumps(corpo.geojson, separators=(",", ":"), sort_keys=True),
            srid=corpo.srid,
            layer=corpo.layer,
            external_reference=corpo.external_reference,
            captured_at=corpo.captured_at,
            notes=corpo.notes,
        )
    except KeyError as error:
        raise _nao_encontrado("Propriedade") from error
    except ValueError as error:
        raise _conflito(error) from error

    return _geometria(geometria)


class CamadaRecusadaResponse(BaseModel):
    layer: str
    motivo: str


class ImportacaoResponse(BaseModel):
    """O que entrou e o que nao entrou — as duas coisas visiveis."""

    gravadas: list[GeometriaResponse]
    recusadas: list[CamadaRecusadaResponse]


class ImportarCarRequest(BaseModel):
    cod_imovel: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=2, max_length=2)
    notes: str | None = Field(default=None, max_length=1000)
    incluir_camadas: bool = Field(
        default=True,
        description=(
            "Traz tambem reserva legal, APP, hidrografia e o que mais o CAR "
            "declarar sobre o imovel. Cada camada e versionada por si."
        ),
    )


@router.post(
    "/properties/{property_id}/geometry/import-car",
    response_model=ImportacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Importar o imovel a partir do CAR",
    description=(
        "Traz o poligono do provider e o guarda como versao nova, com o que veio "
        "junto: municipio, area, modulos fiscais e a data da ultima atualizacao "
        "do cadastro. "
        "`captured_at` recebe a data de atualizacao do CAR, e **nao** a da "
        "importacao. Ha cadastro em uso com dado de anos atras, e confundir os "
        "dois faria a avaliacao parecer mais fresca do que e. "
        "**Nada do que vem e interpretado como conformidade.** A condicao do "
        "cadastro diz onde ele esta na fila do SICAR, e nao se a propriedade esta "
        "regular. O Titan tambem nao infere titularidade a partir de coordenadas: "
        "o codigo informado pode ser de outro imovel, e o registro diz apenas que "
        "alguem o informou.\n\n"
        "**Camada invalida nao derruba a importacao.** Dado oficial contem "
        "geometria degenerada; o que nao pode ser admitido volta em `recusadas`, "
        "com o motivo. So o perimetro invalido faz a operacao falhar."
    ),
    responses=RESPOSTAS_PADRAO,
)
def importar_geometria_do_car(
    property_id: str,
    corpo: ImportarCarRequest,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(PROPERTY_REGISTRAR_GEOMETRIA))
    ],
    connection: ConnectionDependency,
) -> ImportacaoResponse:
    try:
        resultado = _geometria_servico(connection).import_from_car(
            context=operation_context(contexto),
            property_id=typed_id_or_problem(
                property_id, entity_type="rural_property", campo="property_id"
            ),
            cod_imovel=corpo.cod_imovel,
            state=corpo.state,
            notes=corpo.notes,
            incluir_camadas=corpo.incluir_camadas,
        )
    except CarNaoEncontrado as error:
        raise _nao_encontrado("Imovel no CAR") from error
    except GeodataNaoConfigurado as error:
        raise DomainProblem(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            reason_code="PROVIDER_NAO_CONFIGURADO",
            title="Consulta ao CAR indisponivel",
            detail=str(error),
        ) from error
    except GeodataIndisponivel as error:
        raise DomainProblem(
            status_code=status.HTTP_502_BAD_GATEWAY,
            reason_code="PROVIDER_INDISPONIVEL",
            title="O provider de geodados nao respondeu",
            detail=str(error),
        ) from error
    except KeyError as error:
        raise _nao_encontrado("Propriedade") from error
    except ValueError as error:
        raise _conflito(error) from error

    return ImportacaoResponse(
        gravadas=[_geometria(g) for g in resultado.gravadas],
        recusadas=[
            CamadaRecusadaResponse(layer=r.layer, motivo=r.motivo) for r in resultado.recusadas
        ],
    )
