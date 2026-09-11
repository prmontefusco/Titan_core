"""Testes do `PartService` — Titan Asset (A4)."""

from datetime import UTC, datetime

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_application.part_service import PartRepositoryPort, PartService
from packages.asset_domain.events import (
    PART_LIFECYCLE_STATE_CHANGED,
    PART_REGISTERED,
    PART_REVISION_ADDED,
    PART_REVISION_SUPERSEDED,
)
from packages.asset_domain.part import Part, PartIdentity, PartLifecycleState
from packages.shared_kernel import TypedId
from tests.asset_support import FakeEventLog

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class InMemoryPartRepository(PartRepositoryPort):
    def __init__(self) -> None:
        self.parts: dict[str, Part] = {}

    def save(self, part: Part) -> None:
        self.parts[part.part_id.value.hex] = part

    def update(self, part: Part) -> None:
        self.parts[part.part_id.value.hex] = part

    def get_by_id(self, part_id: TypedId) -> Part | None:
        return self.parts.get(part_id.value.hex)


def _register(service: PartService, context: AssetOperationContext) -> Part:
    return service.register_part(
        context,
        identity=PartIdentity(
            part_number="PN-100", description="Retentor hidráulico", manufacturer="Acme"
        ),
        occurred_at=OCCURRED_AT,
    )


def test_register_part(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = PartService(repository=InMemoryPartRepository(), recorder=recorder)
    part = _register(service, context)

    assert part.organization_id == context.organization_id
    assert service.get_part(part.part_id) == part
    event_log.only(PART_REGISTERED)


def test_add_revision_and_supersede(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = PartService(repository=InMemoryPartRepository(), recorder=recorder)
    part = _register(service, context)

    with_revision_a = service.add_part_revision(
        context, part.part_id, revision_code="A", occurred_at=OCCURRED_AT
    )
    assert len(with_revision_a.revisions) == 1
    revision_a_id = with_revision_a.revisions[0].revision_id
    event_log.only(PART_REVISION_ADDED)

    with_revision_b = service.add_part_revision(
        context, part.part_id, revision_code="B", occurred_at=OCCURRED_AT
    )
    revision_b_id = next(r.revision_id for r in with_revision_b.revisions if r.revision_code == "B")

    superseded = service.supersede_part_revision(
        context,
        part.part_id,
        predecessor_revision_id=revision_a_id,
        successor_revision_id=revision_b_id,
        reason="Retentor A descontinuado pelo fabricante.",
        occurred_at=OCCURRED_AT,
    )
    predecessor = next(r for r in superseded.revisions if r.revision_id == revision_a_id)
    assert predecessor.lifecycle_state is PartLifecycleState.SUPERSEDED
    assert len(superseded.supersessions) == 1
    event_log.only(PART_REVISION_SUPERSEDED)
    lifecycle_event = event_log.only(PART_LIFECYCLE_STATE_CHANGED)
    assert lifecycle_event.aggregate_version == 5
