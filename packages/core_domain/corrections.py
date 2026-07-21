"""Correções imutáveis que preservam o evento original."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from packages.core_domain.events import CanonicalPayload, DomainEvent
from packages.shared_kernel import RecordTimestamps, TypedId, UniversalReference
from packages.shared_kernel.serialization import CanonicalValue


class ChangeKind(StrEnum):
    CORRECAO_DE_ERRO = "CORRECAO_DE_ERRO"
    COMPLEMENTACAO = "COMPLEMENTACAO"


@dataclass(frozen=True, slots=True)
class Correction:
    """Novo evento que corrige ou complementa outro sem substituí-lo."""

    event: DomainEvent
    corrected_event_id: TypedId
    change_kind: ChangeKind
    justification: str

    def __post_init__(self) -> None:
        if self.event.event_type != "registro_corrigido":
            raise ValueError("Correction exige evento registro_corrigido.")
        if self.corrected_event_id.entity_type != "domain_event":
            raise ValueError("corrected_event_id deve referenciar domain_event.")
        if self.event.causation_id != self.corrected_event_id:
            raise ValueError("A correção deve possuir o original como causation_id.")
        if not isinstance(self.change_kind, ChangeKind):
            raise TypeError("change_kind deve ser ChangeKind.")
        if not isinstance(self.justification, str) or not self.justification.strip():
            raise ValueError("justification deve ser texto não vazio.")


def build_correction(
    *,
    correction_event_id: TypedId,
    original: DomainEvent,
    aggregate_version: int,
    change_kind: ChangeKind,
    justification: str,
    new_content: Mapping[str, CanonicalValue],
    corrected_at: datetime,
    actor_reference: UniversalReference,
    source_reference: UniversalReference,
    correlation_id: TypedId,
) -> Correction:
    """Cria a correção; persistência e projeções continuam responsabilidades externas."""
    if not isinstance(original, DomainEvent):
        raise TypeError("original deve ser DomainEvent.")
    if aggregate_version <= original.aggregate_version:
        raise ValueError("A correção deve possuir versão posterior ao evento original.")
    if not isinstance(change_kind, ChangeKind):
        raise TypeError("change_kind deve ser ChangeKind.")
    if not isinstance(justification, str) or not justification.strip():
        raise ValueError("justification deve ser texto não vazio.")
    if not isinstance(new_content, Mapping) or not new_content:
        raise ValueError("new_content deve ser mapa não vazio.")

    payload = CanonicalPayload.from_mapping(
        schema="correcao_registro_payload",
        version=1,
        value={
            "change_kind": change_kind.value,
            "evento_original_id": str(original.event_id.value),
            "justificativa": justification.strip(),
            "novo_conteudo": new_content,
            "versao_original": original.aggregate_version,
        },
    )
    event = DomainEvent(
        event_id=correction_event_id,
        organization_id=original.organization_id,
        aggregate_reference=original.aggregate_reference,
        aggregate_version=aggregate_version,
        event_type="registro_corrigido",
        event_version=1,
        timestamps=RecordTimestamps(occurred_at=corrected_at, recorded_at=corrected_at),
        actor_reference=actor_reference,
        source_reference=source_reference,
        correlation_id=correlation_id,
        causation_id=original.event_id,
        payload=payload,
    )
    return Correction(event, original.event_id, change_kind, justification.strip())
