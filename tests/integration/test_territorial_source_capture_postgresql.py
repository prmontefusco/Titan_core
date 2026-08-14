"""Persistencia append-only de capturas territoriais sinteticas (T-05D Corte 2)."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from packages.core_infrastructure.persistence import set_local_organization_context
from packages.livestock_application.temporal_territorial_capture import (
    TemporalTerritorialCaptureReader,
)
from packages.livestock_domain.geometry import (
    CAMADA_PERIMETRO,
    SRID_CANONICO,
    GeometrySource,
    PropertyGeometry,
    digest_de,
)
from packages.livestock_domain.territorial_capture import (
    TERRITORIAL_CANONICALIZATION_VERSION,
    TERRITORIAL_RESPONSE_SCHEMA,
    TERRITORIAL_RESPONSE_SCHEMA_VERSION,
    TERRITORIAL_TEST_TIMELINE_LAYER,
    TerritorialCaptureKind,
    TerritorialSourceCapture,
    territorial_response_digest,
)
from packages.livestock_infrastructure.persistence.geometry_repository import (
    TransactionalPropertyGeometryRepository,
)
from packages.livestock_infrastructure.persistence.territorial_capture_repository import (
    TransactionalTerritorialSourceCaptureRepository,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_api_support import Ambiente

_QUADRADO = json.dumps(
    {
        "type": "Polygon",
        "coordinates": [
            [[-47.9, -15.8], [-47.8, -15.8], [-47.8, -15.7], [-47.9, -15.7], [-47.9, -15.8]]
        ],
    }
)


def _digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def _property_for_organization(connection: Connection, organization_id: OrganizationId) -> TypedId:
    property_id = TypedId.new("rural_property")
    set_local_organization_context(connection, organization_id)
    connection.execute(
        text(
            "INSERT INTO core_audit.rural_properties ("
            "property_id, record_owner_organization_id, code, name, municipality, "
            "state_code, status, version, created_at) VALUES ("
            ":property_id, :organization_id, :code, 'Fazenda Territorial', "
            "'Brasilia', 'DF', 'ACTIVE', 1, NOW())"
        ),
        {
            "property_id": property_id.value,
            "organization_id": organization_id.value,
            "code": f"TERR-{uuid4().hex[:12]}",
        },
    )
    return property_id


def _geometry(
    connection: Connection, organization_id: OrganizationId, property_id: TypedId
) -> PropertyGeometry:
    set_local_organization_context(connection, organization_id)
    geometry = PropertyGeometry(
        geometry_id=TypedId.new("property_geometry"),
        organization_id=organization_id,
        property_id=property_id,
        source=GeometrySource.DECLARADA,
        layer=CAMADA_PERIMETRO,
        srid=SRID_CANONICO,
        source_payload=_QUADRADO,
        source_digest=digest_de(_QUADRADO),
        version=1,
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        imported_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    TransactionalPropertyGeometryRepository(connection).save(geometry)
    return geometry


def _capture(
    organization_id: OrganizationId,
    property_id: TypedId,
    geometry: PropertyGeometry,
    *,
    source_layer: str = TERRITORIAL_TEST_TIMELINE_LAYER,
    kind: TerritorialCaptureKind = TerritorialCaptureKind.TIMELINE,
    operation: str = "timeline",
    known_at: datetime = datetime(2026, 1, 2, tzinfo=UTC),
    response_summary: dict[str, object] | None = None,
) -> TerritorialSourceCapture:
    return TerritorialSourceCapture.create_synthetic(
        organization_id=organization_id,
        property_id=property_id,
        geometry_id=geometry.geometry_id,
        geometry_version=geometry.version,
        source_layer=source_layer,
        kind=kind,
        operation=operation,
        request_scope_digest=_digest(f"{property_id.value}:{source_layer}:{operation}"),
        response_summary=response_summary or {"has_occurrence": True, "years": [2020]},
        source_version_ids=("synthetic-territorial-v1",),
        captured_at=datetime(2026, 1, 2, tzinfo=UTC),
        known_at=known_at,
        source_valid_from=datetime(2026, 1, 1, tzinfo=UTC),
        source_valid_to=datetime(2027, 1, 1, tzinfo=UTC),
        recorded_at=known_at,
        limitations=("SYNTHETIC_TEST_SOURCE",),
    )


def _restricted_role(connection: Connection) -> str:
    role = f"titan_territorial_probe_{uuid4().hex[:12]}"
    quoted = connection.engine.dialect.identifier_preparer.quote(role)
    connection.execute(
        text(
            f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted}"))
    connection.execute(
        text(
            "GRANT SELECT, INSERT, UPDATE, DELETE "
            f"ON core_audit.territorial_source_captures TO {quoted}"
        )
    )
    return quoted


def test_territorial_capture_roundtrip_preserves_canonical_contract(
    ambiente: Ambiente,
) -> None:
    connection = ambiente.connection
    organization_id = ambiente.org_a.organization_id
    property_id = _property_for_organization(connection, organization_id)
    geometry = _geometry(connection, organization_id, property_id)
    capture = _capture(
        organization_id,
        property_id,
        geometry,
        response_summary={"has_occurrence": True, "years": [2020, 2021]},
    )
    repository = TransactionalTerritorialSourceCaptureRepository(connection)
    set_local_organization_context(connection, organization_id)

    repository.save(capture)
    found = repository.list_by_property(organization_id, property_id)
    selection = TemporalTerritorialCaptureReader(repository).select(
        organization_id,
        property_id,
        reference_time=datetime(2026, 1, 3, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 3, tzinfo=UTC),
    )

    assert len(found) == 1
    assert found[0].capture_id == capture.capture_id
    assert dict(found[0].response_summary) == {"has_occurrence": True, "years": (2020, 2021)}
    assert found[0].response_schema == TERRITORIAL_RESPONSE_SCHEMA
    assert found[0].response_schema_version == TERRITORIAL_RESPONSE_SCHEMA_VERSION
    assert found[0].canonicalization_version == TERRITORIAL_CANONICALIZATION_VERSION
    assert found[0].response_digest == territorial_response_digest(found[0].response_summary)
    assert found[0].source_version_ids == ("synthetic-territorial-v1",)
    assert found[0].limitations == ("SYNTHETIC_TEST_SOURCE",)
    assert selection.limitation is None
    assert [item.capture_id for item in selection.captures] == [capture.capture_id]


def test_territorial_capture_rls_is_select_insert_only_for_tenant_role(
    ambiente: Ambiente,
) -> None:
    connection = ambiente.connection
    organization_id = ambiente.org_a.organization_id
    property_id = _property_for_organization(connection, organization_id)
    geometry = _geometry(connection, organization_id, property_id)
    capture = _capture(organization_id, property_id, geometry)
    set_local_organization_context(connection, organization_id)
    TransactionalTerritorialSourceCaptureRepository(connection).save(capture)
    quoted_role = _restricted_role(connection)
    insert_id = uuid4()
    try:
        connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
        connection.execute(
            text("SELECT set_config('titan.organization_id', :organization_id, true)"),
            {"organization_id": str(organization_id.value)},
        )
        visible = connection.execute(
            text(
                "SELECT capture_id FROM core_audit.territorial_source_captures "
                "WHERE capture_id = :capture_id"
            ),
            {"capture_id": capture.capture_id.value},
        ).scalar_one()
        assert visible == capture.capture_id.value

        connection.execute(
            text(
                "INSERT INTO core_audit.territorial_source_captures ("
                "capture_id, record_owner_organization_id, property_id, geometry_id, "
                "geometry_version, source_profile_code, source_environment, source_name, "
                "source_layer, kind, operation, request_scope_digest, response_schema, "
                "response_schema_version, canonicalization_version, response_digest, "
                "response_summary, source_version_ids, source_valid_from, source_valid_to, "
                "captured_at, known_at, recorded_at, limitations) VALUES ("
                ":capture_id, :organization_id, :property_id, :geometry_id, "
                "1, 'TERRITORIAL_TEST_SOURCE', 'SYNTHETIC', 'TERRITORIAL_TEST_SOURCE', "
                "'TERRITORIAL_TEST_OVERLAP', 'OVERLAP', 'intersects', :request_digest, "
                ":response_schema, :response_schema_version, :canonicalization_version, "
                ":response_digest, CAST(:response_summary AS jsonb), "
                "CAST(:source_version_ids AS jsonb), :valid_from, :valid_to, "
                ":captured_at, :known_at, :recorded_at, CAST(:limitations AS jsonb))"
            ),
            {
                "capture_id": insert_id,
                "organization_id": organization_id.value,
                "property_id": property_id.value,
                "geometry_id": geometry.geometry_id.value,
                "request_digest": "a" * 64,
                "response_schema": TERRITORIAL_RESPONSE_SCHEMA,
                "response_schema_version": TERRITORIAL_RESPONSE_SCHEMA_VERSION,
                "canonicalization_version": TERRITORIAL_CANONICALIZATION_VERSION,
                "response_digest": territorial_response_digest(
                    {"has_overlap": False, "feature_count": 0}
                ),
                "response_summary": json.dumps({"has_overlap": False, "feature_count": 0}),
                "source_version_ids": json.dumps(["rls-test-v1"]),
                "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
                "valid_to": datetime(2027, 1, 1, tzinfo=UTC),
                "captured_at": datetime(2026, 1, 2, tzinfo=UTC),
                "known_at": datetime(2026, 1, 2, tzinfo=UTC),
                "recorded_at": datetime(2026, 1, 2, tzinfo=UTC),
                "limitations": json.dumps([]),
            },
        )

        updated = connection.execute(
            text(
                "UPDATE core_audit.territorial_source_captures "
                "SET operation = 'alterado' WHERE capture_id = :capture_id"
            ),
            {"capture_id": capture.capture_id.value},
        )
        deleted = connection.execute(
            text(
                "DELETE FROM core_audit.territorial_source_captures WHERE capture_id = :capture_id"
            ),
            {"capture_id": insert_id},
        )
        assert updated.rowcount == 0
        assert deleted.rowcount == 0
    finally:
        connection.execute(text("RESET ROLE"))
        connection.execute(text(f"DROP OWNED BY {quoted_role}"))
        connection.execute(text(f"DROP ROLE {quoted_role}"))


def test_territorial_capture_rejects_property_or_geometry_from_other_organization(
    ambiente: Ambiente,
) -> None:
    connection = ambiente.connection
    org_a = ambiente.org_a.organization_id
    org_b = ambiente.org_b.organization_id
    property_a = _property_for_organization(connection, org_a)
    geometry_a = _geometry(connection, org_a, property_a)
    property_b = _property_for_organization(connection, org_b)
    capture = _capture(org_a, property_b, geometry_a)

    set_local_organization_context(connection, org_a)
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            TransactionalTerritorialSourceCaptureRepository(connection).save(capture)

    geometry_b = _geometry(connection, org_b, property_b)
    capture = _capture(org_a, property_a, geometry_b)
    set_local_organization_context(connection, org_a)
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            TransactionalTerritorialSourceCaptureRepository(connection).save(capture)
