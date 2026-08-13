"""Reconstrução temporal estrita do lifecycle de identificadores de Animal."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from packages.core_application.event_log import CanonicalDomainEventReader, RecordedCanonicalEvent
from packages.livestock_application.event_recorder import AGGREGATE_CONTRACT_VERSION
from packages.livestock_domain.animal import IdentifierType
from packages.livestock_domain.events import IDENTIFIER_ATTACHED, IDENTIFIER_DEACTIVATED
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

TEMPORAL_IDENTIFIER_FACT_TYPE = "livestock.identifier_history"
_CANONICAL_SERIALIZATION_VERSION = "titan-json-v1"
_PAYLOAD_VERSION = 1


class TemporalIdentifierLimitation(StrEnum):
    SOURCE_UNAVAILABLE = "LIVESTOCK_IDENTIFIER_HISTORY_SOURCE_UNAVAILABLE"
    ABSENT_AT_CONTEXT = "LIVESTOCK_IDENTIFIER_HISTORY_ABSENT_AT_CONTEXT"
    INVALID_EVENT = "LIVESTOCK_IDENTIFIER_HISTORY_INVALID_EVENT"
    CONFLICT = "LIVESTOCK_IDENTIFIER_HISTORY_CONFLICT"


@dataclass(frozen=True, slots=True)
class HistoricalAnimalIdentifier:
    identifier_id: TypedId
    identifier_type: IdentifierType
    identifier_value: str
    attached_event_id: TypedId
    attached_payload_digest: str


@dataclass(frozen=True, slots=True)
class TemporalIdentifierSelection:
    identifiers: tuple[HistoricalAnimalIdentifier, ...]
    supporting_event_ids: tuple[TypedId, ...]
    supporting_payload_digests: tuple[str, ...]
    observed_at: datetime | None
    recorded_at: datetime | None
    limitation: TemporalIdentifierLimitation | None


@dataclass(frozen=True, slots=True)
class TemporalAnimalIdentifierReader:
    """Interpreta somente os dois schemas Livestock aprovados pela ADR-0062."""

    event_reader: CanonicalDomainEventReader

    def select(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        *,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> TemporalIdentifierSelection:
        reference = UniversalReference(
            target_id=animal_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        events = self.event_reader.list_canonical_for_aggregate(reference)
        eligible = tuple(
            event
            for event in events
            if event.occurred_at <= reference_time and event.recorded_at <= knowledge_cutoff
        )
        if not eligible:
            return _empty(TemporalIdentifierLimitation.ABSENT_AT_CONTEXT)

        active: dict[TypedId, HistoricalAnimalIdentifier] = {}
        supporting: list[RecordedCanonicalEvent] = []
        for event in eligible:
            if event.aggregate_reference != reference:
                return _empty(TemporalIdentifierLimitation.INVALID_EVENT)
            if event.event_type not in {IDENTIFIER_ATTACHED, IDENTIFIER_DEACTIVATED}:
                continue
            payload = _payload_for(event)
            if payload is None or payload.get("animal_id") != str(animal_id.value):
                return _empty(TemporalIdentifierLimitation.INVALID_EVENT)
            event_time_field = (
                "attached_at" if event.event_type == IDENTIFIER_ATTACHED else "deactivated_at"
            )
            if _as_utc_datetime(payload.get(event_time_field)) != event.occurred_at:
                return _empty(TemporalIdentifierLimitation.INVALID_EVENT)
            identifier_id = _identifier_id(payload.get("identifier_id"))
            if identifier_id is None:
                return _empty(TemporalIdentifierLimitation.INVALID_EVENT)

            if event.event_type == IDENTIFIER_ATTACHED:
                identifier_type = _identifier_type(payload.get("identifier_type"))
                identifier_value = payload.get("identifier_value")
                if (
                    identifier_type is None
                    or not isinstance(identifier_value, str)
                    or not identifier_value.strip()
                    or identifier_id in active
                ):
                    return _empty(TemporalIdentifierLimitation.CONFLICT)
                active[identifier_id] = HistoricalAnimalIdentifier(
                    identifier_id=identifier_id,
                    identifier_type=identifier_type,
                    identifier_value=identifier_value,
                    attached_event_id=event.event_id,
                    attached_payload_digest=event.payload_digest,
                )
            elif identifier_id not in active:
                return _empty(TemporalIdentifierLimitation.CONFLICT)
            else:
                del active[identifier_id]
            supporting.append(event)

        if not supporting:
            return _empty(TemporalIdentifierLimitation.ABSENT_AT_CONTEXT)
        if _has_active_type_conflict(tuple(active.values())):
            return _empty(TemporalIdentifierLimitation.CONFLICT)

        return TemporalIdentifierSelection(
            identifiers=tuple(
                sorted(active.values(), key=lambda item: item.identifier_id.value.hex)
            ),
            supporting_event_ids=tuple(event.event_id for event in supporting),
            supporting_payload_digests=tuple(event.payload_digest for event in supporting),
            observed_at=max(event.occurred_at for event in supporting),
            recorded_at=max(event.recorded_at for event in supporting),
            limitation=None,
        )


def _empty(limitation: TemporalIdentifierLimitation) -> TemporalIdentifierSelection:
    return TemporalIdentifierSelection((), (), (), None, None, limitation)


def _has_active_type_conflict(identifiers: Sequence[HistoricalAnimalIdentifier]) -> bool:
    types = [identifier.identifier_type for identifier in identifiers]
    return len(types) != len(set(types))


def _identifier_id(value: object) -> TypedId | None:
    if not isinstance(value, str):
        return None
    try:
        return TypedId("animal_identifier", UUID(value))
    except ValueError:
        return None


def _identifier_type(value: object) -> IdentifierType | None:
    if not isinstance(value, str):
        return None
    try:
        return IdentifierType(value)
    except ValueError:
        return None


def _payload_for(event: RecordedCanonicalEvent) -> Mapping[str, object] | None:
    expected_schema = f"{event.event_type.replace('.', '_')}_payload"
    if event.payload_schema != expected_schema or event.payload_version != _PAYLOAD_VERSION:
        return None
    try:
        envelope = json.loads(event.payload_canonical_bytes.decode("utf-8"))
        if not isinstance(envelope, list) or len(envelope) != 2:
            return None
        if envelope[0] != _CANONICAL_SERIALIZATION_VERSION:
            return None
        decoded = _decode_canonical(envelope[1])
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(decoded, Mapping):
        return None
    data = decoded.get("data")
    return data if isinstance(data, Mapping) else None


def _decode_canonical(value: object) -> object:
    if not isinstance(value, list) or len(value) != 2 or not isinstance(value[0], str):
        raise ValueError("Valor canônico inválido.")
    tag, raw = value
    if tag == "null" and raw == []:
        return None
    if tag == "string" and isinstance(raw, str):
        return raw
    if tag == "integer" and isinstance(raw, str):
        return int(raw)
    if tag == "datetime" and isinstance(raw, str):
        return _as_utc_datetime(raw)
    if tag == "map" and isinstance(raw, list):
        result: dict[str, object] = {}
        for item in raw:
            if not isinstance(item, list) or len(item) != 2 or not isinstance(item[0], str):
                raise ValueError("Mapa canônico inválido.")
            result[item[0]] = _decode_canonical(item[1])
        return result
    raise ValueError("Tipo canônico não suportado para lifecycle de identificador.")


def _as_utc_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo == UTC else None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo == UTC else None
