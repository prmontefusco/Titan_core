"""Caso de uso do agregado `Part` — Titan Asset & Sustainment (A4).

`InterchangeabilityGroup` **não** entra aqui: é agregado separado
(`06_AGGREGATE_ANALYSIS.md` §1), com serviço próprio em
`interchangeability_group_service.py` — `docs/asset/09_COMMAND_MODEL.md`
`ChangeInterchangeabilityGroup` tem fronteira transacional só
`InterchangeabilityGroup`, não `Part`, então `Part.join_interchangeability_group`
não é exposto por nenhum comando deste slice (fica para quando um comando
concreto precisar, constituição §38).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.events import (
    PART_LIFECYCLE_STATE_CHANGED,
    PART_REGISTERED,
    PART_REVISION_ADDED,
    PART_REVISION_SUPERSEDED,
    part_lifecycle_state_changed_payload,
    part_registered_payload,
    part_revision_added_payload,
    part_revision_superseded_payload,
)
from packages.asset_domain.part import Part, PartIdentity, PartLifecycleState, PartRevision
from packages.shared_kernel import TypedId


class PartNaoEncontrado(KeyError):
    """`part_id` não corresponde a nenhum `Part` desta Organization."""


class PartRepositoryPort(Protocol):
    def save(self, part: Part) -> None: ...

    def update(self, part: Part) -> None: ...

    def get_by_id(self, part_id: TypedId) -> Part | None: ...


@dataclass(frozen=True, slots=True)
class PartService:
    repository: PartRepositoryPort
    recorder: AssetEventRecorder

    def _require(self, part_id: TypedId) -> Part:
        part = self.repository.get_by_id(part_id)
        if part is None:
            raise PartNaoEncontrado(f"Part '{part_id.value}' não encontrado.")
        return part

    def register_part(
        self,
        context: AssetOperationContext,
        *,
        identity: PartIdentity,
        occurred_at: datetime,
    ) -> Part:
        part = Part(
            part_id=TypedId.new("part"),
            organization_id=context.organization_id,
            identity=identity,
        )
        self.repository.save(part)
        self.recorder.record(
            context=context,
            aggregate_id=part.part_id,
            event_type=PART_REGISTERED,
            payload=part_registered_payload(
                part_id=part.part_id,
                part_number=identity.part_number,
                description=identity.description,
                manufacturer=identity.manufacturer,
                manufacturer_pn=identity.manufacturer_pn,
                nsn=identity.nsn,
            ),
            occurred_at=occurred_at,
        )
        return part

    def add_part_revision(
        self,
        context: AssetOperationContext,
        part_id: TypedId,
        *,
        revision_code: str,
        spec_ref: TypedId | None = None,
        drawing_ref: TypedId | None = None,
        materials: tuple[str, ...] = (),
        occurred_at: datetime,
    ) -> Part:
        part = self._require(part_id)
        revision = PartRevision(
            revision_id=TypedId.new("part_revision"),
            revision_code=revision_code,
            spec_ref=spec_ref,
            drawing_ref=drawing_ref,
            materials=materials,
        )
        updated = part.add_revision(revision)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.part_id,
            event_type=PART_REVISION_ADDED,
            payload=part_revision_added_payload(
                part_id=updated.part_id,
                revision_id=revision.revision_id,
                revision_code=revision.revision_code,
                spec_ref=revision.spec_ref,
                drawing_ref=revision.drawing_ref,
            ),
            occurred_at=occurred_at,
        )
        return updated

    def supersede_part_revision(
        self,
        context: AssetOperationContext,
        part_id: TypedId,
        *,
        predecessor_revision_id: TypedId,
        successor_revision_id: TypedId,
        reason: str,
        occurred_at: datetime,
    ) -> Part:
        part = self._require(part_id)
        updated = part.supersede_revision(
            predecessor_revision_id=predecessor_revision_id,
            successor_revision_id=successor_revision_id,
            reason=reason,
        )
        # `supersede_revision` já validou que a revisão existe (levantaria
        # `RevisaoNaoEncontrada` senão) — buscar no `part` original é seguro.
        predecessor_before = next(
            revision
            for revision in part.revisions
            if revision.revision_id == predecessor_revision_id
        )
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.part_id,
            event_type=PART_REVISION_SUPERSEDED,
            payload=part_revision_superseded_payload(
                part_id=updated.part_id,
                predecessor_revision_id=predecessor_revision_id,
                successor_revision_id=successor_revision_id,
                reason=reason,
            ),
            occurred_at=occurred_at,
        )
        self.recorder.record(
            context=context,
            aggregate_id=updated.part_id,
            event_type=PART_LIFECYCLE_STATE_CHANGED,
            payload=part_lifecycle_state_changed_payload(
                part_id=updated.part_id,
                revision_id=predecessor_revision_id,
                from_state=predecessor_before.lifecycle_state.value,
                to_state=PartLifecycleState.SUPERSEDED.value,
            ),
            occurred_at=occurred_at,
        )
        return updated

    def get_part(self, part_id: TypedId) -> Part | None:
        return self.repository.get_by_id(part_id)
