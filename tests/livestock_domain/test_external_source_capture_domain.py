from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from packages.livestock_domain.external_source_capture import ExternalSourceCaptureArtifact
from packages.shared_kernel import OrganizationId, TypedId

NOW = datetime(2026, 8, 13, tzinfo=UTC)


def _artifact(projection: dict[str, object]) -> ExternalSourceCaptureArtifact:
    return ExternalSourceCaptureArtifact.create(
        organization_id=OrganizationId.new(),
        contract_version="SISBOV_SIMULATOR_CAPTURE/v1",
        resource_kind="MOVEMENT",
        request_scope_digest="a" * 64,
        transport_outcome="CAPTURED",
        response_status_code=200,
        response_digest="b" * 64,
        captured_at=NOW,
        parser_name="SisbovSimulatorParser",
        parser_version="1",
        parsing_diagnostic_code=None,
        recorded_by=TypedId.new("actor"),
        review_projection=projection,
    )


def test_projection_is_deeply_immutable_and_has_canonical_digest() -> None:
    input_projection: dict[str, object] = {
        "resource_kind": "MOVEMENT",
        "external_reference": "MOV-1",
        "declared_fields": {
            "statusMovimentacao": "ATIVA",
            "gtas": ["GTA-1"],
            "animais": ["BR-1"],
        },
    }

    artifact = _artifact(input_projection)
    input_projection["declared_fields"]["gtas"].append("GTA-2")  # type: ignore[index]

    assert artifact.review_projection is not None
    assert artifact.review_projection["declared_fields"]["gtas"] == ("GTA-1",)
    assert artifact.projection_digest is not None
    assert artifact.supports_confirmed_candidate_review()
    with pytest.raises(TypeError):
        artifact.review_projection["declared_fields"]["gtas"] += ("GTA-3",)


def test_projection_rejects_non_allowlisted_field() -> None:
    with pytest.raises(ValueError, match="allowlist"):
        _artifact(
            {
                "resource_kind": "MOVEMENT",
                "external_reference": "MOV-1",
                "declared_fields": {
                    "statusMovimentacao": "ATIVA",
                    "gtas": [],
                    "animais": [],
                    "cpfProdutor": "nao-permitido",
                },
            }
        )


def test_projection_rejects_mismatched_resource_kind() -> None:
    with pytest.raises(ValueError, match="resource_kind"):
        _artifact(
            {
                "resource_kind": "ANIMAL",
                "external_reference": "MOV-1",
                "declared_fields": {
                    "statusAnimal": "ATIVO",
                    "ERASPropriedadeLocalizacao": None,
                },
            }
        )


def test_direct_projection_is_canonicalized() -> None:
    artifact = _artifact(
        {
            "resource_kind": "MOVEMENT",
            "external_reference": "MOV-1",
            "declared_fields": {
                "animais": [],
                "gtas": [],
                "statusMovimentacao": "ATIVA",
            },
        }
    )

    assert isinstance(artifact.review_projection, MappingProxyType)
