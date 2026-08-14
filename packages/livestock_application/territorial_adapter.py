"""Adapter territorial sintetico-realista para T-05D Corte 3."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any

from packages.livestock_domain.territorial_capture import (
    TERRITORIAL_TEST_OVERLAP_LAYER,
    TERRITORIAL_TEST_TIMELINE_LAYER,
    TerritorialCaptureKind,
    TerritorialSourceCapture,
    territorial_response_digest,
)
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.serialization import CanonicalSerializer, canonicalize_for_hash
from packages.shared_kernel.temporal import require_utc


class SyntheticTerritorialAdapterProfile(StrEnum):
    PRODES_LIKE_TIMELINE = "PRODES_LIKE_TIMELINE"
    DETER_LIKE_TIMELINE = "DETER_LIKE_TIMELINE"
    FUNAI_LIKE_OVERLAP = "FUNAI_LIKE_OVERLAP"
    IBAMA_LIKE_OVERLAP = "IBAMA_LIKE_OVERLAP"


class SyntheticTerritorialAdapterLimitation(StrEnum):
    SYNTHETIC_TERRITORIAL_SOURCE = "SYNTHETIC_TERRITORIAL_SOURCE"
    NO_EXTERNAL_RECOGNITION_ASSERTED = "NO_EXTERNAL_RECOGNITION_ASSERTED"
    SOURCE_INTERVAL_NOT_DECLARED = "SOURCE_INTERVAL_NOT_DECLARED"
    SOURCE_VERSION_DECLARED_BY_TEST_FIXTURE = "SOURCE_VERSION_DECLARED_BY_TEST_FIXTURE"
    RAW_SOURCE_BYTES_NOT_PRESERVED = "RAW_SOURCE_BYTES_NOT_PRESERVED"
    GEOMETRY_ACCURACY_NOT_REEVALUATED = "GEOMETRY_ACCURACY_NOT_REEVALUATED"


@dataclass(frozen=True, slots=True)
class SyntheticTerritorialCaptureRequest:
    organization_id: OrganizationId
    property_id: TypedId
    geometry_id: TypedId
    geometry_version: int
    profile: SyntheticTerritorialAdapterProfile
    request_scope: Mapping[str, Any]
    response_payload: Mapping[str, Any]
    captured_at: datetime
    known_at: datetime
    source_valid_from: datetime | None = None
    source_valid_to: datetime | None = None
    recorded_at: datetime | None = None
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SyntheticTerritorialCaptureAdapter:
    """Normaliza payloads controlados em `TerritorialSourceCapture`.

    O adapter nao consulta fonte externa e nao decide conformidade. Ele apenas
    transforma um payload sintetico-realista em material historico preservavel.
    """

    def capture(self, request: SyntheticTerritorialCaptureRequest) -> TerritorialSourceCapture:
        _validate_request(request)
        response_summary = _response_summary(request.profile, request.response_payload)
        source_version_ids = _source_version_ids(request.profile, response_summary)
        limitations = _limitations(
            request.limitations,
            source_valid_from=request.source_valid_from,
            source_valid_to=request.source_valid_to,
            source_version_ids=source_version_ids,
        )
        kind = _kind(request.profile)
        source_layer = _source_layer(kind)
        return TerritorialSourceCapture.create_synthetic(
            organization_id=request.organization_id,
            property_id=request.property_id,
            geometry_id=request.geometry_id,
            geometry_version=request.geometry_version,
            source_layer=source_layer,
            kind=kind,
            operation=kind.value,
            request_scope_digest=synthetic_territorial_request_scope_digest(request.request_scope),
            response_summary=response_summary,
            source_version_ids=source_version_ids,
            captured_at=request.captured_at,
            known_at=request.known_at,
            source_valid_from=request.source_valid_from,
            source_valid_to=request.source_valid_to,
            recorded_at=request.recorded_at or datetime.now(UTC),
            limitations=limitations,
        )


def synthetic_territorial_request_scope_digest(request_scope: Mapping[str, Any]) -> str:
    material = CanonicalSerializer().serialize(canonicalize_for_hash(request_scope))
    return sha256(material).hexdigest()


def synthetic_territorial_response_digest_for_payload(
    profile: SyntheticTerritorialAdapterProfile, response_payload: Mapping[str, Any]
) -> str:
    return territorial_response_digest(_response_summary(profile, response_payload))


def _validate_request(request: SyntheticTerritorialCaptureRequest) -> None:
    require_utc(request.captured_at, field_name="captured_at")
    require_utc(request.known_at, field_name="known_at")
    if request.recorded_at is not None:
        require_utc(request.recorded_at, field_name="recorded_at")
    if request.source_valid_from is not None:
        require_utc(request.source_valid_from, field_name="source_valid_from")
    if request.source_valid_to is not None:
        require_utc(request.source_valid_to, field_name="source_valid_to")
    if request.property_id.entity_type != "rural_property":
        raise ValueError("property_id deve ser rural_property.")
    if request.geometry_id.entity_type != "property_geometry":
        raise ValueError("geometry_id deve ser property_geometry.")
    if request.geometry_version < 1:
        raise ValueError("geometry_version deve ser >= 1.")
    if not request.request_scope:
        raise ValueError("request_scope nao pode ser vazio.")


def _kind(profile: SyntheticTerritorialAdapterProfile) -> TerritorialCaptureKind:
    if profile in {
        SyntheticTerritorialAdapterProfile.PRODES_LIKE_TIMELINE,
        SyntheticTerritorialAdapterProfile.DETER_LIKE_TIMELINE,
    }:
        return TerritorialCaptureKind.TIMELINE
    return TerritorialCaptureKind.OVERLAP


def _source_layer(kind: TerritorialCaptureKind) -> str:
    if kind is TerritorialCaptureKind.TIMELINE:
        return TERRITORIAL_TEST_TIMELINE_LAYER
    return TERRITORIAL_TEST_OVERLAP_LAYER


def _response_summary(
    profile: SyntheticTerritorialAdapterProfile, response_payload: Mapping[str, Any]
) -> dict[str, Any]:
    if _kind(profile) is TerritorialCaptureKind.TIMELINE:
        return _timeline_summary(profile, response_payload)
    return _overlap_summary(profile, response_payload)


def _timeline_summary(
    profile: SyntheticTerritorialAdapterProfile, response_payload: Mapping[str, Any]
) -> dict[str, Any]:
    years = response_payload.get("years")
    if not isinstance(years, Sequence) or isinstance(years, str):
        raise ValueError("Payload timeline exige years como lista.")
    normalized_years: list[dict[str, Any]] = []
    for item in years:
        if not isinstance(item, Mapping):
            raise ValueError("Cada item de years deve ser objeto.")
        normalized_years.append(
            {
                "year": _required_int(item, "year"),
                "feature_count": _required_int(item, "feature_count"),
                "source_area_hectares": _optional_number(item, "source_area_hectares"),
                "overlap_area_hectares": _optional_number(item, "overlap_area_hectares"),
                "source_version_ids": _string_list(item.get("source_version_ids", ())),
            }
        )
    return {
        "profile": profile.value,
        "layer": _profile_layer(profile),
        "operation": TerritorialCaptureKind.TIMELINE.value,
        "property_area_hectares": _optional_number(response_payload, "property_area_hectares"),
        "years": normalized_years,
    }


def _overlap_summary(
    profile: SyntheticTerritorialAdapterProfile, response_payload: Mapping[str, Any]
) -> dict[str, Any]:
    overlap_area = _optional_number(response_payload, "overlap_area_hectares")
    property_area = _optional_number(response_payload, "property_area_hectares")
    overlap_ratio = _optional_number(response_payload, "overlap_ratio")
    if overlap_ratio is None and overlap_area is not None and property_area not in (None, 0):
        overlap_ratio = overlap_area / property_area
    return {
        "profile": profile.value,
        "layer": _profile_layer(profile),
        "operation": TerritorialCaptureKind.OVERLAP.value,
        "feature_count": _required_int(response_payload, "feature_count"),
        "property_area_hectares": property_area,
        "overlap_area_hectares": overlap_area,
        "overlap_ratio": overlap_ratio,
        "source_version_ids": _string_list(response_payload.get("source_version_ids", ())),
    }


def _profile_layer(profile: SyntheticTerritorialAdapterProfile) -> str:
    return profile.value.removesuffix("_TIMELINE").removesuffix("_OVERLAP")


def _source_version_ids(
    profile: SyntheticTerritorialAdapterProfile, response_summary: Mapping[str, Any]
) -> tuple[str, ...]:
    if _kind(profile) is TerritorialCaptureKind.OVERLAP:
        return tuple(_string_list(response_summary.get("source_version_ids", ())))
    versions: list[str] = []
    years = response_summary.get("years", ())
    if isinstance(years, Sequence) and not isinstance(years, str):
        for item in years:
            if isinstance(item, Mapping):
                versions.extend(_string_list(item.get("source_version_ids", ())))
    return tuple(dict.fromkeys(versions))


def _limitations(
    explicit_limitations: tuple[str, ...],
    *,
    source_valid_from: datetime | None,
    source_valid_to: datetime | None,
    source_version_ids: tuple[str, ...],
) -> tuple[str, ...]:
    values = [
        SyntheticTerritorialAdapterLimitation.SYNTHETIC_TERRITORIAL_SOURCE.value,
        SyntheticTerritorialAdapterLimitation.NO_EXTERNAL_RECOGNITION_ASSERTED.value,
        SyntheticTerritorialAdapterLimitation.RAW_SOURCE_BYTES_NOT_PRESERVED.value,
        SyntheticTerritorialAdapterLimitation.GEOMETRY_ACCURACY_NOT_REEVALUATED.value,
    ]
    if source_valid_from is None and source_valid_to is None:
        values.append(SyntheticTerritorialAdapterLimitation.SOURCE_INTERVAL_NOT_DECLARED.value)
    if not source_version_ids:
        values.append(
            SyntheticTerritorialAdapterLimitation.SOURCE_VERSION_DECLARED_BY_TEST_FIXTURE.value
        )
    values.extend(explicit_limitations)
    return tuple(dict.fromkeys(values))


def _required_int(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise ValueError(f"{key} deve ser inteiro.")
    return item


def _optional_number(value: Mapping[str, Any], key: str) -> float | None:
    item = value.get(key)
    if item is None:
        return None
    if isinstance(item, bool) or not isinstance(item, int | float):
        raise ValueError(f"{key} deve ser numerico.")
    return float(item)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("source_version_ids deve ser lista de strings.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("source_version_ids deve conter strings nao vazias.")
        result.append(item)
    return result
