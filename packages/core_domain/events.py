"""Contrato universal e imutável de eventos de domínio."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from packages.shared_kernel import (
    CanonicalSerializer,
    OrganizationId,
    RecordTimestamps,
    TypedId,
    UniversalReference,
)
from packages.shared_kernel.serialization import CanonicalValue

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_SECRET_KEYS = frozenset(
    {
        "access_token",
        "client_secret",
        "id_token",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "token",
    }
)


def _require_positive_version(value: int, *, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} deve ser um número inteiro.")
    if value < 1:
        raise ValueError(f"{field_name} deve ser maior ou igual a 1.")


def _require_typed_id(value: TypedId, *, entity_type: str, field_name: str) -> None:
    if not isinstance(value, TypedId):
        raise TypeError(f"{field_name} deve ser um TypedId.")
    if value.entity_type != entity_type:
        raise ValueError(f"{field_name} deve possuir tipo lógico {entity_type!r}.")


def _contains_secret_key(value: CanonicalValue) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key.casefold() in _SECRET_KEYS or _contains_secret_key(item):
                return True
        return False
    if isinstance(value, Sequence) and not isinstance(value, str):
        return any(_contains_secret_key(item) for item in value)
    return False


@dataclass(frozen=True, slots=True, init=False)
class CanonicalPayload:
    """Payload mínimo preservado como bytes canônicos e versionados."""

    schema: str
    version: int
    canonical_bytes: bytes

    def __init__(
        self,
        *,
        schema: str,
        version: int,
        value: Mapping[str, CanonicalValue],
        serializer: CanonicalSerializer | None = None,
    ) -> None:
        if not isinstance(schema, str):
            raise TypeError("schema deve ser texto.")
        if not _NAME_PATTERN.fullmatch(schema):
            raise ValueError("schema deve usar nome canônico em minúsculas.")
        _require_positive_version(version, field_name="version")
        if not isinstance(value, Mapping):
            raise TypeError("O payload de evento deve ser um mapa.")
        selected_serializer = serializer or CanonicalSerializer()
        canonical_bytes = selected_serializer.serialize(
            {"data": value, "schema": schema, "version": version}
        )
        if _contains_secret_key(value):
            raise ValueError("O payload contém chave reservada para segredo ou credencial.")
        object.__setattr__(self, "schema", schema)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "canonical_bytes", canonical_bytes)

    @classmethod
    def from_mapping(
        cls,
        *,
        schema: str,
        version: int,
        value: Mapping[str, CanonicalValue],
        serializer: CanonicalSerializer | None = None,
    ) -> "CanonicalPayload":
        return cls(
            schema=schema,
            version=version,
            value=value,
            serializer=serializer,
        )


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Algo relevante que ocorreu no domínio após uma operação válida."""

    event_id: TypedId
    organization_id: OrganizationId
    aggregate_reference: UniversalReference
    aggregate_version: int
    event_type: str
    event_version: int
    timestamps: RecordTimestamps
    actor_reference: UniversalReference
    source_reference: UniversalReference
    correlation_id: TypedId
    causation_id: TypedId | None
    payload: CanonicalPayload

    def __post_init__(self) -> None:
        _require_typed_id(self.event_id, entity_type="domain_event", field_name="event_id")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser um OrganizationId.")
        if not isinstance(self.aggregate_reference, UniversalReference):
            raise TypeError("aggregate_reference deve ser uma UniversalReference.")
        if self.aggregate_reference.organization_id != self.organization_id:
            raise ValueError("O agregado deve pertencer à Organization do evento.")
        _require_positive_version(self.aggregate_version, field_name="aggregate_version")
        if not isinstance(self.event_type, str):
            raise TypeError("event_type deve ser texto.")
        if not _NAME_PATTERN.fullmatch(self.event_type):
            raise ValueError("event_type deve usar nome canônico em minúsculas.")
        _require_positive_version(self.event_version, field_name="event_version")
        if not isinstance(self.timestamps, RecordTimestamps):
            raise TypeError("timestamps deve ser um RecordTimestamps.")
        if not isinstance(self.actor_reference, UniversalReference):
            raise TypeError("actor_reference deve ser uma UniversalReference.")
        if not isinstance(self.source_reference, UniversalReference):
            raise TypeError("source_reference deve ser uma UniversalReference.")
        _require_typed_id(
            self.correlation_id,
            entity_type="correlation",
            field_name="correlation_id",
        )
        if self.causation_id is not None:
            _require_typed_id(
                self.causation_id,
                entity_type="domain_event",
                field_name="causation_id",
            )
        if not isinstance(self.payload, CanonicalPayload):
            raise TypeError("payload deve ser um CanonicalPayload.")
