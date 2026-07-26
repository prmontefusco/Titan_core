"""Campanhas sanitarias oficiais (Passo 14.2)."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from apps.api.livestock_dependencies import (
    ConnectionDependency,
    operation_context,
    require_permission,
    typed_id_or_problem,
)
from apps.api.pagination import Pagina, PaginacaoDependency, montar_pagina
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_domain import OrganizationContext
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.livestock_application.authorization import (
    SANITARY_CAMPAIGN_CRIAR,
    SANITARY_CAMPAIGN_LER,
)
from packages.livestock_application.event_recorder import LivestockEventRecorder
from packages.livestock_application.sanitary_campaign_service import SanitaryCampaignService
from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.livestock_infrastructure.persistence.sanitary_campaign_repository import (
    TransactionalSanitaryCampaignRepository,
)
from packages.shared_kernel import SystemClock

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


class RegistrarCampanhaSanitariaRequest(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=255)
    starts_at: datetime
    ends_at: datetime
    disease: str | None = Field(default=None, max_length=255)
    authority: str | None = Field(default=None, max_length=255)


class CampanhaSanitariaResponse(BaseModel):
    campaign_id: str
    organization_id: str
    code: str
    name: str
    starts_at: datetime
    ends_at: datetime
    disease: str | None
    authority: str | None


def _resposta(campaign: SanitaryCampaign) -> CampanhaSanitariaResponse:
    return CampanhaSanitariaResponse(
        campaign_id=str(campaign.campaign_id.value),
        organization_id=str(campaign.organization_id.value),
        code=campaign.code,
        name=campaign.name,
        starts_at=campaign.starts_at,
        ends_at=campaign.ends_at,
        disease=campaign.disease,
        authority=campaign.authority,
    )


def _servico(connection: Connection) -> SanitaryCampaignService:
    return SanitaryCampaignService(
        campaign_repository=TransactionalSanitaryCampaignRepository(connection=connection),
        recorder=LivestockEventRecorder(
            event_log=DomainEventRepository(connection=connection), clock=SystemClock()
        ),
    )


@router.post(
    "/sanitary-campaigns",
    response_model=CampanhaSanitariaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar uma campanha sanitaria oficial",
    responses=RESPOSTAS_PADRAO,
)
def registrar_campanha_sanitaria(
    corpo: RegistrarCampanhaSanitariaRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(SANITARY_CAMPAIGN_CRIAR))],
    connection: ConnectionDependency,
) -> CampanhaSanitariaResponse:
    try:
        campaign = _servico(connection).register_campaign(
            context=operation_context(contexto),
            code=corpo.code,
            name=corpo.name,
            starts_at=corpo.starts_at,
            ends_at=corpo.ends_at,
            disease=corpo.disease,
            authority=corpo.authority,
        )
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operacao recusada pelo dominio",
            detail=str(error),
        ) from error
    return _resposta(campaign)


@router.get(
    "/sanitary-campaigns",
    response_model=Pagina[CampanhaSanitariaResponse],
    summary="Listar campanhas sanitarias",
    responses=RESPOSTAS_PADRAO,
)
def listar_campanhas_sanitarias(
    contexto: Annotated[OrganizationContext, Depends(require_permission(SANITARY_CAMPAIGN_LER))],
    paginacao: PaginacaoDependency,
    connection: ConnectionDependency,
) -> Any:
    encontrados = TransactionalSanitaryCampaignRepository(
        connection=connection
    ).list_by_organization(
        contexto.organization_id,
        limit=paginacao.limite_de_sondagem,
        offset=paginacao.offset,
    )
    return montar_pagina([_resposta(campaign) for campaign in encontrados], paginacao)


@router.get(
    "/sanitary-campaigns/{campaign_id}",
    response_model=CampanhaSanitariaResponse,
    summary="Detalhar uma campanha sanitaria",
    responses=RESPOSTAS_PADRAO,
)
def detalhar_campanha_sanitaria(
    campaign_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(SANITARY_CAMPAIGN_LER))],
    connection: ConnectionDependency,
) -> CampanhaSanitariaResponse:
    alvo = typed_id_or_problem(campaign_id, entity_type="sanitary_campaign", campo="campaign_id")
    encontrado = TransactionalSanitaryCampaignRepository(connection=connection).get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Campanha sanitaria nao encontrada nesta organizacao.",
        )
    return _resposta(encontrado)
