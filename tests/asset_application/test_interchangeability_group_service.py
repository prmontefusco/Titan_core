"""Testes do `InterchangeabilityGroupService` — Titan Asset (A4)."""

from datetime import UTC, datetime

import pytest

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_application.interchangeability_group_service import (
    InterchangeabilityGroupNaoEncontrado,
    InterchangeabilityGroupRepositoryPort,
    InterchangeabilityGroupService,
)
from packages.asset_domain.events import PART_INTERCHANGEABILITY_GROUP_CHANGED
from packages.asset_domain.part import InterchangeabilityGroup
from packages.shared_kernel import TypedId
from tests.asset_support import FakeEventLog

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class InMemoryInterchangeabilityGroupRepository(InterchangeabilityGroupRepositoryPort):
    def __init__(self) -> None:
        self.groups: dict[str, InterchangeabilityGroup] = {}

    def save(self, group: InterchangeabilityGroup) -> None:
        self.groups[group.group_id.value.hex] = group

    def update(self, group: InterchangeabilityGroup) -> None:
        self.groups[group.group_id.value.hex] = group

    def get_by_id(self, group_id: TypedId) -> InterchangeabilityGroup | None:
        return self.groups.get(group_id.value.hex)


def test_add_member_creates_group_implicitly_on_first_call(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = InterchangeabilityGroupService(
        repository=InMemoryInterchangeabilityGroupRepository(), recorder=recorder
    )
    group_id = TypedId.new("interchangeability_group")
    revision_1 = TypedId.new("part_revision")

    group = service.add_member(context, group_id, revision_ref=revision_1, occurred_at=OCCURRED_AT)

    assert group.group_id == group_id
    assert group.member_part_revisions == (revision_1,)
    event = event_log.only(PART_INTERCHANGEABILITY_GROUP_CHANGED)
    assert event.aggregate_version == 1


def test_add_second_member_updates_existing_group(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = InterchangeabilityGroupService(
        repository=InMemoryInterchangeabilityGroupRepository(), recorder=recorder
    )
    group_id = TypedId.new("interchangeability_group")
    revision_1 = TypedId.new("part_revision")
    revision_2 = TypedId.new("part_revision")

    service.add_member(context, group_id, revision_ref=revision_1, occurred_at=OCCURRED_AT)
    group = service.add_member(context, group_id, revision_ref=revision_2, occurred_at=OCCURRED_AT)

    assert group.member_part_revisions == (revision_1, revision_2)
    assert group.interchanges_with(revision_1) == (revision_2,)
    assert len(event_log.of_type(PART_INTERCHANGEABILITY_GROUP_CHANGED)) == 2


def test_remove_member(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = InterchangeabilityGroupService(
        repository=InMemoryInterchangeabilityGroupRepository(), recorder=recorder
    )
    group_id = TypedId.new("interchangeability_group")
    revision_1 = TypedId.new("part_revision")
    service.add_member(context, group_id, revision_ref=revision_1, occurred_at=OCCURRED_AT)

    updated = service.remove_member(
        context, group_id, revision_ref=revision_1, occurred_at=OCCURRED_AT
    )
    assert updated.member_part_revisions == ()


def test_remove_member_on_unknown_group_raises(
    recorder: AssetEventRecorder, context: AssetOperationContext
) -> None:
    service = InterchangeabilityGroupService(
        repository=InMemoryInterchangeabilityGroupRepository(), recorder=recorder
    )
    with pytest.raises(InterchangeabilityGroupNaoEncontrado):
        service.remove_member(
            context,
            TypedId.new("interchangeability_group"),
            revision_ref=TypedId.new("part_revision"),
            occurred_at=OCCURRED_AT,
        )
