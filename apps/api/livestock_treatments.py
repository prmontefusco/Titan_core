"""Aplicação de tratamento (Passo 10.4b).

Há **duas** rotas de escrita e nenhuma de edição, porque o registro é
append-only: corrigir cria um novo registro que aponta para o original, que
permanece intacto. Expor um `PUT /treatments/{id}` seria oferecer no HTTP uma
operação que o domínio recusa — e a recusa é o ponto do Marco 9.
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
from packages.core_infrastructure.persistence.evidence import TransactionalEvidenceRepository
from packages.core_infrastructure.persistence.outbox import TransactionalOutboxMessageWriter
from packages.livestock_application.authorization import TREATMENT_REGISTRAR
from packages.livestock_application.erp_outbox import LivestockErpOutboxService
from packages.livestock_application.event_recorder import LivestockEventRecorder
from packages.livestock_application.treatment_service import TreatmentApplicationService
from packages.livestock_domain.treatment import TreatmentApplication
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLotMembershipRepository,
)
from packages.livestock_infrastructure.persistence.medication_repository import (
    TransactionalMedicationBatchRepository,
    TransactionalPrescriptionRepository,
)
from packages.livestock_infrastructure.persistence.sanitary_campaign_repository import (
    TransactionalSanitaryCampaignRepository,
)
from packages.livestock_infrastructure.persistence.treatment_repository import (
    TransactionalTreatmentApplicationRepository,
)
from packages.shared_kernel import SystemClock, UniversalReference

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


class RegistrarTratamentoRequest(BaseModel):
    animal_id: str
    medication_batch_id: str
    applied_at: datetime = Field(description="Instante da aplicação, em UTC.")
    dose: str | None = None
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidências do Core que sustentam o registro.",
    )
    evidence_notes: list[str] = Field(
        default_factory=list,
        description="Anotações do operador. Não são prova.",
    )
    prescription_id: str | None = None
    sanitary_campaign_id: str | None = None


class CorrigirTratamentoRequest(BaseModel):
    applied_at: datetime
    dose: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)
    prescription_id: str | None = None
    sanitary_campaign_id: str | None = None


class TratamentoResponse(BaseModel):
    application_id: str
    animal_id: str
    medication_batch_id: str
    applied_at: datetime
    dose: str | None
    prescription_id: str | None
    sanitary_campaign_id: str | None
    corrects_application_id: str | None


def _servico(connection: Connection) -> TreatmentApplicationService:
    return TreatmentApplicationService(
        application_repository=TransactionalTreatmentApplicationRepository(connection=connection),
        animal_repository=TransactionalAnimalRepository(connection=connection),
        batch_repository=TransactionalMedicationBatchRepository(connection=connection),
        prescription_repository=TransactionalPrescriptionRepository(connection=connection),
        recorder=LivestockEventRecorder(
            event_log=DomainEventRepository(connection=connection), clock=SystemClock()
        ),
        # O repositório de Evidence do Core satisfaz a porta de consulta por
        # estrutura: a vertical só precisa de `get_by_id`.
        evidence_lookup=TransactionalEvidenceRepository(connection=connection),
        campaign_lookup=TransactionalSanitaryCampaignRepository(connection=connection),
        lot_membership_lookup=TransactionalLotMembershipRepository(connection=connection),
        erp_outbox_service=LivestockErpOutboxService(
            writer=TransactionalOutboxMessageWriter(connection=connection)
        ),
    )


def _resposta(aplicacao: TreatmentApplication) -> TratamentoResponse:
    return TratamentoResponse(
        application_id=str(aplicacao.application_id.value),
        animal_id=str(aplicacao.animal_id.value),
        medication_batch_id=str(aplicacao.medication_batch_id.value),
        applied_at=aplicacao.applied_at,
        dose=aplicacao.dose,
        prescription_id=(
            str(aplicacao.prescription_id.value) if aplicacao.prescription_id is not None else None
        ),
        sanitary_campaign_id=(
            str(aplicacao.sanitary_campaign_id.value)
            if aplicacao.sanitary_campaign_id is not None
            else None
        ),
        corrects_application_id=(
            str(aplicacao.corrects_application_id.value)
            if aplicacao.corrects_application_id is not None
            else None
        ),
    )


def _evidencias(contexto: OrganizationContext, ids: list[str]) -> tuple[UniversalReference, ...]:
    return tuple(
        UniversalReference(
            target_id=typed_id_or_problem(bruto, entity_type="evidence", campo="evidence_ids"),
            organization_id=contexto.organization_id,
            contract_version=1,
        )
        for bruto in ids
    )


@router.post(
    "/treatments",
    response_model=TratamentoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar uma aplicação de tratamento",
    responses=RESPOSTAS_PADRAO,
)
def registrar_tratamento(
    corpo: RegistrarTratamentoRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TREATMENT_REGISTRAR))],
    connection: ConnectionDependency,
) -> TratamentoResponse:
    try:
        aplicacao = _servico(connection).register_application(
            context=operation_context(contexto),
            animal_id=typed_id_or_problem(corpo.animal_id, entity_type="animal", campo="animal_id"),
            medication_batch_id=typed_id_or_problem(
                corpo.medication_batch_id,
                entity_type="medication_batch",
                campo="medication_batch_id",
            ),
            applied_at=corpo.applied_at,
            dose=corpo.dose,
            evidence_references=_evidencias(contexto, corpo.evidence_ids),
            evidence_notes=tuple(corpo.evidence_notes),
            prescription_id=(
                typed_id_or_problem(
                    corpo.prescription_id, entity_type="prescription", campo="prescription_id"
                )
                if corpo.prescription_id
                else None
            ),
            sanitary_campaign_id=(
                typed_id_or_problem(
                    corpo.sanitary_campaign_id,
                    entity_type="sanitary_campaign",
                    campo="sanitary_campaign_id",
                )
                if corpo.sanitary_campaign_id
                else None
            ),
        )
    except KeyError as error:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail="Animal, lote, prescrição ou evidência não encontrados nesta organização.",
        ) from error
    except ValueError as error:
        # Instante no futuro ou sem timezone: o cliente mandou algo que o domínio
        # recusa por regra, e não por má formação sintática.
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operação recusada pelo domínio",
            detail=str(error),
        ) from error

    return _resposta(aplicacao)


@router.post(
    "/treatments/{application_id}/corrections",
    response_model=TratamentoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Corrigir uma aplicação por novo registro",
    description=(
        "Cria um **novo** registro que supersede o original. O original permanece "
        "intacto e visível na linha do tempo: o histórico só cresce."
    ),
    responses=RESPOSTAS_PADRAO,
)
def corrigir_tratamento(
    application_id: str,
    corpo: CorrigirTratamentoRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TREATMENT_REGISTRAR))],
    connection: ConnectionDependency,
) -> TratamentoResponse:
    try:
        correcao = _servico(connection).correct_application(
            context=operation_context(contexto),
            original_application_id=typed_id_or_problem(
                application_id,
                entity_type="treatment_application",
                campo="application_id",
            ),
            applied_at=corpo.applied_at,
            dose=corpo.dose,
            evidence_references=_evidencias(contexto, corpo.evidence_ids),
            evidence_notes=tuple(corpo.evidence_notes),
            prescription_id=(
                typed_id_or_problem(
                    corpo.prescription_id, entity_type="prescription", campo="prescription_id"
                )
                if corpo.prescription_id
                else None
            ),
            sanitary_campaign_id=(
                typed_id_or_problem(
                    corpo.sanitary_campaign_id,
                    entity_type="sanitary_campaign",
                    campo="sanitary_campaign_id",
                )
                if corpo.sanitary_campaign_id
                else None
            ),
        )
    except KeyError as error:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail="Aplicação, evidência ou prescrição não encontradas nesta organização.",
        ) from error
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operação recusada pelo domínio",
            detail=str(error),
        ) from error

    return _resposta(correcao)
