"""Pedido de vinculo a um tipo de entidade dentro de uma Organization.

Autoatribuicao de Role e proibida (ADR-0031): o cadastro no provedor de
identidade nunca concede acesso por si so. Este agregado registra apenas a
intencao declarada por quem ja se autenticou; a concessao real de Membership e
Role so acontece quando um Actor com a permissao de decisao aprova o pedido.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class EntityKind(StrEnum):
    ADMIN = "ADMIN"
    PRODUTOR = "PRODUTOR"
    FRIGORIFICO = "FRIGORIFICO"
    VETERINARIO = "VETERINARIO"
    AUDITOR = "AUDITOR"
    CERTIFICADOR = "CERTIFICADOR"
    CONSUMIDOR = "CONSUMIDOR"


class EntityTypeRequestStatus(StrEnum):
    PENDENTE = "PENDENTE"
    APROVADA = "APROVADA"
    NEGADA = "NEGADA"


class EntityTypeRequestJaDecidido(ValueError):
    """O pedido ja saiu de PENDENTE e nao pode ser decidido de novo."""


@dataclass(frozen=True, slots=True)
class EntityTypeRequest:
    request_id: TypedId
    organization_id: OrganizationId
    requested_kind: EntityKind
    requested_by_user_id: TypedId
    status: EntityTypeRequestStatus
    requested_at: datetime
    decided_at: datetime | None = None
    decided_by_actor_id: TypedId | None = None
    decision_reason: str | None = None

    def __post_init__(self) -> None:
        if self.request_id.entity_type != "entity_type_request":
            raise ValueError("request_id deve ter entity_type 'entity_type_request'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.requested_kind, EntityKind):
            raise TypeError("requested_kind deve ser EntityKind.")
        if self.requested_by_user_id.entity_type != "user":
            raise ValueError("requested_by_user_id deve ter entity_type 'user'.")
        if not isinstance(self.status, EntityTypeRequestStatus):
            raise TypeError("status deve ser EntityTypeRequestStatus.")
        require_utc(self.requested_at, field_name="requested_at")

        if self.status is EntityTypeRequestStatus.PENDENTE:
            if self.decided_at is not None or self.decided_by_actor_id is not None:
                raise ValueError("Pedido PENDENTE nao pode ter decisao registrada.")
            if self.decision_reason is not None:
                raise ValueError("Pedido PENDENTE nao pode ter motivo de decisao.")
            return

        if self.decided_at is None or self.decided_by_actor_id is None:
            raise ValueError("Pedido decidido exige decided_at e decided_by_actor_id.")
        require_utc(self.decided_at, field_name="decided_at")
        if self.decided_at < self.requested_at:
            raise ValueError("decided_at nao pode ser anterior a requested_at.")
        if self.decided_by_actor_id.entity_type != "actor":
            raise ValueError("decided_by_actor_id deve ter entity_type 'actor'.")
        if self.status is EntityTypeRequestStatus.NEGADA and not (
            self.decision_reason and self.decision_reason.strip()
        ):
            raise ValueError("Pedido NEGADA exige decision_reason.")
        if self.status is EntityTypeRequestStatus.APROVADA and self.decision_reason == "":
            raise ValueError("decision_reason vazio deve ser None, nao string vazia.")

    @classmethod
    def submit(
        cls,
        *,
        organization_id: OrganizationId,
        requested_kind: EntityKind,
        requested_by_user_id: TypedId,
        requested_at: datetime,
    ) -> "EntityTypeRequest":
        return cls(
            request_id=TypedId.new("entity_type_request"),
            organization_id=organization_id,
            requested_kind=requested_kind,
            requested_by_user_id=requested_by_user_id,
            status=EntityTypeRequestStatus.PENDENTE,
            requested_at=requested_at,
        )

    def approve(self, *, decided_at: datetime, decided_by_actor_id: TypedId) -> "EntityTypeRequest":
        if self.status is not EntityTypeRequestStatus.PENDENTE:
            raise EntityTypeRequestJaDecidido(
                f"Pedido ja esta {self.status.value}, nao pode ser aprovado de novo."
            )
        return replace(
            self,
            status=EntityTypeRequestStatus.APROVADA,
            decided_at=decided_at,
            decided_by_actor_id=decided_by_actor_id,
        )

    def deny(
        self, *, decided_at: datetime, decided_by_actor_id: TypedId, reason: str
    ) -> "EntityTypeRequest":
        if self.status is not EntityTypeRequestStatus.PENDENTE:
            raise EntityTypeRequestJaDecidido(
                f"Pedido ja esta {self.status.value}, nao pode ser negado de novo."
            )
        if not reason.strip():
            raise ValueError("reason nao pode ser vazio ao negar um pedido.")
        return replace(
            self,
            status=EntityTypeRequestStatus.NEGADA,
            decided_at=decided_at,
            decided_by_actor_id=decided_by_actor_id,
            decision_reason=reason.strip(),
        )
