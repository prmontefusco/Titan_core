"""Pedido de tipo de entidade: submissão pública, decisão administrativa.

`POST /entity-type-requests` é a única rota da vertical que não exige
`OrganizationContext` — por definição, quem pede ainda não tem Membership na
Organization-alvo. As demais rotas exigem a permissão de decisão, nunca papel
(mesmo princípio de `livestock_dependencies.require_permission`).
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field

from apps.api.livestock_dependencies import (
    ORGANIZATION_HEADER,
    ConnectionDependency,
    UserIdDependency,
    _requested_organization,
    require_permission,
    typed_id_or_problem,
    uuid_or_problem,
)
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_domain import OrganizationContext
from packages.core_infrastructure.persistence import MembershipRepository
from packages.core_infrastructure.persistence.organizations import set_local_organization_context
from packages.livestock_application.authorization import (
    ENTITY_TYPE_REQUEST_DECIDIR,
    ENTITY_TYPE_REQUEST_LER,
)
from packages.livestock_application.entity_type_request_service import (
    CatalogoDePermissoesIncompleto,
    EntityTypeRequestJaExiste,
    EntityTypeRequestNaoEncontrado,
    EntityTypeRequestService,
)
from packages.livestock_domain.entity_type_request import (
    EntityKind,
    EntityTypeRequest,
    EntityTypeRequestJaDecidido,
)
from packages.livestock_infrastructure.persistence import (
    TransactionalEntityTypeRequestRepository,
    TransactionalMembershipGrant,
)
from packages.shared_kernel import OrganizationId

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


class SubmeterPedidoRequest(BaseModel):
    organization_id: str = Field(description="Organization à qual a pessoa pede para se vincular.")
    requested_kind: EntityKind


class NegarPedidoRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class PedidoResponse(BaseModel):
    request_id: str
    organization_id: str
    requested_kind: EntityKind
    status: str
    requested_at: datetime
    decided_at: datetime | None
    decision_reason: str | None


class MeuStatusResponse(BaseModel):
    has_membership: bool
    requests: list[PedidoResponse]


def _para_resposta(pedido: EntityTypeRequest) -> PedidoResponse:
    return PedidoResponse(
        request_id=str(pedido.request_id.value),
        organization_id=str(pedido.organization_id.value),
        requested_kind=pedido.requested_kind,
        status=pedido.status.value,
        requested_at=pedido.requested_at,
        decided_at=pedido.decided_at,
        decision_reason=pedido.decision_reason,
    )


def _service(connection: ConnectionDependency) -> EntityTypeRequestService:
    return EntityTypeRequestService(
        requests=TransactionalEntityTypeRequestRepository(connection=connection),
        grants=TransactionalMembershipGrant(connection=connection),
    )


@router.post(
    "/entity-type-requests",
    response_model=PedidoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Pedir vínculo a um tipo de entidade numa Organization",
    responses=RESPOSTAS_PADRAO,
)
def submeter_pedido(
    corpo: SubmeterPedidoRequest,
    requested_by_user_id: UserIdDependency,
    connection: ConnectionDependency,
) -> PedidoResponse:
    organizacao = OrganizationId(uuid_or_problem(corpo.organization_id, campo="organization_id"))
    set_local_organization_context(connection, organizacao)

    try:
        pedido = _service(connection).submit(
            organization_id=organizacao,
            requested_kind=corpo.requested_kind,
            requested_by_user_id=requested_by_user_id,
            requested_at=datetime.now(UTC),
        )
    except EntityTypeRequestJaExiste as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="PEDIDO_PENDENTE_JA_EXISTE",
            title="Pedido pendente já existe",
            detail=str(error),
        ) from error

    return _para_resposta(pedido)


@router.get(
    "/entity-type-requests/mine",
    response_model=MeuStatusResponse,
    summary="Consultar meu próprio vínculo e pedidos nesta Organization",
    responses=RESPOSTAS_PADRAO,
)
def meu_status(
    requested_by_user_id: UserIdDependency,
    connection: ConnectionDependency,
    organizacao: Annotated[str | None, Header(alias=ORGANIZATION_HEADER)] = None,
) -> MeuStatusResponse:
    """Autoconsulta: nunca exige permissão, só o próprio principal autenticado.

    É deliberadamente diferente de `require_permission` — perguntar "qual é o
    meu status aqui" não pode depender de já ter status nenhum, senão quem
    ainda não foi aprovado nunca saberia que está esperando.
    """
    organization_id = _requested_organization(organizacao)
    set_local_organization_context(connection, organization_id)

    vinculos = MembershipRepository(connection).list_valid_for_user(
        requested_by_user_id, organization_id, datetime.now(UTC)
    )
    pedidos = _service(connection).requests.list_for_user(organization_id, requested_by_user_id)

    return MeuStatusResponse(
        has_membership=len(vinculos) > 0,
        requests=[_para_resposta(pedido) for pedido in pedidos],
    )


@router.get(
    "/entity-type-requests",
    response_model=list[PedidoResponse],
    summary="Listar pedidos pendentes na Organization",
    responses=RESPOSTAS_PADRAO,
)
def listar_pendentes(
    contexto: Annotated[OrganizationContext, Depends(require_permission(ENTITY_TYPE_REQUEST_LER))],
    connection: ConnectionDependency,
) -> list[PedidoResponse]:
    pendentes = _service(connection).requests.list_pending(contexto.organization_id)
    return [_para_resposta(pedido) for pedido in pendentes]


@router.post(
    "/entity-type-requests/{request_id}/approve",
    response_model=PedidoResponse,
    summary="Aprovar um pedido e conceder Membership/Role reais",
    responses=RESPOSTAS_PADRAO,
)
def aprovar_pedido(
    request_id: str,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(ENTITY_TYPE_REQUEST_DECIDIR))
    ],
    connection: ConnectionDependency,
) -> PedidoResponse:
    try:
        aprovado = _service(connection).approve(
            request_id=typed_id_or_problem(
                request_id, entity_type="entity_type_request", campo="request_id"
            ),
            decided_at=datetime.now(UTC),
            decided_by_actor_id=contexto.actor_id,
        )
    except EntityTypeRequestNaoEncontrado as error:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="PEDIDO_NAO_ENCONTRADO",
            title="Pedido não encontrado",
            detail=str(error),
        ) from error
    except EntityTypeRequestJaDecidido as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="PEDIDO_JA_DECIDIDO",
            title="Pedido já foi decidido",
            detail=str(error),
        ) from error
    except CatalogoDePermissoesIncompleto as error:
        raise DomainProblem(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            reason_code="CATALOGO_DE_PERMISSOES_INCOMPLETO",
            title="Catálogo de permissões incompleto",
            detail=str(error),
        ) from error

    return _para_resposta(aprovado)


@router.post(
    "/entity-type-requests/{request_id}/deny",
    response_model=PedidoResponse,
    summary="Negar um pedido",
    responses=RESPOSTAS_PADRAO,
)
def negar_pedido(
    request_id: str,
    corpo: NegarPedidoRequest,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(ENTITY_TYPE_REQUEST_DECIDIR))
    ],
    connection: ConnectionDependency,
) -> PedidoResponse:
    try:
        negado = _service(connection).deny(
            request_id=typed_id_or_problem(
                request_id, entity_type="entity_type_request", campo="request_id"
            ),
            decided_at=datetime.now(UTC),
            decided_by_actor_id=contexto.actor_id,
            reason=corpo.reason,
        )
    except EntityTypeRequestNaoEncontrado as error:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="PEDIDO_NAO_ENCONTRADO",
            title="Pedido não encontrado",
            detail=str(error),
        ) from error
    except EntityTypeRequestJaDecidido as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="PEDIDO_JA_DECIDIDO",
            title="Pedido já foi decidido",
            detail=str(error),
        ) from error

    return _para_resposta(negado)
