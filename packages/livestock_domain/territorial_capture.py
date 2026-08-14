"""Captura territorial versionada para reconstrucao historica sintetica."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Any

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class TerritorialCaptureEnvironment(StrEnum):
    SYNTHETIC = "SYNTHETIC"


class TerritorialCaptureKind(StrEnum):
    TIMELINE = "TIMELINE"
    OVERLAP = "OVERLAP"


TERRITORIAL_TEST_SOURCE = "TERRITORIAL_TEST_SOURCE"
TERRITORIAL_TEST_TIMELINE_LAYER = "TERRITORIAL_TEST_TIMELINE"
TERRITORIAL_TEST_OVERLAP_LAYER = "TERRITORIAL_TEST_OVERLAP"


def territorial_response_digest(response_summary: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        thaw_territorial_response_summary(response_summary),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(canonical.encode()).hexdigest()


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("response_summary possui chave nao textual.")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError("response_summary possui valor nao serializavel.")


def thaw_territorial_response_summary(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw_territorial_response_summary(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_territorial_response_summary(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class TerritorialSourceCapture:
    capture_id: TypedId
    organization_id: OrganizationId
    property_id: TypedId
    geometry_id: TypedId
    geometry_version: int
    source_profile_code: str
    source_environment: TerritorialCaptureEnvironment
    source_name: str
    source_layer: str
    kind: TerritorialCaptureKind
    operation: str
    request_scope_digest: str
    response_digest: str
    response_summary: MappingProxyType[str, Any]
    source_version_ids: tuple[str, ...]
    captured_at: datetime
    known_at: datetime
    source_valid_from: datetime | None = None
    source_valid_to: datetime | None = None
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_utc(self.captured_at, field_name="captured_at")
        require_utc(self.known_at, field_name="known_at")
        require_utc(self.recorded_at, field_name="recorded_at")
        if self.source_valid_from is not None:
            require_utc(self.source_valid_from, field_name="source_valid_from")
        if self.source_valid_to is not None:
            require_utc(self.source_valid_to, field_name="source_valid_to")
        if self.capture_id.entity_type != "territorial_source_capture":
            raise ValueError("capture_id deve ser territorial_source_capture.")
        if self.property_id.entity_type != "rural_property":
            raise ValueError("property_id deve ser rural_property.")
        if self.geometry_id.entity_type != "property_geometry":
            raise ValueError("geometry_id deve ser property_geometry.")
        if self.geometry_version < 1:
            raise ValueError("geometry_version deve ser >= 1.")
        if self.source_environment is not TerritorialCaptureEnvironment.SYNTHETIC:
            raise ValueError("O primeiro corte aceita somente ambiente SYNTHETIC.")
        if self.source_profile_code != TERRITORIAL_TEST_SOURCE:
            raise ValueError("O primeiro corte aceita apenas TERRITORIAL_TEST_SOURCE.")
        if self.source_layer not in {
            TERRITORIAL_TEST_TIMELINE_LAYER,
            TERRITORIAL_TEST_OVERLAP_LAYER,
        }:
            raise ValueError("Camada territorial sintetica nao suportada.")
        if (
            self.kind is TerritorialCaptureKind.TIMELINE
            and self.source_layer != TERRITORIAL_TEST_TIMELINE_LAYER
        ):
            raise ValueError("Captura TIMELINE exige camada TERRITORIAL_TEST_TIMELINE.")
        if (
            self.kind is TerritorialCaptureKind.OVERLAP
            and self.source_layer != TERRITORIAL_TEST_OVERLAP_LAYER
        ):
            raise ValueError("Captura OVERLAP exige camada TERRITORIAL_TEST_OVERLAP.")
        for name in ("source_name", "source_layer", "operation"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} nao pode ser vazio.")
        for name in ("request_scope_digest", "response_digest"):
            digest = getattr(self, name)
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError(f"{name} deve ser SHA-256 hexadecimal.")
        if self.source_valid_from is not None and self.source_valid_to is not None:
            if self.source_valid_to <= self.source_valid_from:
                raise ValueError("source_valid_to deve ser posterior a source_valid_from.")
        if any(not item.strip() for item in self.source_version_ids):
            raise ValueError("source_version_ids nao pode conter item vazio.")
        if any(not item.strip() for item in self.limitations):
            raise ValueError("limitations nao pode conter item vazio.")
        frozen = _freeze(self.response_summary)
        if not isinstance(frozen, MappingProxyType):
            raise TypeError("response_summary deve ser objeto.")
        object.__setattr__(self, "response_summary", frozen)
        if self.response_digest != territorial_response_digest(frozen):
            raise ValueError("response_digest nao confere com response_summary.")

    @classmethod
    def create_synthetic(
        cls,
        *,
        organization_id: OrganizationId,
        property_id: TypedId,
        geometry_id: TypedId,
        geometry_version: int,
        source_layer: str,
        kind: TerritorialCaptureKind,
        operation: str,
        request_scope_digest: str,
        response_summary: Mapping[str, Any],
        source_version_ids: tuple[str, ...],
        captured_at: datetime,
        known_at: datetime,
        source_valid_from: datetime | None = None,
        source_valid_to: datetime | None = None,
        recorded_at: datetime | None = None,
        limitations: tuple[str, ...] = (),
    ) -> "TerritorialSourceCapture":
        return cls(
            capture_id=TypedId.new("territorial_source_capture"),
            organization_id=organization_id,
            property_id=property_id,
            geometry_id=geometry_id,
            geometry_version=geometry_version,
            source_profile_code=TERRITORIAL_TEST_SOURCE,
            source_environment=TerritorialCaptureEnvironment.SYNTHETIC,
            source_name=TERRITORIAL_TEST_SOURCE,
            source_layer=source_layer,
            kind=kind,
            operation=operation,
            request_scope_digest=request_scope_digest,
            response_digest=territorial_response_digest(response_summary),
            response_summary=MappingProxyType(dict(response_summary)),
            source_version_ids=source_version_ids,
            captured_at=captured_at,
            known_at=known_at,
            source_valid_from=source_valid_from,
            source_valid_to=source_valid_to,
            recorded_at=datetime.now(UTC) if recorded_at is None else recorded_at,
            limitations=limitations,
        )
