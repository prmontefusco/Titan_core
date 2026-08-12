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
from packages.livestock_application.authorization import MEDICATION_CRIAR, MEDICATION_LER
from packages.livestock_application.event_recorder import LivestockEventRecorder
from packages.livestock_application.medication_classification_service import (
    MedicationClassificationService,
)
from packages.livestock_application.medication_service import (
    MedicationBatchService,
    MedicationService,
)
from packages.livestock_domain.medication import MedicationProductClass
from packages.livestock_domain.medication_classification import MedicationClassificationStatus
from packages.livestock_domain.prescription import Prescription, PrescriptionTargetType
from packages.livestock_infrastructure.persistence.medication_classification_repository import (
    TransactionalMedicationClassificationRepository,
)
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
from packages.shared_kernel import SystemClock, TypedId

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


class RegistrarClassificacaoSanitariaRequest(BaseModel):
    status: MedicationClassificationStatus
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime
    limitations: list[str] = Field(default_factory=list)


class ClassificacaoSanitariaResponse(BaseModel):
    assertion_id: str
    medication_id: str
    category: str
    status: str
    valid_from: datetime | None
    valid_to: datetime | None
    observed_at: datetime
    confidence_tier: str
    validation_status: str
    limitations: list[str]


def _classificacao(item: object) -> ClassificacaoSanitariaResponse:
    from packages.livestock_domain.medication_classification import (
        MedicationSanitaryClassificationAssertion,
    )

    assert isinstance(item, MedicationSanitaryClassificationAssertion)
    return ClassificacaoSanitariaResponse(
        assertion_id=str(item.assertion_id.value),
        medication_id=str(item.medication_id.value),
        category=item.category.value,
        status=item.status.value,
        valid_from=item.valid_from,
        valid_to=item.valid_to,
        observed_at=item.observed_at,
        confidence_tier=item.confidence_tier.value,
        validation_status=item.validation_status.value,
        limitations=list(item.limitations),
    )


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


class EmitirPrescricaoRequest(BaseModel):
    veterinarian_id: str
    medication_id: str
    property_id: str
    dosage: str = Field(min_length=1, max_length=255)
    administration_route: str = Field(min_length=1, max_length=80)
    target_type: PrescriptionTargetType
    target_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)
    prescribed_date: datetime | None = None


class PrescricaoResponse(BaseModel):
    prescription_id: str
    organization_id: str
    veterinarian_id: str
    medication_id: str
    property_id: str
    prescribed_date: datetime
    dosage: str
    administration_route: str
    target_type: PrescriptionTargetType
    target_ids: list[str]
    reason: str


def _servico_medicamento(connection: Connection) -> MedicationService:
    return MedicationService(
        medication_repository=TransactionalMedicationRepository(connection=connection),
        prescription_repository=TransactionalPrescriptionRepository(connection=connection),
        veterinarian_repository=TransactionalVeterinarianRepository(connection=connection),
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        recorder=_recorder(connection),
    )


def _prescricao(prescription: Prescription) -> PrescricaoResponse:
    return PrescricaoResponse(
        prescription_id=str(prescription.prescription_id.value),
        organization_id=str(prescription.organization_id.value),
        veterinarian_id=str(prescription.veterinarian_id.value),
        medication_id=str(prescription.medication_id.value),
        property_id=str(prescription.property_id.value),
        prescribed_date=prescription.prescribed_date,
        dosage=prescription.dosage,
        administration_route=prescription.administration_route,
        target_type=prescription.target_type,
        target_ids=[str(target_id.value) for target_id in prescription.target_ids],
        reason=prescription.reason,
    )


def _target_ids_or_problem(
    target_type: PrescriptionTargetType, ids: list[str]
) -> tuple[TypedId, ...]:
    entity_type = "animal" if target_type is PrescriptionTargetType.ANIMAL else "livestock_lot"
    return tuple(
        typed_id_or_problem(target_id, entity_type=entity_type, campo="target_ids")
        for target_id in ids
    )


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
    try:
        medicamento = _servico_medicamento(connection).register_medication(
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


@router.post(
    "/prescriptions",
    response_model=PrescricaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Emitir uma prescricao veterinaria",
    responses=RESPOSTAS_PADRAO,
)
def emitir_prescricao(
    corpo: EmitirPrescricaoRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_CRIAR))],
    connection: ConnectionDependency,
) -> PrescricaoResponse:
    try:
        prescription = _servico_medicamento(connection).issue_prescription(
            context=operation_context(contexto),
            veterinarian_id=typed_id_or_problem(
                corpo.veterinarian_id, entity_type="veterinarian", campo="veterinarian_id"
            ),
            medication_id=typed_id_or_problem(
                corpo.medication_id, entity_type="medication", campo="medication_id"
            ),
            property_id=typed_id_or_problem(
                corpo.property_id, entity_type="rural_property", campo="property_id"
            ),
            dosage=corpo.dosage,
            administration_route=corpo.administration_route,
            target_type=corpo.target_type,
            target_ids=_target_ids_or_problem(corpo.target_type, corpo.target_ids),
            reason=corpo.reason,
            prescribed_date=corpo.prescribed_date,
        )
    except KeyError as error:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nÃ£o encontrado",
            detail="Veterinario, medicamento ou propriedade nao encontrados nesta organizacao.",
        ) from error
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operacao recusada pelo dominio",
            detail=str(error),
        ) from error
    return _prescricao(prescription)


@router.get(
    "/prescriptions/{prescription_id}",
    response_model=PrescricaoResponse,
    summary="Detalhar uma prescricao veterinaria",
    responses=RESPOSTAS_PADRAO,
)
def detalhar_prescricao(
    prescription_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_LER))],
    connection: ConnectionDependency,
) -> PrescricaoResponse:
    alvo = typed_id_or_problem(prescription_id, entity_type="prescription", campo="prescription_id")
    prescription = TransactionalPrescriptionRepository(connection=connection).get_by_id(alvo)
    if prescription is None or prescription.organization_id != contexto.organization_id:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Prescricao nao encontrada nesta organizacao.",
        )
    return _prescricao(prescription)


@router.post(
    "/medications/{medication_id}/sanitary-classifications",
    response_model=ClassificacaoSanitariaResponse,
    status_code=status.HTTP_201_CREATED,
    responses=RESPOSTAS_PADRAO,
)
def registrar_classificacao_sanitaria(
    medication_id: str,
    corpo: RegistrarClassificacaoSanitariaRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_CRIAR))],
    connection: ConnectionDependency,
) -> ClassificacaoSanitariaResponse:
    service = MedicationClassificationService(
        TransactionalMedicationClassificationRepository(connection),
        TransactionalMedicationRepository(connection),
    )
    try:
        item = service.record(
            context=operation_context(contexto),
            medication_id=typed_id_or_problem(
                medication_id, entity_type="medication", campo="medication_id"
            ),
            status=corpo.status,
            valid_from=corpo.valid_from,
            valid_to=corpo.valid_to,
            observed_at=corpo.observed_at,
            limitations=tuple(corpo.limitations),
        )
    except KeyError as error:
        raise DomainProblem(
            status_code=404,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail=str(error),
        ) from error
    except ValueError as error:
        raise DomainProblem(
            status_code=409,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operação recusada",
            detail=str(error),
        ) from error
    return _classificacao(item)


@router.get(
    "/medications/{medication_id}/sanitary-classifications",
    response_model=list[ClassificacaoSanitariaResponse],
    responses=RESPOSTAS_PADRAO,
)
def listar_classificacoes_sanitarias(
    medication_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(MEDICATION_LER))],
    connection: ConnectionDependency,
) -> list[ClassificacaoSanitariaResponse]:
    target = typed_id_or_problem(medication_id, entity_type="medication", campo="medication_id")
    medication = TransactionalMedicationRepository(connection).get_by_id(target)
    if medication is None or medication.organization_id != contexto.organization_id:
        raise DomainProblem(
            status_code=404,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail="Medicamento não encontrado nesta organização.",
        )
    return [
        _classificacao(item)
        for item in TransactionalMedicationClassificationRepository(connection).list_by_medication(
            contexto.organization_id, target
        )
    ]
