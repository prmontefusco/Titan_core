from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import pytest

from packages.core_domain import Membership, MembershipRoleAssignment, Role
from packages.livestock_application.authorization import (
    ADMIN_MESTRE,
    ENTITY_TYPE_REQUEST_DECIDIR,
    ENTITY_TYPE_REQUEST_LER,
    FRIGORIFICO,
)
from packages.livestock_application.entity_type_request_service import (
    CatalogoDePermissoesIncompleto,
    EntityTypeRequestJaExiste,
    EntityTypeRequestNaoEncontrado,
    EntityTypeRequestService,
)
from packages.livestock_domain.entity_type_request import EntityKind, EntityTypeRequest
from packages.shared_kernel import OrganizationId, TypedId


@dataclass
class _FakeRequests:
    by_id: dict[UUID, EntityTypeRequest] = field(default_factory=dict)

    def add(self, request: EntityTypeRequest) -> None:
        self.by_id[request.request_id.value] = request

    def get(self, request_id: TypedId) -> EntityTypeRequest | None:
        return self.by_id.get(request_id.value)

    def get_pending_for_user(
        self, organization_id: OrganizationId, requested_by_user_id: TypedId
    ) -> EntityTypeRequest | None:
        for pedido in self.by_id.values():
            if (
                pedido.organization_id == organization_id
                and pedido.requested_by_user_id == requested_by_user_id
                and pedido.status.value == "PENDENTE"
            ):
                return pedido
        return None

    def list_pending(self, organization_id: OrganizationId) -> tuple[EntityTypeRequest, ...]:
        return tuple(
            pedido
            for pedido in self.by_id.values()
            if pedido.organization_id == organization_id and pedido.status.value == "PENDENTE"
        )

    def list_for_user(
        self, organization_id: OrganizationId, requested_by_user_id: TypedId
    ) -> tuple[EntityTypeRequest, ...]:
        return tuple(
            sorted(
                (
                    pedido
                    for pedido in self.by_id.values()
                    if pedido.organization_id == organization_id
                    and pedido.requested_by_user_id == requested_by_user_id
                ),
                key=lambda pedido: pedido.requested_at,
                reverse=True,
            )
        )

    def record_decision(self, request: EntityTypeRequest) -> None:
        self.by_id[request.request_id.value] = request


@dataclass
class _FakeGrants:
    permission_ids_by_code: dict[str, TypedId]
    roles: dict[tuple[UUID, str], Role] = field(default_factory=dict)
    memberships: list[Membership] = field(default_factory=list)
    assignments: list[MembershipRoleAssignment] = field(default_factory=list)

    def role_by_name(self, organization_id: OrganizationId, name: str) -> Role | None:
        return self.roles.get((organization_id.value, name))

    def permission_id_by_code(self, code: str) -> TypedId | None:
        return self.permission_ids_by_code.get(code)

    def add_role(self, role: Role) -> None:
        self.roles[(role.organization_id.value, role.name)] = role

    def add_membership(self, membership: Membership) -> None:
        self.memberships.append(membership)

    def assign_role(self, assignment: MembershipRoleAssignment) -> None:
        self.assignments.append(assignment)


def _service(
    *, permission_codes: tuple[str, ...] = ()
) -> tuple[EntityTypeRequestService, _FakeGrants]:
    grants = _FakeGrants(
        permission_ids_by_code={codigo: TypedId.new("permission") for codigo in permission_codes}
    )
    return EntityTypeRequestService(requests=_FakeRequests(), grants=grants), grants


def test_submit_recusa_segundo_pedido_pendente_da_mesma_pessoa() -> None:
    servico, _ = _service()
    organizacao = OrganizationId.new()
    usuario = TypedId.new("user")

    servico.submit(
        organization_id=organizacao,
        requested_kind=EntityKind.PRODUTOR,
        requested_by_user_id=usuario,
        requested_at=datetime.now(UTC),
    )

    with pytest.raises(EntityTypeRequestJaExiste):
        servico.submit(
            organization_id=organizacao,
            requested_kind=EntityKind.AUDITOR,
            requested_by_user_id=usuario,
            requested_at=datetime.now(UTC),
        )


def test_approve_recusa_quando_permission_nao_existe_no_catalogo() -> None:
    servico, _ = _service(permission_codes=())  # ADMIN_MESTRE exige 2 permissions, nenhuma semeada
    pedido = servico.submit(
        organization_id=OrganizationId.new(),
        requested_kind=EntityKind.ADMIN,
        requested_by_user_id=TypedId.new("user"),
        requested_at=datetime.now(UTC),
    )

    with pytest.raises(CatalogoDePermissoesIncompleto):
        servico.approve(
            request_id=pedido.request_id,
            decided_at=pedido.requested_at,
            decided_by_actor_id=TypedId.new("actor"),
        )


def test_approve_concede_role_com_permissoes_e_membership() -> None:
    servico, grants = _service(
        permission_codes=(ENTITY_TYPE_REQUEST_LER, ENTITY_TYPE_REQUEST_DECIDIR)
    )
    organizacao = OrganizationId.new()
    usuario = TypedId.new("user")
    pedido = servico.submit(
        organization_id=organizacao,
        requested_kind=EntityKind.ADMIN,
        requested_by_user_id=usuario,
        requested_at=datetime.now(UTC),
    )

    aprovado = servico.approve(
        request_id=pedido.request_id,
        decided_at=pedido.requested_at,
        decided_by_actor_id=TypedId.new("actor"),
    )

    assert aprovado.status.value == "APROVADA"
    assert len(grants.memberships) == 1
    assert grants.memberships[0].user_id == usuario
    assert grants.memberships[0].organization_id == organizacao
    papel = grants.roles[(organizacao.value, ADMIN_MESTRE)]
    assert len(papel.permission_ids) == 2
    assert len(grants.assignments) == 1
    assert grants.assignments[0].role_id == papel.role_id


def test_approve_reaproveita_role_ja_existente_em_vez_de_duplicar() -> None:
    servico, grants = _service(permission_codes=())
    organizacao = OrganizationId.new()
    papel_existente = Role.create(organization_id=organizacao, name=FRIGORIFICO, permission_ids=())
    grants.add_role(papel_existente)

    pedido = servico.submit(
        organization_id=organizacao,
        requested_kind=EntityKind.FRIGORIFICO,
        requested_by_user_id=TypedId.new("user"),
        requested_at=datetime.now(UTC),
    )
    servico.approve(
        request_id=pedido.request_id,
        decided_at=pedido.requested_at,
        decided_by_actor_id=TypedId.new("actor"),
    )

    assert len(grants.roles) == 1
    assert grants.assignments[0].role_id == papel_existente.role_id


def test_deny_nao_concede_acesso() -> None:
    servico, grants = _service()
    pedido = servico.submit(
        organization_id=OrganizationId.new(),
        requested_kind=EntityKind.CONSUMIDOR,
        requested_by_user_id=TypedId.new("user"),
        requested_at=datetime.now(UTC),
    )

    negado = servico.deny(
        request_id=pedido.request_id,
        decided_at=pedido.requested_at,
        decided_by_actor_id=TypedId.new("actor"),
        reason="Sem evidencia suficiente.",
    )

    assert negado.status.value == "NEGADA"
    assert grants.memberships == []
    assert grants.assignments == []


def test_approve_pedido_inexistente_falha() -> None:
    servico, _ = _service()

    with pytest.raises(EntityTypeRequestNaoEncontrado):
        servico.approve(
            request_id=TypedId.new("entity_type_request"),
            decided_at=datetime.now(UTC),
            decided_by_actor_id=TypedId.new("actor"),
        )
