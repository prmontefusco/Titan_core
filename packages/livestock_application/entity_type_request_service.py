"""Caso de uso: pedido de tipo de entidade, decisão e concessão real de acesso.

Submeter e decidir são separados porque quem pede nunca pode ser quem aprova o
próprio pedido (ADR-0031: sem autoatribuição). `approve()` não é só mudar um
status — é o único lugar do sistema que transforma uma intenção declarada em
`Membership` e `Role` de verdade, na mesma unidade de trabalho da decisão.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain import Membership, MembershipRoleAssignment, Role
from packages.livestock_application.authorization import ENTITY_KIND_ROLE_NAMES, ROLE_PERMISSIONS
from packages.livestock_domain.entity_type_request import EntityKind, EntityTypeRequest
from packages.shared_kernel import OrganizationId, TypedId


class EntityTypeRequestJaExiste(ValueError):
    """Já existe um pedido pendente da mesma pessoa, na mesma Organization."""


class EntityTypeRequestNaoEncontrado(ValueError):
    """O request_id informado não corresponde a um pedido existente."""


class CatalogoDePermissoesIncompleto(ValueError):
    """O papel exige uma Permission que ainda não foi semeada no banco.

    Aprovar sem essa checagem criaria um Role com menos Permission do que
    `ROLE_PERMISSIONS` promete — silenciosamente. Melhor recusar a decisão do
    que conceder um papel manco.
    """


class EntityTypeRequestRepositoryPort(Protocol):
    def add(self, request: EntityTypeRequest) -> None: ...

    def get(self, request_id: TypedId) -> EntityTypeRequest | None: ...

    def get_pending_for_user(
        self, organization_id: OrganizationId, requested_by_user_id: TypedId
    ) -> EntityTypeRequest | None: ...

    def list_pending(self, organization_id: OrganizationId) -> tuple[EntityTypeRequest, ...]: ...

    def list_for_user(
        self, organization_id: OrganizationId, requested_by_user_id: TypedId
    ) -> tuple[EntityTypeRequest, ...]: ...

    def record_decision(self, request: EntityTypeRequest) -> None: ...


class MembershipGrantPort(Protocol):
    """Fronteira com o Core: Membership, Role e Permission já existem lá.

    O pedido em si (`EntityTypeRequest`) é conceito exclusivo desta vertical; a
    concessão de acesso reaproveita as primitivas do Core sem duplicá-las.
    """

    def role_by_name(self, organization_id: OrganizationId, name: str) -> Role | None: ...

    def permission_id_by_code(self, code: str) -> TypedId | None: ...

    def add_role(self, role: Role) -> None: ...

    def add_membership(self, membership: Membership) -> None: ...

    def assign_role(self, assignment: MembershipRoleAssignment) -> None: ...


@dataclass(frozen=True, slots=True)
class EntityTypeRequestService:
    requests: EntityTypeRequestRepositoryPort
    grants: MembershipGrantPort

    def submit(
        self,
        *,
        organization_id: OrganizationId,
        requested_kind: EntityKind,
        requested_by_user_id: TypedId,
        requested_at: datetime,
    ) -> EntityTypeRequest:
        existente = self.requests.get_pending_for_user(organization_id, requested_by_user_id)
        if existente is not None:
            raise EntityTypeRequestJaExiste(
                "Já existe um pedido pendente desta pessoa nesta Organization."
            )
        pedido = EntityTypeRequest.submit(
            organization_id=organization_id,
            requested_kind=requested_kind,
            requested_by_user_id=requested_by_user_id,
            requested_at=requested_at,
        )
        self.requests.add(pedido)
        return pedido

    def approve(
        self,
        *,
        request_id: TypedId,
        decided_at: datetime,
        decided_by_actor_id: TypedId,
    ) -> EntityTypeRequest:
        pedido = self._get_or_raise(request_id)
        aprovado = pedido.approve(decided_at=decided_at, decided_by_actor_id=decided_by_actor_id)
        self._grant_access(aprovado, granted_by_actor_id=decided_by_actor_id)
        self.requests.record_decision(aprovado)
        return aprovado

    def deny(
        self,
        *,
        request_id: TypedId,
        decided_at: datetime,
        decided_by_actor_id: TypedId,
        reason: str,
    ) -> EntityTypeRequest:
        pedido = self._get_or_raise(request_id)
        negado = pedido.deny(
            decided_at=decided_at, decided_by_actor_id=decided_by_actor_id, reason=reason
        )
        self.requests.record_decision(negado)
        return negado

    def _get_or_raise(self, request_id: TypedId) -> EntityTypeRequest:
        pedido = self.requests.get(request_id)
        if pedido is None:
            raise EntityTypeRequestNaoEncontrado(f"Pedido {request_id.value} não encontrado.")
        return pedido

    def _grant_access(self, aprovado: EntityTypeRequest, *, granted_by_actor_id: TypedId) -> None:
        nome_papel = ENTITY_KIND_ROLE_NAMES[aprovado.requested_kind]
        papel = self.grants.role_by_name(aprovado.organization_id, nome_papel)
        if papel is None:
            permission_ids: list[TypedId] = []
            for codigo in sorted(ROLE_PERMISSIONS[nome_papel]):
                permission_id = self.grants.permission_id_by_code(codigo)
                if permission_id is None:
                    raise CatalogoDePermissoesIncompleto(
                        f"Permission '{codigo}' exigida pelo papel '{nome_papel}' "
                        "não existe no catálogo desta Organization."
                    )
                permission_ids.append(permission_id)
            papel = Role.create(
                organization_id=aprovado.organization_id,
                name=nome_papel,
                permission_ids=tuple(permission_ids),
            )
            self.grants.add_role(papel)

        vinculo = Membership.create(
            user_id=aprovado.requested_by_user_id,
            organization_id=aprovado.organization_id,
            valid_from=aprovado.decided_at or aprovado.requested_at,
            valid_until=None,
            origin_reference=aprovado.request_id,
            granted_by_actor_id=granted_by_actor_id,
        )
        self.grants.add_membership(vinculo)
        self.grants.assign_role(
            MembershipRoleAssignment.create(
                membership_id=vinculo.membership_id,
                role_id=papel.role_id,
                organization_id=aprovado.organization_id,
                valid_from=aprovado.decided_at or aprovado.requested_at,
                valid_until=None,
                granted_by_actor_id=granted_by_actor_id,
            )
        )
