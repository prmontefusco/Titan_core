"""T-05D Corte 3: adapter territorial sintetico-realista."""

from datetime import UTC, datetime

from packages.livestock_application.temporal_territorial_capture import (
    TemporalTerritorialCaptureLimitation,
    TemporalTerritorialCaptureReader,
)
from packages.livestock_application.territorial_adapter import (
    SyntheticTerritorialAdapterLimitation,
    SyntheticTerritorialAdapterProfile,
    SyntheticTerritorialCaptureAdapter,
    SyntheticTerritorialCaptureRequest,
    synthetic_territorial_request_scope_digest,
    synthetic_territorial_response_digest_for_payload,
)
from packages.livestock_domain.territorial_capture import (
    TERRITORIAL_RESPONSE_SCHEMA,
    TERRITORIAL_TEST_OVERLAP_LAYER,
    TERRITORIAL_TEST_TIMELINE_LAYER,
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


def _request(
    *,
    profile: SyntheticTerritorialAdapterProfile = (
        SyntheticTerritorialAdapterProfile.PRODES_LIKE_TIMELINE
    ),
    response_payload: dict[str, object] | None = None,
    request_scope: dict[str, object] | None = None,
    source_valid_from: datetime | None = datetime(2024, 1, 1, tzinfo=UTC),
    source_valid_to: datetime | None = datetime(2025, 1, 1, tzinfo=UTC),
    known_at: datetime = datetime(2026, 3, 2, tzinfo=UTC),
) -> SyntheticTerritorialCaptureRequest:
    organization_id = OrganizationId.new()
    property_id = TypedId.new("rural_property")
    geometry_id = TypedId.new("property_geometry")
    return SyntheticTerritorialCaptureRequest(
        organization_id=organization_id,
        property_id=property_id,
        geometry_id=geometry_id,
        geometry_version=1,
        profile=profile,
        request_scope=request_scope
        or {
            "property_id": property_id.value.hex,
            "geometry_id": geometry_id.value.hex,
            "geometry_version": 1,
            "layer": profile.value,
            "operation": "TIMELINE",
            "requested_years": [2024],
        },
        response_payload=response_payload
        or {
            "property_area_hectares": 1000.0,
            "years": [
                {
                    "year": 2024,
                    "feature_count": 1,
                    "source_area_hectares": 12.5,
                    "overlap_area_hectares": 4.2,
                    "source_version_ids": ["PRODES_TEST_2024_V1"],
                }
            ],
        },
        captured_at=datetime(2026, 3, 1, tzinfo=UTC),
        known_at=known_at,
        source_valid_from=source_valid_from,
        source_valid_to=source_valid_to,
        recorded_at=known_at,
    )


def test_timeline_like_adapter_produces_canonical_capture() -> None:
    capture = SyntheticTerritorialCaptureAdapter().capture(_request())

    assert capture.source_layer == TERRITORIAL_TEST_TIMELINE_LAYER
    assert capture.operation == "TIMELINE"
    assert capture.response_schema == TERRITORIAL_RESPONSE_SCHEMA
    assert capture.source_version_ids == ("PRODES_TEST_2024_V1",)
    assert capture.response_summary["profile"] == "PRODES_LIKE_TIMELINE"
    assert capture.response_summary["layer"] == "PRODES_LIKE"
    assert capture.response_summary["years"][0]["overlap_area_hectares"] == 4.2
    assert SyntheticTerritorialAdapterLimitation.SYNTHETIC_TERRITORIAL_SOURCE in {
        SyntheticTerritorialAdapterLimitation(item) for item in capture.limitations
    }


def test_request_scope_digest_is_stable_when_keys_are_reordered() -> None:
    first = {
        "property_id": "p1",
        "geometry_id": "g1",
        "geometry_version": 1,
        "requested_years": [2024, 2025],
    }
    second = {
        "requested_years": [2024, 2025],
        "geometry_version": 1,
        "geometry_id": "g1",
        "property_id": "p1",
    }

    assert synthetic_territorial_request_scope_digest(first) == (
        synthetic_territorial_request_scope_digest(second)
    )


def test_response_digest_changes_when_material_value_changes() -> None:
    payload = {
        "property_area_hectares": 1000.0,
        "years": [
            {
                "year": 2024,
                "feature_count": 1,
                "source_area_hectares": 12.5,
                "overlap_area_hectares": 4.2,
                "source_version_ids": ["PRODES_TEST_2024_V1"],
            }
        ],
    }
    changed = {
        **payload,
        "years": [
            {
                "year": 2024,
                "feature_count": 2,
                "source_area_hectares": 12.5,
                "overlap_area_hectares": 4.2,
                "source_version_ids": ["PRODES_TEST_2024_V1"],
            }
        ],
    }

    assert synthetic_territorial_response_digest_for_payload(
        SyntheticTerritorialAdapterProfile.PRODES_LIKE_TIMELINE, payload
    ) != synthetic_territorial_response_digest_for_payload(
        SyntheticTerritorialAdapterProfile.PRODES_LIKE_TIMELINE, changed
    )


def test_known_at_controls_temporal_selection_independently_from_source_validity() -> None:
    request = _request(
        source_valid_from=datetime(2024, 1, 1, tzinfo=UTC),
        source_valid_to=datetime(2025, 1, 1, tzinfo=UTC),
        known_at=datetime(2026, 3, 2, tzinfo=UTC),
    )
    capture = SyntheticTerritorialCaptureAdapter().capture(request)

    selection = TemporalTerritorialCaptureReader(_CaptureRepo([capture])).select(
        request.organization_id,
        request.property_id,
        reference_time=datetime(2024, 6, 1, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 3, 1, tzinfo=UTC),
    )

    assert selection.limitation is TemporalTerritorialCaptureLimitation.ABSENT_AT_CONTEXT


def test_overlap_without_features_is_not_normative_clean_state() -> None:
    request = _request(
        profile=SyntheticTerritorialAdapterProfile.FUNAI_LIKE_OVERLAP,
        request_scope={"layer": "FUNAI_LIKE", "operation": "OVERLAP"},
        response_payload={
            "feature_count": 0,
            "property_area_hectares": 1000.0,
            "overlap_area_hectares": 0.0,
            "source_version_ids": ["FUNAI_TEST_2026_V1"],
        },
        source_valid_from=None,
        source_valid_to=None,
    )

    capture = SyntheticTerritorialCaptureAdapter().capture(request)

    assert capture.source_layer == TERRITORIAL_TEST_OVERLAP_LAYER
    assert capture.response_summary["feature_count"] == 0
    assert "SEM_RESTRICAO" not in capture.response_summary
    assert "conclusion" not in capture.response_summary
    assert "NO_EXTERNAL_RECOGNITION_ASSERTED" in capture.limitations
    assert "SOURCE_INTERVAL_NOT_DECLARED" in capture.limitations


def test_missing_source_version_creates_limitation_without_inventing_version() -> None:
    request = _request(
        response_payload={
            "property_area_hectares": 1000.0,
            "years": [
                {
                    "year": 2024,
                    "feature_count": 1,
                    "source_area_hectares": 12.5,
                    "overlap_area_hectares": 4.2,
                }
            ],
        }
    )

    capture = SyntheticTerritorialCaptureAdapter().capture(request)

    assert capture.source_version_ids == ()
    assert "SOURCE_VERSION_DECLARED_BY_TEST_FIXTURE" in capture.limitations
