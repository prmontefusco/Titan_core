"""Selecao historica de capturas territoriais sinteticas."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from packages.core_domain.facts import Fact
from packages.livestock_domain.territorial_capture import (
    TerritorialCaptureKind,
    TerritorialSourceCapture,
    thaw_territorial_response_summary,
)
from packages.shared_kernel import OrganizationId, TypedId

TEMPORAL_TERRITORIAL_TEST_TIMELINE_FACT_TYPE = "livestock.territorial.test_timeline"
TEMPORAL_TERRITORIAL_TEST_OVERLAP_FACT_TYPE = "livestock.territorial.test_overlap"


class TemporalTerritorialCaptureLimitation(StrEnum):
    ABSENT_AT_CONTEXT = "LIVESTOCK_TEMPORAL_TERRITORIAL_CAPTURE_ABSENT_AT_CONTEXT"
    CONFLICT = "LIVESTOCK_TEMPORAL_TERRITORIAL_CAPTURE_CONFLICT"


class TerritorialSourceCaptureRepositoryPort(Protocol):
    def list_by_property(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> list[TerritorialSourceCapture]: ...


@dataclass(frozen=True, slots=True)
class TemporalTerritorialCaptureSelection:
    captures: tuple[TerritorialSourceCapture, ...]
    limitation: TemporalTerritorialCaptureLimitation | None


@dataclass(frozen=True, slots=True)
class TemporalTerritorialCaptureReader:
    repository: TerritorialSourceCaptureRepositoryPort

    def select(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
        *,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> TemporalTerritorialCaptureSelection:
        eligible = [
            capture
            for capture in self.repository.list_by_property(organization_id, property_id)
            if _is_eligible(
                capture,
                organization_id,
                property_id,
                reference_time=reference_time,
                knowledge_cutoff=knowledge_cutoff,
            )
        ]
        if not eligible:
            return TemporalTerritorialCaptureSelection(
                (), TemporalTerritorialCaptureLimitation.ABSENT_AT_CONTEXT
            )
        if _has_conflict(eligible):
            return TemporalTerritorialCaptureSelection(
                (), TemporalTerritorialCaptureLimitation.CONFLICT
            )
        return TemporalTerritorialCaptureSelection(
            tuple(
                sorted(
                    eligible,
                    key=lambda item: (
                        item.source_name,
                        item.source_layer,
                        item.operation,
                        item.capture_id.value.hex,
                    ),
                )
            ),
            None,
        )


def facts_from_temporal_territorial_selection(
    selection: TemporalTerritorialCaptureSelection,
) -> tuple[Fact, ...]:
    if selection.limitation is not None:
        raise ValueError("Selecao territorial limitada nao pode produzir fatos.")
    return tuple(_fact_from_capture(capture) for capture in selection.captures)


def _is_eligible(
    capture: TerritorialSourceCapture,
    organization_id: OrganizationId,
    property_id: TypedId,
    *,
    reference_time: datetime,
    knowledge_cutoff: datetime,
) -> bool:
    if capture.organization_id != organization_id or capture.property_id != property_id:
        return False
    if capture.captured_at > reference_time or capture.known_at > knowledge_cutoff:
        return False
    if capture.source_valid_from is not None and capture.source_valid_from > reference_time:
        return False
    return not (capture.source_valid_to is not None and reference_time >= capture.source_valid_to)


def _has_conflict(captures: list[TerritorialSourceCapture]) -> bool:
    seen: set[tuple[TypedId, int, str, str, str, TerritorialCaptureKind]] = set()
    for capture in captures:
        key = (
            capture.geometry_id,
            capture.geometry_version,
            capture.source_name,
            capture.source_layer,
            capture.operation,
            capture.kind,
        )
        if key in seen:
            return True
        seen.add(key)
    return False


def _fact_from_capture(capture: TerritorialSourceCapture) -> Fact:
    return Fact.create(
        fact_type=_fact_type(capture.kind),
        payload={
            "capture_id": capture.capture_id.value.hex,
            "property_id": capture.property_id.value.hex,
            "geometry_id": capture.geometry_id.value.hex,
            "geometry_version": capture.geometry_version,
            "source_profile_code": capture.source_profile_code,
            "source_name": capture.source_name,
            "source_layer": capture.source_layer,
            "operation": capture.operation,
            "request_scope_digest": capture.request_scope_digest,
            "response_digest": capture.response_digest,
            "response_summary": thaw_territorial_response_summary(capture.response_summary),
            "source_version_ids": list(capture.source_version_ids),
            "captured_at": capture.captured_at.isoformat(),
            "known_at": capture.known_at.isoformat(),
            "source_valid_from": (
                None if capture.source_valid_from is None else capture.source_valid_from.isoformat()
            ),
            "source_valid_to": (
                None if capture.source_valid_to is None else capture.source_valid_to.isoformat()
            ),
            "limitations": list(capture.limitations),
            "derivation": "TEMPORAL_TERRITORIAL_CAPTURE_V1",
        },
        observed_at=(
            capture.source_valid_from
            if capture.source_valid_from is not None
            else capture.captured_at
        ),
        recorded_at=max(capture.known_at, capture.recorded_at),
    )


def _fact_type(kind: TerritorialCaptureKind) -> str:
    if kind is TerritorialCaptureKind.TIMELINE:
        return TEMPORAL_TERRITORIAL_TEST_TIMELINE_FACT_TYPE
    return TEMPORAL_TERRITORIAL_TEST_OVERLAP_FACT_TYPE
