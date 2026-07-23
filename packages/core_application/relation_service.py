"""Casos de uso e porta para Relações Universais e Temporais (Passo 7.1)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain.relations import UniversalRelation
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class RelationRepositoryPort(Protocol):
    def save(self, relation: UniversalRelation) -> None: ...

    def get_by_id(self, relation_id: TypedId) -> UniversalRelation | None: ...

    def list_outgoing(
        self,
        organization_id: OrganizationId,
        source_id: TypedId,
        at_time: datetime | None = None,
    ) -> list[UniversalRelation]: ...

    def list_incoming(
        self,
        organization_id: OrganizationId,
        target_id: TypedId,
        at_time: datetime | None = None,
    ) -> list[UniversalRelation]: ...


class CrossOrganizationTraversalDenied(RuntimeError):
    """Tentativa de atravessar a genealogia para fora da Organization do contexto."""


@dataclass(frozen=True, slots=True)
class RelationService:
    """Registra e consulta relações sempre dentro de uma Organization.

    A travessia da genealogia é uma operação de leitura poderosa: sem uma fronteira
    explícita, seguir arestas viraria um caminho de vazamento entre tenants.
    """

    repository: RelationRepositoryPort

    def register_relation(self, relation: UniversalRelation) -> UniversalRelation:
        self.repository.save(relation)
        return relation

    def close_relation(self, relation_id: TypedId, ended_at: datetime) -> UniversalRelation:
        current = self.repository.get_by_id(relation_id)
        if current is None:
            raise KeyError(f"Relação {relation_id.value} não encontrada.")
        closed = current.close(ended_at)
        self.repository.save(closed)
        return closed

    def list_outgoing_at(
        self,
        organization_id: OrganizationId,
        source_reference: UniversalReference,
        at_time: datetime | None = None,
    ) -> list[UniversalRelation]:
        self._guard_traversal(organization_id, source_reference)
        return self.repository.list_outgoing(
            organization_id=organization_id,
            source_id=source_reference.target_id,
            at_time=at_time,
        )

    def list_incoming_at(
        self,
        organization_id: OrganizationId,
        target_reference: UniversalReference,
        at_time: datetime | None = None,
    ) -> list[UniversalRelation]:
        self._guard_traversal(organization_id, target_reference)
        return self.repository.list_incoming(
            organization_id=organization_id,
            target_id=target_reference.target_id,
            at_time=at_time,
        )

    @staticmethod
    def _guard_traversal(organization_id: OrganizationId, reference: UniversalReference) -> None:
        if reference.organization_id is not None and reference.organization_id != organization_id:
            raise CrossOrganizationTraversalDenied(
                "Travessia de genealogia negada: a referência pertence a outra Organization."
            )
