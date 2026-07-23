"""Modelo de domínio para Projeções Reconstruíveis (Passo 7.2).

Projeção é estrutura de leitura derivada de Events e registros imutáveis. Não é
fonte de verdade, não contém regra de negócio própria e deve ser reconstruível:
apagá-la e reconstruí-la a partir das fontes tem de produzir exatamente o mesmo
conteúdo.
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class ReferencingKind(Enum):
    """Natureza do registro imutável que originou a referência."""

    DOMAIN_EVENT = "domain_event"
    RELATION = "relation"


class ReferenceRole(Enum):
    """Papel em que a referência aparece no registro de origem."""

    AGGREGATE = "aggregate"
    ACTOR = "actor"
    SOURCE = "source"
    RELATION_SOURCE = "relation_source"
    RELATION_TARGET = "relation_target"


@dataclass(frozen=True, slots=True)
class ReverseReference:
    """Uma aresta reversa: quem aponta para determinada referência.

    Não carrega interpretação: apenas registra que um evento ou relação citou
    aquela referência, em qual papel e quando.
    """

    organization_id: OrganizationId
    referenced: UniversalReference
    referencing_kind: ReferencingKind
    referencing_id: TypedId
    role: ReferenceRole
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.referenced, UniversalReference):
            raise TypeError("referenced deve ser uma UniversalReference.")
        if not isinstance(self.referencing_kind, ReferencingKind):
            raise TypeError("referencing_kind deve ser um ReferencingKind válido.")
        if not isinstance(self.referencing_id, TypedId):
            raise TypeError("referencing_id deve ser um TypedId.")
        if not isinstance(self.role, ReferenceRole):
            raise TypeError("role deve ser um ReferenceRole válido.")
        if not isinstance(self.occurred_at, datetime):
            raise TypeError("occurred_at deve ser um datetime.")
        if (
            self.referenced.organization_id is not None
            and self.referenced.organization_id != self.organization_id
        ):
            raise ValueError(
                "A projeção não atravessa Organizations: a referência pertence a outra."
            )

    def sort_key(self) -> tuple[str, str, str, str, str]:
        """Chave de ordenação total e estável, independente da ordem de leitura."""
        return (
            self.referenced.target_id.entity_type,
            str(self.referenced.target_id.value),
            self.referencing_kind.value,
            str(self.referencing_id.value),
            self.role.value,
        )


def compute_projection_digest(entries: Sequence[ReverseReference]) -> str:
    """Digest SHA-256 do conteúdo da projeção, independente da ordem.

    É o que torna a reconstrução verificável: reconstruir e comparar o digest
    prova que a projeção derivada continua idêntica, sem inspecionar linha a linha.
    O instante de reconstrução não entra no digest, porque ele descreve a execução
    e não o conteúdo derivado.
    """
    payload = sorted(
        [
            {
                "organization_id": str(e.organization_id.value),
                "referenced_type": e.referenced.target_id.entity_type,
                "referenced_id": str(e.referenced.target_id.value),
                "referencing_kind": e.referencing_kind.value,
                "referencing_id": str(e.referencing_id.value),
                "role": e.role.value,
            }
            for e in entries
        ],
        key=lambda item: (
            item["referenced_type"],
            item["referenced_id"],
            item["referencing_kind"],
            item["referencing_id"],
            item["role"],
        ),
    )
    raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()
