"""Casos de uso para Projeções Reconstruíveis (Passo 7.2)."""

from dataclasses import dataclass
from typing import Protocol

from packages.core_domain.projections import ReverseReference, compute_projection_digest
from packages.shared_kernel import OrganizationId, UniversalReference


class ProjectionSourcePort(Protocol):
    """Leitura das fontes imutáveis das quais a projeção é derivada.

    A projeção nunca inventa conteúdo: tudo que ela contém vem daqui.
    """

    def read_event_references(self, organization_id: OrganizationId) -> list[ReverseReference]: ...

    def read_relation_references(
        self, organization_id: OrganizationId
    ) -> list[ReverseReference]: ...


class ProjectionRepositoryPort(Protocol):
    def replace_all(
        self, organization_id: OrganizationId, entries: list[ReverseReference]
    ) -> None: ...

    def clear(self, organization_id: OrganizationId) -> None: ...

    def list_all(self, organization_id: OrganizationId) -> list[ReverseReference]: ...

    def list_referencing(
        self, organization_id: OrganizationId, referenced: UniversalReference
    ) -> list[ReverseReference]: ...


@dataclass(frozen=True, slots=True)
class ProjectionRebuildService:
    """Deriva a projeção de referências reversas a partir das fontes imutáveis.

    Não há regra de negócio aqui: o serviço apenas indexa o que eventos e relações
    já declararam. Por isso reconstruir é sempre seguro — a projeção é descartável
    e a fonte histórica permanece intacta.
    """

    source: ProjectionSourcePort
    repository: ProjectionRepositoryPort

    def derive(self, organization_id: OrganizationId) -> list[ReverseReference]:
        entries = [
            *self.source.read_event_references(organization_id),
            *self.source.read_relation_references(organization_id),
        ]
        # Ordem total e estável: o conteúdo derivado não pode depender da ordem em
        # que o banco devolveu as linhas.
        entries.sort(key=lambda e: e.sort_key())
        return entries

    def rebuild(self, organization_id: OrganizationId) -> str:
        """Reconstrói a projeção do zero e devolve o digest do conteúdo derivado."""
        entries = self.derive(organization_id)
        self.repository.replace_all(organization_id, entries)
        return compute_projection_digest(entries)

    def current_digest(self, organization_id: OrganizationId) -> str:
        """Digest do que está gravado na projeção hoje."""
        return compute_projection_digest(self.repository.list_all(organization_id))

    def is_consistent_with_sources(self, organization_id: OrganizationId) -> bool:
        """Compara o gravado com o que as fontes produziriam agora, sem gravar nada."""
        return self.current_digest(organization_id) == compute_projection_digest(
            self.derive(organization_id)
        )

    def list_referencing(
        self, organization_id: OrganizationId, referenced: UniversalReference
    ) -> list[ReverseReference]:
        if referenced.organization_id is not None and referenced.organization_id != organization_id:
            raise ValueError(
                "A projeção não atravessa Organizations: a referência pertence a outra."
            )
        return self.repository.list_referencing(organization_id, referenced)
