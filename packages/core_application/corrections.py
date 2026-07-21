"""Caso de uso mínimo para registrar correção sem sobrescrita."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain import ChangeKind, Correction, DomainEvent, build_correction
from packages.shared_kernel import TypedId, UniversalReference
from packages.shared_kernel.serialization import CanonicalValue


class CorrectionEventWriter(Protocol):
    def append(self, event: DomainEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class CorrectionService:
    writer: CorrectionEventWriter

    def correct(
        self,
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
        correction = build_correction(
            correction_event_id=correction_event_id,
            original=original,
            aggregate_version=aggregate_version,
            change_kind=change_kind,
            justification=justification,
            new_content=new_content,
            corrected_at=corrected_at,
            actor_reference=actor_reference,
            source_reference=source_reference,
            correlation_id=correlation_id,
        )
        self.writer.append(correction.event)
        return correction
