"""Transformação industrial — abate com fan-out real (ADR-0046, Passo 11.2).

Uma única rota, de escrita: registrar `TransformationEvent(SLAUGHTER)` a partir
de um animal já com saída ABATE registrada, produzindo duas ou mais saídas
rastreáveis. Consulta de `TraceableItem` (dossiê, timeline, recall) fica para o
Passo 11.3/11.5 — nenhuma delas existe ainda, deliberadamente.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
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
from packages.core_application.relation_service import RelationService
from packages.core_domain import OrganizationContext
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.core_infrastructure.persistence.relations import TransactionalRelationRepository
from packages.livestock_application.authorization import TRANSFORMATION_REGISTRAR
from packages.livestock_application.event_recorder import LivestockEventRecorder
from packages.livestock_application.transformation_service import (
    AnimalJaTransformado,
    AnimalNaoAbatido,
    SlaughterOutputSpec,
    SlaughterResult,
    SlaughterService,
)
from packages.livestock_domain.transformation import TraceableItemType
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.exit_repository import (
    TransactionalAnimalExitRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.livestock_infrastructure.persistence.transformation_repository import (
    TransactionalTraceableItemRepository,
    TransactionalTransformationEventRepository,
)
from packages.shared_kernel import SystemClock, UniversalReference

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


class SaidaDeAbateRequest(BaseModel):
    item_type: TraceableItemType
    quantity: str | None = Field(
        default=None, description="Quantidade decimal, como texto (ex.: '215.400')."
    )
    unit: str = ""
    measurement_basis: str | None = None
    label: str | None = None


class RegistrarAbateRequest(BaseModel):
    animal_id: str
    facility_property_id: str
    occurred_at: datetime = Field(description="Instante da transformação, em UTC.")
    outputs: list[SaidaDeAbateRequest] = Field(min_length=2)
    evidence_ids: list[str] = Field(default_factory=list)


class ItemRastreavelResponse(BaseModel):
    item_id: str
    item_type: TraceableItemType
    label: str | None


class TransformacaoResponse(BaseModel):
    transformation_id: str
    process_type: str
    occurred_at: datetime
    animal_id: str
    facility_property_id: str
    created_items: list[ItemRastreavelResponse]


def _servico(connection: Connection) -> SlaughterService:
    return SlaughterService(
        event_repository=TransactionalTransformationEventRepository(connection=connection),
        item_repository=TransactionalTraceableItemRepository(connection=connection),
        animal_repository=TransactionalAnimalRepository(connection=connection),
        exit_repository=TransactionalAnimalExitRepository(connection=connection),
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        relation_service=RelationService(
            repository=TransactionalRelationRepository(connection=connection)
        ),
        recorder=LivestockEventRecorder(
            event_log=DomainEventRepository(connection=connection), clock=SystemClock()
        ),
    )


def _quantidade_ou_problema(bruto: str | None, campo: str) -> Decimal | None:
    if bruto is None:
        return None
    try:
        return Decimal(bruto)
    except InvalidOperation as error:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="QUANTIDADE_INVALIDA",
            title="Quantidade inválida",
            detail=f"O campo {campo} deve conter um número decimal.",
        ) from error


def _evidencias(contexto: OrganizationContext, ids: list[str]) -> tuple[UniversalReference, ...]:
    return tuple(
        UniversalReference(
            target_id=typed_id_or_problem(bruto, entity_type="evidence", campo="evidence_ids"),
            organization_id=contexto.organization_id,
            contract_version=1,
        )
        for bruto in ids
    )


def _resposta(
    resultado: SlaughterResult, animal_id: str, facility_property_id: str
) -> TransformacaoResponse:
    return TransformacaoResponse(
        transformation_id=str(resultado.event.event_id.value),
        process_type=resultado.event.process_type.value,
        occurred_at=resultado.event.occurred_at,
        animal_id=animal_id,
        facility_property_id=facility_property_id,
        created_items=[
            ItemRastreavelResponse(
                item_id=str(item.item_id.value), item_type=item.item_type, label=item.label
            )
            for item in resultado.created_items
        ],
    )


@router.post(
    "/transformations/slaughter",
    response_model=TransformacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar transformação de abate (fan-out)",
    description=(
        "Registra um `TransformationEvent(SLAUGHTER)`: consome um animal com "
        "saída ABATE já registrada e produz duas ou mais saídas rastreáveis "
        "(ADR-0046, Passo 11.2). O animal e o frigorífico precisam pertencer à "
        "mesma Organization — o caso inter-organizacional segue o protocolo da "
        "ADR-0042 e não é coberto por esta rota."
    ),
    responses=RESPOSTAS_PADRAO,
)
def registrar_abate(
    corpo: RegistrarAbateRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TRANSFORMATION_REGISTRAR))],
    connection: ConnectionDependency,
) -> TransformacaoResponse:
    outputs = tuple(
        SlaughterOutputSpec(
            item_type=saida.item_type,
            quantity=_quantidade_ou_problema(saida.quantity, "outputs.quantity"),
            unit=saida.unit,
            measurement_basis=saida.measurement_basis,
            label=saida.label,
        )
        for saida in corpo.outputs
    )

    try:
        resultado = _servico(connection).register_slaughter(
            context=operation_context(contexto),
            animal_id=typed_id_or_problem(corpo.animal_id, entity_type="animal", campo="animal_id"),
            facility_property_id=typed_id_or_problem(
                corpo.facility_property_id,
                entity_type="rural_property",
                campo="facility_property_id",
            ),
            occurred_at=corpo.occurred_at,
            outputs=outputs,
            evidence_references=_evidencias(contexto, corpo.evidence_ids),
        )
    except KeyError as error:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail="Animal ou propriedade não encontrados nesta organização.",
        ) from error
    except (AnimalNaoAbatido, AnimalJaTransformado, ValueError) as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operação recusada pelo domínio",
            detail=str(error),
        ) from error

    return _resposta(resultado, corpo.animal_id, corpo.facility_property_id)
