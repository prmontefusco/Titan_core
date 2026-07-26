"""Medicamento e lote de medicamento (Passo 10.4b).

Duas rotas, e não uma: medicamento é o produto — nome, princípio ativo, prazo de
carência — e lote é a unidade física fabricada que a aplicação de tratamento
referencia. É a separação que permite ao recall localizar exatamente os animais
que receberam um lote específico, e não todos os que já tomaram aquele produto.
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
from packages.livestock_application.authorization import MEDICATION_CRIAR
from packages.livestock_application.event_recorder import LivestockEventRecorder
from packages.livestock_application.medication_service import (
    MedicationBatchService,
    MedicationService,
)
from packages.livestock_domain.medication import MedicationProductClass
from packages.livestock_infrastructure.persistence.medication_repository import (
    TransactionalMedicationBatchRepository,
    TransactionalMedicationRepository,
    TransactionalPrescriptionRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
)
from packages.shared_kernel import SystemClock

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


def _recorder(connection: Connection) -> LivestockEventRecorder:
    return LivestockEventRecorder(
        event_log=DomainEventRepository(connection=connection), clock=SystemClock()
    )


class RegistrarMedicamentoRequest(BaseModel):
    trade_name: str = Field(min_length=1, max_length=255)
    active_ingredient: str = Field(min_length=1, max_length=255)
    manufacturer: str = Field(min_length=1, max_length=255)
    withdrawal_period_days: int = Field(
        ge=0, description="Dias de carência declarados para o produto."
    )
    product_class: MedicationProductClass = MedicationProductClass.PHARMACOLOGICAL
    dosage_instruction: str | None = None


class MedicamentoResponse(BaseModel):
    medication_id: str
    organization_id: str
    trade_name: str
    active_ingredient: str
    withdrawal_period_days: int
    product_class: MedicationProductClass


class RegistrarLoteRequest(BaseModel):
    medication_id: str
    batch_number: str = Field(min_length=1, max_length=100)
    expiry_date: datetime
    manufacturing_date: datetime | None = None


class LoteResponse(BaseModel):
    batch_id: str
    medication_id: str
    batch_number: str
    expiry_date: datetime


@router.post(
    "/medications",
    response_model=MedicamentoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar um medicamento",
    responses=RESPOSTAS_PADRAO,
)
def registrar_medicamento(
    corpo: RegistrarMedicamentoRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_CRIAR))],
    connection: ConnectionDependency,
) -> MedicamentoResponse:
    servico = MedicationService(
        medication_repository=TransactionalMedicationRepository(connection=connection),
        prescription_repository=TransactionalPrescriptionRepository(connection=connection),
        veterinarian_repository=TransactionalVeterinarianRepository(connection=connection),
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        recorder=_recorder(connection),
    )

    try:
        medicamento = servico.register_medication(
            context=operation_context(contexto),
            trade_name=corpo.trade_name,
            active_ingredient=corpo.active_ingredient,
            manufacturer=corpo.manufacturer,
            withdrawal_period_days=corpo.withdrawal_period_days,
            product_class=corpo.product_class,
            dosage_instruction=corpo.dosage_instruction,
        )
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operação recusada pelo domínio",
            detail=str(error),
        ) from error

    return MedicamentoResponse(
        medication_id=str(medicamento.medication_id.value),
        organization_id=str(medicamento.organization_id.value),
        trade_name=medicamento.trade_name,
        active_ingredient=medicamento.active_ingredient,
        withdrawal_period_days=medicamento.withdrawal_period_days,
        product_class=medicamento.product_class,
    )


@router.post(
    "/medication-batches",
    response_model=LoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar um lote de medicamento",
    responses=RESPOSTAS_PADRAO,
)
def registrar_lote(
    corpo: RegistrarLoteRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_CRIAR))],
    connection: ConnectionDependency,
) -> LoteResponse:
    servico = MedicationBatchService(
        batch_repository=TransactionalMedicationBatchRepository(connection=connection),
        medication_repository=TransactionalMedicationRepository(connection=connection),
        recorder=_recorder(connection),
    )

    try:
        lote = servico.register_batch(
            context=operation_context(contexto),
            medication_id=typed_id_or_problem(
                corpo.medication_id, entity_type="medication", campo="medication_id"
            ),
            batch_number=corpo.batch_number,
            expiry_date=corpo.expiry_date,
            manufacturing_date=corpo.manufacturing_date,
        )
    except KeyError as error:
        # Medicamento inexistente e medicamento de outra organização respondem
        # igual: distinguir revelaria o que existe fora do alcance de quem chama.
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail="Medicamento não encontrado nesta organização.",
        ) from error
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operação recusada pelo domínio",
            detail=str(error),
        ) from error

    return LoteResponse(
        batch_id=str(lote.batch_id.value),
        medication_id=str(lote.medication_id.value),
        batch_number=lote.batch_number,
        expiry_date=lote.expiry_date,
    )
