"""Persistencia append-only de capturas territoriais sinteticas."""

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.temporal_territorial_capture import (
    TerritorialSourceCaptureRepositoryPort,
)
from packages.livestock_domain.territorial_capture import (
    TERRITORIAL_CANONICALIZATION_VERSION,
    TERRITORIAL_RESPONSE_SCHEMA,
    TERRITORIAL_RESPONSE_SCHEMA_VERSION,
    TERRITORIAL_TEST_OVERLAP_LAYER,
    TERRITORIAL_TEST_SOURCE,
    TERRITORIAL_TEST_TIMELINE_LAYER,
    TerritorialCaptureEnvironment,
    TerritorialCaptureKind,
    TerritorialSourceCapture,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

territorial_source_captures_table = Table(
    "territorial_source_captures",
    livestock_metadata,
    Column("capture_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("property_id", PG_UUID(as_uuid=True), nullable=False),
    Column("geometry_id", PG_UUID(as_uuid=True), nullable=False),
    Column("geometry_version", Integer, nullable=False),
    Column("source_profile_code", String(120), nullable=False),
    Column("source_environment", String(40), nullable=False),
    Column("source_name", String(120), nullable=False),
    Column("source_layer", String(120), nullable=False),
    Column("kind", String(40), nullable=False),
    Column("operation", String(80), nullable=False),
    Column("request_scope_digest", String(64), nullable=False),
    Column("response_schema", String(160), nullable=False),
    Column("response_schema_version", Integer, nullable=False),
    Column("canonicalization_version", String(120), nullable=False),
    Column("response_digest", String(64), nullable=False),
    Column("response_summary", JSONB, nullable=False),
    Column("source_version_ids", JSONB, nullable=False),
    Column("source_valid_from", DateTime(timezone=True), nullable=True),
    Column("source_valid_to", DateTime(timezone=True), nullable=True),
    Column("captured_at", DateTime(timezone=True), nullable=False),
    Column("known_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("limitations", JSONB, nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_territorial_source_captures_organization",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id", "property_id"],
        [
            "core_audit.rural_properties.record_owner_organization_id",
            "core_audit.rural_properties.property_id",
        ],
        name="fk_territorial_source_captures_property_same_owner",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id", "geometry_id"],
        [
            "core_audit.property_geometries.record_owner_organization_id",
            "core_audit.property_geometries.geometry_id",
        ],
        name="fk_territorial_source_captures_geometry_same_owner",
    ),
    CheckConstraint("geometry_version >= 1", name="ck_territorial_capture_geometry_version"),
    CheckConstraint(
        "source_valid_to IS NULL OR source_valid_from IS NULL "
        "OR source_valid_to > source_valid_from",
        name="ck_territorial_capture_source_valid_interval",
    ),
    CheckConstraint(
        "request_scope_digest ~ '^[0-9a-f]{64}$'",
        name="ck_territorial_capture_request_digest",
    ),
    CheckConstraint(
        "response_digest ~ '^[0-9a-f]{64}$'",
        name="ck_territorial_capture_response_digest",
    ),
    CheckConstraint(
        "source_environment = 'SYNTHETIC'",
        name="ck_territorial_capture_environment",
    ),
    CheckConstraint(
        "source_profile_code = 'TERRITORIAL_TEST_SOURCE'",
        name="ck_territorial_capture_source_profile",
    ),
    CheckConstraint(
        "kind IN ('TIMELINE', 'OVERLAP')",
        name="ck_territorial_capture_kind",
    ),
    CheckConstraint(
        "response_schema_version >= 1",
        name="ck_territorial_capture_response_schema_version",
    ),
    CheckConstraint(
        "canonicalization_version = 'TERRITORIAL_RESPONSE_SUMMARY_CANONICAL_JSON_V1'",
        name="ck_territorial_capture_canonicalization",
    ),
    CheckConstraint(
        "(kind = 'TIMELINE' AND source_layer = 'TERRITORIAL_TEST_TIMELINE') OR "
        "(kind = 'OVERLAP' AND source_layer = 'TERRITORIAL_TEST_OVERLAP')",
        name="ck_territorial_capture_kind_layer",
    ),
    Index(
        "ix_territorial_captures_property_temporal",
        "record_owner_organization_id",
        "property_id",
        "source_profile_code",
        "source_layer",
        "operation",
        "known_at",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
)


def _json_compatible(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return {key: _json_compatible(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_compatible(item) for item in value]
    return value


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


@dataclass(frozen=True, slots=True)
class TransactionalTerritorialSourceCaptureRepository(TerritorialSourceCaptureRepositoryPort):
    connection: Connection

    def save(self, capture: TerritorialSourceCapture) -> None:
        self.connection.execute(
            insert(territorial_source_captures_table).values(
                capture_id=capture.capture_id.value,
                record_owner_organization_id=capture.organization_id.value,
                property_id=capture.property_id.value,
                geometry_id=capture.geometry_id.value,
                geometry_version=capture.geometry_version,
                source_profile_code=capture.source_profile_code,
                source_environment=capture.source_environment.value,
                source_name=capture.source_name,
                source_layer=capture.source_layer,
                kind=capture.kind.value,
                operation=capture.operation,
                request_scope_digest=capture.request_scope_digest,
                response_schema=capture.response_schema,
                response_schema_version=capture.response_schema_version,
                canonicalization_version=capture.canonicalization_version,
                response_digest=capture.response_digest,
                response_summary=_json_compatible(capture.response_summary),
                source_version_ids=list(capture.source_version_ids),
                source_valid_from=capture.source_valid_from,
                source_valid_to=capture.source_valid_to,
                captured_at=capture.captured_at,
                known_at=capture.known_at,
                recorded_at=capture.recorded_at,
                limitations=list(capture.limitations),
            )
        )

    def list_by_property(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> list[TerritorialSourceCapture]:
        rows = self.connection.execute(
            select(territorial_source_captures_table)
            .where(
                territorial_source_captures_table.c.record_owner_organization_id
                == organization_id.value,
                territorial_source_captures_table.c.property_id == property_id.value,
            )
            .order_by(
                territorial_source_captures_table.c.known_at,
                territorial_source_captures_table.c.captured_at,
                territorial_source_captures_table.c.capture_id,
            )
        ).all()
        return [self._map(row) for row in rows]

    @staticmethod
    def _map(row: Row[Any]) -> TerritorialSourceCapture:
        return TerritorialSourceCapture(
            capture_id=TypedId("territorial_source_capture", row.capture_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            property_id=TypedId("rural_property", row.property_id),
            geometry_id=TypedId("property_geometry", row.geometry_id),
            geometry_version=row.geometry_version,
            source_profile_code=row.source_profile_code,
            source_environment=TerritorialCaptureEnvironment(row.source_environment),
            source_name=row.source_name,
            source_layer=row.source_layer,
            kind=TerritorialCaptureKind(row.kind),
            operation=row.operation,
            request_scope_digest=row.request_scope_digest,
            response_schema=row.response_schema,
            response_schema_version=row.response_schema_version,
            canonicalization_version=row.canonicalization_version,
            response_digest=row.response_digest,
            response_summary=MappingProxyType(dict(row.response_summary)),
            source_version_ids=tuple(row.source_version_ids),
            captured_at=_aware(row.captured_at),  # type: ignore[arg-type]
            known_at=_aware(row.known_at),  # type: ignore[arg-type]
            source_valid_from=_aware(row.source_valid_from),
            source_valid_to=_aware(row.source_valid_to),
            recorded_at=_aware(row.recorded_at),  # type: ignore[arg-type]
            limitations=tuple(row.limitations),
        )


__all__ = [
    "TransactionalTerritorialSourceCaptureRepository",
    "territorial_source_captures_table",
    "TERRITORIAL_RESPONSE_SCHEMA",
    "TERRITORIAL_RESPONSE_SCHEMA_VERSION",
    "TERRITORIAL_CANONICALIZATION_VERSION",
    "TERRITORIAL_TEST_OVERLAP_LAYER",
    "TERRITORIAL_TEST_SOURCE",
    "TERRITORIAL_TEST_TIMELINE_LAYER",
]
