"""Transformação industrial — abate e desossa (ADR-0046, Passos 11.2 e 11.6).

Duas rotas de escrita: registrar `TransformationEvent(SLAUGHTER)` (fan-out
real, a partir de um animal já com saída ABATE registrada) e registrar
`TransformationEvent(DEBONING)` (fan-in real, a partir de duas ou mais
`CARCASS`/`HALF_CARCASS` já produzidas por um `SLAUGHTER` anterior). Consulta
de `TraceableItem` (dossiê, timeline, recall) vive em `livestock_queries.py`.
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
    DeboningInputSpec,
    DeboningResult,
    DeboningService,
    ItemDeTipoInvalido,
    ItemJaConsumido,
    SlaughterResult,
    SlaughterService,
    TransformationOutputSpec,
)
from packages.livestock_domain.transformation import TraceableItemType, TransformationBalance
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


class SaidaTransformacaoRequest(BaseModel):
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
    outputs: list[SaidaTransformacaoRequest] = Field(min_length=2)
    evidence_ids: list[str] = Field(default_factory=list)
    input_quantity: str | None = Field(
        default=None,
        description=(
            "Peso do animal na entrada, como texto decimal (ex.: '480.000'). "
            "Sem ele, o balanço fica NOT_ASSESSED — ADR-0046, Passo 11.4."
        ),
    )
    input_unit: str = ""
    input_measurement_basis: str | None = None
    declared_loss: str | None = Field(
        default=None,
        description="Perda conhecida (sangue, evaporação, descarte), como texto decimal.",
    )
    tolerance: str | None = Field(
        default=None, description="Tolerância aceita para a diferença, como texto decimal."
    )


class ItemRastreavelResponse(BaseModel):
    item_id: str
    item_type: TraceableItemType
    label: str | None


class BalancoResponse(BaseModel):
    status: str
    result: str
    measurement_basis: str | None
    input_total: str | None
    output_total: str | None
    declared_loss: str | None
    unaccounted_quantity: str | None
    tolerance: str | None
    reasons: list[str]


class TransformacaoResponse(BaseModel):
    transformation_id: str
    process_type: str
    occurred_at: datetime
    animal_id: str
    facility_property_id: str
    created_items: list[ItemRastreavelResponse]
    balance: BalancoResponse


class EntradaDeDesossaRequest(BaseModel):
    item_id: str
    quantity: str | None = Field(
        default=None, description="Quantidade decimal, como texto (ex.: '150.000')."
    )
    unit: str = ""
    measurement_basis: str | None = None


class RegistrarDesossaRequest(BaseModel):
    facility_property_id: str
    occurred_at: datetime = Field(description="Instante da transformação, em UTC.")
    inputs: list[EntradaDeDesossaRequest] = Field(min_length=2)
    outputs: list[SaidaTransformacaoRequest] = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    declared_loss: str | None = Field(
        default=None,
        description="Perda conhecida (sangue, evaporação, descarte), como texto decimal.",
    )
    tolerance: str | None = Field(
        default=None, description="Tolerância aceita para a diferença, como texto decimal."
    )


class DesossaResponse(BaseModel):
    transformation_id: str
    process_type: str
    occurred_at: datetime
    facility_property_id: str
    input_item_ids: list[str]
    created_items: list[ItemRastreavelResponse]
    balance: BalancoResponse


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


def _servico_desossa(connection: Connection) -> DeboningService:
    return DeboningService(
        event_repository=TransactionalTransformationEventRepository(connection=connection),
        item_repository=TransactionalTraceableItemRepository(connection=connection),
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


def _texto_ou_none(valor: Decimal | None) -> str | None:
    return None if valor is None else str(valor)


def _balanco_resposta(balance: TransformationBalance | None) -> BalancoResponse:
    if balance is None:
        # SlaughterService sempre calcula um balanço (ao menos NOT_ASSESSED);
        # este ramo é só defensivo, para o mapeamento nunca inventar um número.
        return BalancoResponse(
            status="NOT_ASSESSED",
            result="NOT_APPLICABLE",
            measurement_basis=None,
            input_total=None,
            output_total=None,
            declared_loss=None,
            unaccounted_quantity=None,
            tolerance=None,
            reasons=[],
        )
    return BalancoResponse(
        status=balance.status.value,
        result=balance.result.value,
        measurement_basis=balance.measurement_basis,
        input_total=_texto_ou_none(balance.input_total),
        output_total=_texto_ou_none(balance.output_total),
        declared_loss=_texto_ou_none(balance.declared_loss),
        unaccounted_quantity=_texto_ou_none(balance.unaccounted_quantity),
        tolerance=_texto_ou_none(balance.tolerance),
        reasons=list(balance.reasons),
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
        balance=_balanco_resposta(resultado.event.balance),
    )


def _resposta_desossa(resultado: DeboningResult, facility_property_id: str) -> DesossaResponse:
    return DesossaResponse(
        transformation_id=str(resultado.event.event_id.value),
        process_type=resultado.event.process_type.value,
        occurred_at=resultado.event.occurred_at,
        facility_property_id=facility_property_id,
        input_item_ids=[
            str(participante.subject_reference.target_id.value)
            for participante in resultado.event.inputs
        ],
        created_items=[
            ItemRastreavelResponse(
                item_id=str(item.item_id.value), item_type=item.item_type, label=item.label
            )
            for item in resultado.created_items
        ],
        balance=_balanco_resposta(resultado.event.balance),
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
        TransformationOutputSpec(
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
            input_quantity=_quantidade_ou_problema(corpo.input_quantity, "input_quantity"),
            input_unit=corpo.input_unit,
            input_measurement_basis=corpo.input_measurement_basis,
            declared_loss=_quantidade_ou_problema(corpo.declared_loss, "declared_loss"),
            tolerance=_quantidade_ou_problema(corpo.tolerance, "tolerance"),
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


@router.post(
    "/transformations/deboning",
    response_model=DesossaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar transformação de desossa (fan-in)",
    description=(
        "Registra um `TransformationEvent(DEBONING)`: consome duas ou mais "
        "entradas rastreáveis do tipo `CARCASS`/`HALF_CARCASS` — já produzidas "
        "por um `SLAUGHTER` anterior — e produz uma ou mais saídas novas "
        "(ADR-0046, Passo 11.6). O perfil do processo decide quem pode ser "
        "entrada, não o Core; todas as entradas e a propriedade precisam "
        "pertencer à mesma Organization."
    ),
    responses=RESPOSTAS_PADRAO,
)
def registrar_desossa(
    corpo: RegistrarDesossaRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TRANSFORMATION_REGISTRAR))],
    connection: ConnectionDependency,
) -> DesossaResponse:
    inputs = tuple(
        DeboningInputSpec(
            item_id=typed_id_or_problem(
                entrada.item_id, entity_type="traceable_item", campo="inputs.item_id"
            ),
            quantity=_quantidade_ou_problema(entrada.quantity, "inputs.quantity"),
            unit=entrada.unit,
            measurement_basis=entrada.measurement_basis,
        )
        for entrada in corpo.inputs
    )
    outputs = tuple(
        TransformationOutputSpec(
            item_type=saida.item_type,
            quantity=_quantidade_ou_problema(saida.quantity, "outputs.quantity"),
            unit=saida.unit,
            measurement_basis=saida.measurement_basis,
            label=saida.label,
        )
        for saida in corpo.outputs
    )

    try:
        resultado = _servico_desossa(connection).register_deboning(
            context=operation_context(contexto),
            facility_property_id=typed_id_or_problem(
                corpo.facility_property_id,
                entity_type="rural_property",
                campo="facility_property_id",
            ),
            occurred_at=corpo.occurred_at,
            inputs=inputs,
            outputs=outputs,
            evidence_references=_evidencias(contexto, corpo.evidence_ids),
            declared_loss=_quantidade_ou_problema(corpo.declared_loss, "declared_loss"),
            tolerance=_quantidade_ou_problema(corpo.tolerance, "tolerance"),
        )
    except KeyError as error:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail="Item ou propriedade não encontrados nesta organização.",
        ) from error
    except (ItemDeTipoInvalido, ItemJaConsumido, ValueError) as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operação recusada pelo domínio",
            detail=str(error),
        ) from error

    return _resposta_desossa(resultado, corpo.facility_property_id)
