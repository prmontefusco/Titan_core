"""Garantias físicas do Corte 2B para captura externa (ADR-0058)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from packages.core_infrastructure.persistence import set_local_organization_context
from packages.livestock_domain.external_source_capture import ExternalSourceCaptureArtifact
from packages.livestock_infrastructure.persistence import (
    TransactionalExternalSourceCaptureArtifactRepository,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_api_support import Ambiente


def _animal(
    connection: Connection, organization_id: OrganizationId, property_id: TypedId
) -> TypedId:
    animal_id = TypedId.new("animal")
    set_local_organization_context(connection, organization_id)
    connection.execute(
        text(
            "INSERT INTO core_audit.animals ("
            "animal_id, record_owner_organization_id, birth_property_id, sex, created_at) "
            "VALUES (:animal_id, :organization_id, :property_id, 'FEMALE', NOW())"
        ),
        {
            "animal_id": animal_id.value,
            "organization_id": organization_id.value,
            "property_id": property_id.value,
        },
    )
    return animal_id


def _property_for_organization(connection: Connection, organization_id: OrganizationId) -> TypedId:
    property_id = TypedId.new("rural_property")
    set_local_organization_context(connection, organization_id)
    connection.execute(
        text(
            "INSERT INTO core_audit.rural_properties ("
            "property_id, record_owner_organization_id, code, name, municipality, "
            "state_code, created_at) "
            "VALUES (:property_id, :organization_id, :code, 'Fazenda B', 'Uberaba', 'MG', NOW())"
        ),
        {
            "property_id": property_id.value,
            "organization_id": organization_id.value,
            "code": f"B-{uuid4().hex[:12]}",
        },
    )
    return property_id


def _capture(
    connection: Connection, organization_id: OrganizationId
) -> ExternalSourceCaptureArtifact:
    set_local_organization_context(connection, organization_id)
    artifact = ExternalSourceCaptureArtifact.create(
        organization_id=organization_id,
        contract_version="SISBOV_SIMULATOR_CAPTURE/v1",
        resource_kind="ANIMAL",
        request_scope_digest="a" * 64,
        transport_outcome="SUCCEEDED",
        response_status_code=200,
        response_digest="b" * 64,
        captured_at=datetime.now(UTC),
        parser_name="SisbovSimulatorParser",
        parser_version="1",
        parsing_diagnostic_code=None,
        recorded_by=TypedId.new("actor"),
        review_projection={
            "resource_kind": "ANIMAL",
            "external_reference": "BR123",
            "declared_fields": {
                "statusAnimal": "ATIVO",
                "ERASPropriedadeLocalizacao": "123",
            },
        },
    )
    TransactionalExternalSourceCaptureArtifactRepository(connection).save(artifact)
    return artifact


def _restricted_role(connection: Connection) -> str:
    role = f"titan_capture_probe_{uuid4().hex[:12]}"
    quoted = connection.engine.dialect.identifier_preparer.quote(role)
    connection.execute(
        text(
            f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted}"))
    for table in (
        "external_source_capture_artifacts",
        "external_source_capture_association_reviews",
    ):
        connection.execute(
            text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON core_audit.{table} TO {quoted}")
        )
    return quoted


def test_capture_and_review_are_append_only_for_restricted_tenant_role(
    ambiente: Ambiente,
) -> None:
    """Mesmo com grants amplos, RLS só permite SELECT/INSERT no histórico."""
    connection = ambiente.connection
    animal_id = _animal(connection, ambiente.org_a.organization_id, ambiente.property_id)
    artifact = _capture(connection, ambiente.org_a.organization_id)
    quoted_role = _restricted_role(connection)
    review_id = uuid4()
    try:
        connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
        connection.execute(
            text("SELECT set_config('titan.organization_id', :organization_id, true)"),
            {"organization_id": str(ambiente.org_a.organization_id.value)},
        )

        visible = connection.execute(
            text(
                "SELECT artifact_id FROM core_audit.external_source_capture_artifacts "
                "WHERE artifact_id = :artifact_id"
            ),
            {"artifact_id": artifact.artifact_id.value},
        ).scalar_one()
        assert visible == artifact.artifact_id.value

        connection.execute(
            text(
                "INSERT INTO core_audit.external_source_capture_association_reviews ("
                "review_id, record_owner_organization_id, capture_artifact_id, "
                "candidate_animal_id, status, basis_code, reviewed_by, "
                "reviewed_by_entity_type, reviewed_at, limitations) VALUES ("
                ":review_id, :organization_id, :artifact_id, :animal_id, "
                "'NEEDS_MORE_EVIDENCE', 'MATERIAL_INSUFICIENTE', :reviewed_by, "
                "'actor', NOW(), '[]'::jsonb)"
            ),
            {
                "review_id": review_id,
                "organization_id": ambiente.org_a.organization_id.value,
                "artifact_id": artifact.artifact_id.value,
                "animal_id": animal_id.value,
                "reviewed_by": uuid4(),
            },
        )

        updated = connection.execute(
            text(
                "UPDATE core_audit.external_source_capture_artifacts "
                "SET parser_name = 'alterado' WHERE artifact_id = :artifact_id"
            ),
            {"artifact_id": artifact.artifact_id.value},
        )
        deleted = connection.execute(
            text(
                "DELETE FROM core_audit.external_source_capture_association_reviews "
                "WHERE review_id = :review_id"
            ),
            {"review_id": review_id},
        )
        assert updated.rowcount == 0
        assert deleted.rowcount == 0
    finally:
        connection.execute(text("RESET ROLE"))
        connection.execute(text(f"DROP OWNED BY {quoted_role}"))
        connection.execute(text(f"DROP ROLE {quoted_role}"))


def test_review_cannot_reference_an_animal_from_another_organization(ambiente: Ambiente) -> None:
    """A FK composta bloqueia incoerência até sob quem ignora RLS."""
    connection = ambiente.connection
    artifact = _capture(connection, ambiente.org_a.organization_id)
    property_b = _property_for_organization(connection, ambiente.org_b.organization_id)
    animal_b = _animal(connection, ambiente.org_b.organization_id, property_b)

    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO core_audit.external_source_capture_association_reviews ("
                    "review_id, record_owner_organization_id, capture_artifact_id, "
                    "candidate_animal_id, status, basis_code, reviewed_by, "
                    "reviewed_by_entity_type, reviewed_at, limitations) VALUES ("
                    ":review_id, :organization_id, :artifact_id, :animal_id, "
                    "'REJECTED', 'OUTRA_ORGANIZACAO', :reviewed_by, "
                    "'actor', NOW(), '[]'::jsonb)"
                ),
                {
                    "review_id": uuid4(),
                    "organization_id": ambiente.org_a.organization_id.value,
                    "artifact_id": artifact.artifact_id.value,
                    "animal_id": animal_b.value,
                    "reviewed_by": uuid4(),
                },
            )
