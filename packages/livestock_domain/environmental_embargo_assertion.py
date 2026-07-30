"""Assercao auditavel de embargo ambiental sobre propriedade.

E o congelamento de uma observacao espacial, nao uma decisao normativa. O Titan
preserva qual geometria usou, qual base declarou a restricao e o material
essencial devolvido pela consulta, para que regras futuras possam citar um fato
estavel sem depender de nova chamada online.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class EnvironmentalEmbargoAssertionStatus(StrEnum):
    COM_RESTRICAO = "COM_RESTRICAO"
    SEM_RESTRICAO = "SEM_RESTRICAO"
    INDETERMINADA = "INDETERMINADA"


@dataclass(frozen=True, slots=True)
class PropertyEnvironmentalEmbargoAssertion:
    assertion_id: TypedId
    organization_id: OrganizationId
    property_id: TypedId
    geometry_id: TypedId | None
    geometry_version: int | None
    source_name: str
    source_layer: str
    operation: str
    status: EnvironmentalEmbargoAssertionStatus
    source_digest: str | None
    response_digest: str | None
    version_ids: tuple[str, ...]
    restrictions_payload: tuple[MappingProxyType[str, Any], ...] = ()
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.observed_at, field_name="observed_at")
        require_utc(self.recorded_at, field_name="recorded_at")
        if self.assertion_id.entity_type != "property_environmental_embargo_assertion":
            raise ValueError(
                "assertion_id deve ter entity_type 'property_environmental_embargo_assertion'."
            )
        if self.property_id.entity_type != "rural_property":
            raise ValueError("property_id deve ter entity_type 'rural_property'.")
        if self.geometry_id is not None and self.geometry_id.entity_type != "property_geometry":
            raise ValueError("geometry_id deve ter entity_type 'property_geometry'.")
        if self.geometry_version is not None and self.geometry_version < 1:
            raise ValueError("geometry_version deve ser >= 1.")
        if not self.source_name.strip():
            raise ValueError("source_name nao pode ser vazio.")
        if not self.source_layer.strip():
            raise ValueError("source_layer nao pode ser vazio.")
        if not self.operation.strip():
            raise ValueError("operation nao pode ser vazia.")
        if not isinstance(self.status, EnvironmentalEmbargoAssertionStatus):
            raise TypeError("status deve ser EnvironmentalEmbargoAssertionStatus.")
        if self.source_digest is not None and len(self.source_digest) != 64:
            raise ValueError("source_digest deve ser um SHA-256 em hexadecimal.")
        if self.response_digest is not None and len(self.response_digest) != 64:
            raise ValueError("response_digest deve ser um SHA-256 em hexadecimal.")

    @property
    def restriction_count(self) -> int:
        return len(self.restrictions_payload)

    @classmethod
    def create(
        cls,
        *,
        organization_id: OrganizationId,
        property_id: TypedId,
        geometry_id: TypedId | None,
        geometry_version: int | None,
        source_name: str,
        source_layer: str,
        operation: str,
        status: EnvironmentalEmbargoAssertionStatus,
        source_digest: str | None,
        response_digest: str | None,
        version_ids: tuple[str, ...],
        restrictions_payload: tuple[dict[str, Any], ...] = (),
        observed_at: datetime,
    ) -> "PropertyEnvironmentalEmbargoAssertion":
        return cls(
            assertion_id=TypedId.new("property_environmental_embargo_assertion"),
            organization_id=organization_id,
            property_id=property_id,
            geometry_id=geometry_id,
            geometry_version=geometry_version,
            source_name=source_name.strip(),
            source_layer=source_layer.strip(),
            operation=operation.strip(),
            status=status,
            source_digest=source_digest,
            response_digest=response_digest,
            version_ids=tuple(version_ids),
            restrictions_payload=tuple(
                MappingProxyType(dict(item)) for item in restrictions_payload
            ),
            observed_at=observed_at,
        )
