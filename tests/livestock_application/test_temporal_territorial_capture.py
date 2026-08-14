"""T-05D: capturas territoriais sinteticas preservam historia consultada."""

from datetime import UTC, datetime
from hashlib import sha256

from packages.livestock_application.fact_provider import (
    MOVEMENT_DERIVED_PROPERTY_STAY_FACT_TYPE,
    LivestockFactProvider,
)
from packages.livestock_application.temporal_territorial_capture import (
    TEMPORAL_TERRITORIAL_TEST_OVERLAP_FACT_TYPE,
    TEMPORAL_TERRITORIAL_TEST_TIMELINE_FACT_TYPE,
    TemporalTerritorialCaptureLimitation,
    TemporalTerritorialCaptureReader,
)
from packages.livestock_domain.movement import AnimalMovement
from packages.livestock_domain.territorial_capture import (
    TERRITORIAL_TEST_OVERLAP_LAYER,
    TERRITORIAL_TEST_TIMELINE_LAYER,
    TerritorialCaptureKind,
    TerritorialSourceCapture,
)
from packages.shared_kernel import OrganizationId, TypedId


class _CaptureRepo:
    def __init__(self, captures: list[TerritorialSourceCapture]) -> None:
        self.captures = captures

    def list_by_property(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> list[TerritorialSourceCapture]:
        return [
            item
            for item in self.captures
            if item.organization_id == organization_id and item.property_id == property_id
        ]


class _MovementRepo:
    def __init__(self, movements: list[AnimalMovement]) -> None:
        self.movements = movements

    def save(self, movement: AnimalMovement) -> None: ...

    def get_by_id(self, movement_id: TypedId) -> AnimalMovement | None:
        return next((item for item in self.movements if item.movement_id == movement_id), None)

    def list_by_animal(self, animal_id: TypedId) -> list[AnimalMovement]:
        return [item for item in self.movements if animal_id in item.animal_ids]

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[AnimalMovement]:
        return [item for item in self.movements if item.organization_id == organization_id][
            offset : offset + limit
        ]


def _digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def _capture(
    organization_id: OrganizationId,
    property_id: TypedId,
    *,
    geometry_id: TypedId | None = None,
    geometry_version: int = 1,
    source_layer: str = TERRITORIAL_TEST_TIMELINE_LAYER,
    kind: TerritorialCaptureKind = TerritorialCaptureKind.TIMELINE,
    operation: str = "timeline",
    response_summary: dict[str, object] | None = None,
    captured_at: datetime = datetime(2026, 1, 2, tzinfo=UTC),
    known_at: datetime = datetime(2026, 1, 2, tzinfo=UTC),
    source_valid_from: datetime | None = datetime(2026, 1, 1, tzinfo=UTC),
    source_valid_to: datetime | None = datetime(2027, 1, 1, tzinfo=UTC),
) -> TerritorialSourceCapture:
    return TerritorialSourceCapture.create_synthetic(
        organization_id=organization_id,
        property_id=property_id,
        geometry_id=geometry_id or TypedId.new("property_geometry"),
        geometry_version=geometry_version,
        source_layer=source_layer,
        kind=kind,
        operation=operation,
        request_scope_digest=_digest(f"{property_id.value}:{source_layer}:{operation}"),
        response_summary=response_summary or {"has_occurrence": True, "years": [2020]},
        source_version_ids=("synthetic-layer-v1",),
        captured_at=captured_at,
        known_at=known_at,
        source_valid_from=source_valid_from,
        source_valid_to=source_valid_to,
        recorded_at=known_at,
    )


def test_capture_known_after_cutoff_is_not_historical_source() -> None:
    organization_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    reader = TemporalTerritorialCaptureReader(
        _CaptureRepo(
            [
                _capture(
                    organization_id,
                    property_id,
                    captured_at=datetime(2026, 1, 1, tzinfo=UTC),
                    known_at=datetime(2026, 1, 3, tzinfo=UTC),
                )
            ]
        )
    )

    selection = reader.select(
        organization_id,
        property_id,
        reference_time=datetime(2026, 1, 2, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert selection.limitation is TemporalTerritorialCaptureLimitation.ABSENT_AT_CONTEXT


def test_capture_after_reference_time_is_not_historical_source() -> None:
    organization_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    reader = TemporalTerritorialCaptureReader(
        _CaptureRepo(
            [
                _capture(
                    organization_id,
                    property_id,
                    captured_at=datetime(2026, 1, 5, tzinfo=UTC),
                    known_at=datetime(2026, 1, 5, tzinfo=UTC),
                )
            ]
        )
    )

    selection = reader.select(
        organization_id,
        property_id,
        reference_time=datetime(2026, 1, 4, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 6, tzinfo=UTC),
    )

    assert selection.limitation is TemporalTerritorialCaptureLimitation.ABSENT_AT_CONTEXT


def test_two_captures_for_same_scope_fail_closed() -> None:
    organization_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    geometry_id = TypedId.new("property_geometry")
    first = _capture(organization_id, property_id, geometry_id=geometry_id)
    second = _capture(
        organization_id,
        property_id,
        geometry_id=geometry_id,
        response_summary={"has_occurrence": False, "years": []},
    )
    reader = TemporalTerritorialCaptureReader(_CaptureRepo([first, second]))

    selection = reader.select(
        organization_id,
        property_id,
        reference_time=datetime(2026, 1, 10, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 10, tzinfo=UTC),
    )

    assert selection.limitation is TemporalTerritorialCaptureLimitation.CONFLICT


def test_temporal_snapshot_emits_synthetic_territorial_facts_from_movement_property() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    birth_property_id = TypedId.new("rural_property")
    property_id = TypedId.new("rural_property")
    geometry_id = TypedId.new("property_geometry")
    movement = AnimalMovement(
        movement_id=TypedId.new("animal_movement"),
        organization_id=organization_id,
        origin_property_id=birth_property_id,
        destination_property_id=property_id,
        movement_time=datetime(2026, 1, 2, tzinfo=UTC),
        animal_ids=(animal_id,),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    timeline = _capture(
        organization_id,
        property_id,
        geometry_id=geometry_id,
        response_summary={"has_occurrence": True, "years": [2020]},
    )
    overlap = _capture(
        organization_id,
        property_id,
        geometry_id=geometry_id,
        source_layer=TERRITORIAL_TEST_OVERLAP_LAYER,
        kind=TerritorialCaptureKind.OVERLAP,
        operation="intersects",
        response_summary={"has_overlap": False, "feature_count": 0},
    )
    provider = LivestockFactProvider(
        property_repository=None,  # type: ignore[arg-type]
        animal_repository=None,  # type: ignore[arg-type]
        movement_repository=_MovementRepo([movement]),
        temporal_territorial_capture_reader=TemporalTerritorialCaptureReader(
            _CaptureRepo([timeline, overlap])
        ),
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 10, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 10, tzinfo=UTC),
    )
    facts = {item.fact_type: item for item in snapshot.facts}

    assert MOVEMENT_DERIVED_PROPERTY_STAY_FACT_TYPE in facts
    assert TEMPORAL_TERRITORIAL_TEST_TIMELINE_FACT_TYPE in facts
    assert TEMPORAL_TERRITORIAL_TEST_OVERLAP_FACT_TYPE in facts
    assert facts[TEMPORAL_TERRITORIAL_TEST_TIMELINE_FACT_TYPE].payload["capture_id"]
    assert (
        facts[TEMPORAL_TERRITORIAL_TEST_TIMELINE_FACT_TYPE].payload["geometry_id"]
        == geometry_id.value.hex
    )
    assert (
        facts[TEMPORAL_TERRITORIAL_TEST_TIMELINE_FACT_TYPE].payload["response_digest"]
        == timeline.response_digest
    )
    assert facts[TEMPORAL_TERRITORIAL_TEST_OVERLAP_FACT_TYPE].payload["response_summary"] == {
        "has_overlap": False,
        "feature_count": 0,
    }


def test_absent_capture_declares_limitation_instead_of_clean_state() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    property_id = TypedId.new("rural_property")
    movement = AnimalMovement(
        movement_id=TypedId.new("animal_movement"),
        organization_id=organization_id,
        origin_property_id=TypedId.new("rural_property"),
        destination_property_id=property_id,
        movement_time=datetime(2026, 1, 2, tzinfo=UTC),
        animal_ids=(animal_id,),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    provider = LivestockFactProvider(
        property_repository=None,  # type: ignore[arg-type]
        animal_repository=None,  # type: ignore[arg-type]
        movement_repository=_MovementRepo([movement]),
        temporal_territorial_capture_reader=TemporalTerritorialCaptureReader(_CaptureRepo([])),
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 10, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 10, tzinfo=UTC),
    )

    assert snapshot.get_facts_by_type(TEMPORAL_TERRITORIAL_TEST_OVERLAP_FACT_TYPE) == ()
    assert "LIVESTOCK_TEMPORAL_TERRITORIAL_CAPTURE_ABSENT_AT_CONTEXT" in (
        snapshot.knowledge_limitations
    )
