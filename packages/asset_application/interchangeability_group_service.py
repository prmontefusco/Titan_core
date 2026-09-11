"""Caso de uso do agregado `InterchangeabilityGroup` — Titan Asset (A4).

Agregado separado de `Part` (`06_AGGREGATE_ANALYSIS.md` §1). O comando
`ChangeInterchangeabilityGroup` (`docs/asset/09_COMMAND_MODEL.md`) tem
fronteira transacional só `InterchangeabilityGroup` — por isso este serviço
não toca `Part.interchangeability_group_ref` (ver nota em `part_service.py`).

Não há evento de "grupo criado" no catálogo (`08_DOMAIN_EVENTS.md`) — só
`part.interchangeability_group_changed` (`change="ADDED"|"REMOVED"`) para
mudança de membro. Por isso `add_member` cria o grupo implicitamente na
primeira chamada quando ele ainda não existe: a existência do grupo só se
torna um fato de negócio observável quando ganha o primeiro membro.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.events import (
    PART_INTERCHANGEABILITY_GROUP_CHANGED,
    part_interchangeability_group_changed_payload,
)
from packages.asset_domain.part import InterchangeabilityGroup
from packages.shared_kernel import TypedId


class InterchangeabilityGroupNaoEncontrado(KeyError):
    """`group_id` não corresponde a nenhum `InterchangeabilityGroup` desta Organization."""


class InterchangeabilityGroupRepositoryPort(Protocol):
    def save(self, group: InterchangeabilityGroup) -> None: ...

    def update(self, group: InterchangeabilityGroup) -> None: ...

    def get_by_id(self, group_id: TypedId) -> InterchangeabilityGroup | None: ...


@dataclass(frozen=True, slots=True)
class InterchangeabilityGroupService:
    repository: InterchangeabilityGroupRepositoryPort
    recorder: AssetEventRecorder

    def add_member(
        self,
        context: AssetOperationContext,
        group_id: TypedId,
        *,
        revision_ref: TypedId,
        occurred_at: datetime,
    ) -> InterchangeabilityGroup:
        existing = self.repository.get_by_id(group_id)
        if existing is None:
            updated = InterchangeabilityGroup(
                group_id=group_id,
                organization_id=context.organization_id,
                member_part_revisions=(revision_ref,),
            )
            self.repository.save(updated)
        else:
            updated = existing.add_member(revision_ref)
            self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.group_id,
            event_type=PART_INTERCHANGEABILITY_GROUP_CHANGED,
            payload=part_interchangeability_group_changed_payload(
                group_id=updated.group_id,
                part_revision_ref=revision_ref,
                change="ADDED",
            ),
            occurred_at=occurred_at,
        )
        return updated

    def remove_member(
        self,
        context: AssetOperationContext,
        group_id: TypedId,
        *,
        revision_ref: TypedId,
        occurred_at: datetime,
    ) -> InterchangeabilityGroup:
        group = self.repository.get_by_id(group_id)
        if group is None:
            raise InterchangeabilityGroupNaoEncontrado(
                f"InterchangeabilityGroup '{group_id.value}' não encontrado."
            )
        updated = group.remove_member(revision_ref)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.group_id,
            event_type=PART_INTERCHANGEABILITY_GROUP_CHANGED,
            payload=part_interchangeability_group_changed_payload(
                group_id=updated.group_id,
                part_revision_ref=revision_ref,
                change="REMOVED",
            ),
            occurred_at=occurred_at,
        )
        return updated

    def get_group(self, group_id: TypedId) -> InterchangeabilityGroup | None:
        return self.repository.get_by_id(group_id)
