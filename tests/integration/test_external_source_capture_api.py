"""Integração HTTP do Corte 2B: leitura e revisão de captura simulada."""

from datetime import UTC, datetime

import pytest

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from packages.core_infrastructure.persistence import set_local_organization_context
from packages.livestock_domain.external_source_capture import ExternalSourceCaptureArtifact
from packages.livestock_infrastructure.persistence import (
    TransactionalExternalSourceCaptureArtifactRepository,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_api_support import DATABASE_URL, Ambiente, ClienteAutenticado, _cliente

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada.")


@pytest.fixture
def operador(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.operador)


@pytest.fixture
def auditor(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.auditor)


def _headers(ambiente: Ambiente) -> dict[str, str]:
    return {ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)}


def _animal(ambiente: Ambiente, operador: ClienteAutenticado) -> str:
    response = operador.post(
        "/v1/livestock/animals",
        json={"birth_property_id": str(ambiente.property_id.value), "sex": "FEMALE"},
        headers=_headers(ambiente),
    )
    assert response.status_code == 201
    return str(response.json()["animal_id"])


def _capture(
    ambiente: Ambiente,
    *,
    organization_id: OrganizationId | None = None,
    response_status_code: int = 200,
    transport_outcome: str = "CAPTURED",
    parsing_diagnostic_code: str | None = None,
) -> str:
    """Prepara somente o artefato imutável; a revisão é sempre HTTP no teste."""
    organization_id = organization_id or ambiente.org_a.organization_id
    set_local_organization_context(ambiente.connection, organization_id)
    artifact = ExternalSourceCaptureArtifact.create(
        organization_id=organization_id,
        contract_version="SISBOV_SIMULATOR_CAPTURE/v1",
        resource_kind="ANIMAL",
        request_scope_digest="a" * 64,
        transport_outcome=transport_outcome,
        response_status_code=response_status_code,
        response_digest="b" * 64,
        captured_at=datetime.now(UTC),
        parser_name="SisbovSimulatorParser",
        parser_version="1",
        parsing_diagnostic_code=parsing_diagnostic_code,
        recorded_by=TypedId.new("actor"),
        review_projection=(
            None
            if parsing_diagnostic_code is not None
            else {
                "resource_kind": "ANIMAL",
                "external_reference": "BR123456789012345",
                "declared_fields": {
                    "statusAnimal": "ATIVO",
                    "ERASPropriedadeLocalizacao": None,
                },
            }
        ),
    )
    TransactionalExternalSourceCaptureArtifactRepository(ambiente.connection).save(artifact)
    return str(artifact.artifact_id.value)


def test_lista_projecao_minima_da_captura_simulada(
    ambiente: Ambiente, auditor: ClienteAutenticado
) -> None:
    artifact_id = _capture(ambiente)

    response = auditor.get("/v1/livestock/external-source-captures", headers=_headers(ambiente))

    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["artifact_id"] == artifact_id
    assert item["source_environment"] == "SIMULATED"
    assert item["review_projection"]["external_reference"] == "BR123456789012345"
    assert item["reviews"] == []
    assert "response_digest" not in item
    assert "request_scope_digest" not in item


def test_operador_registra_review_e_auditor_a_recupera(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    animal_id = _animal(ambiente, operador)
    artifact_id = _capture(ambiente)

    registered = operador.post(
        f"/v1/livestock/external-source-captures/{artifact_id}/reviews",
        json={
            "candidate_animal_id": animal_id,
            "status": "CONFIRMED_CANDIDATE",
            "basis_code": "IDENTIFICADOR_SISBOV_CONFERIDO",
        },
        headers=_headers(ambiente),
    )

    assert registered.status_code == 201, registered.text
    assert registered.json()["candidate_animal_id"] == animal_id
    listed = auditor.get("/v1/livestock/external-source-captures", headers=_headers(ambiente))
    assert listed.status_code == 200
    review = listed.json()["items"][0]["reviews"][0]
    assert review["candidate_animal_id"] == animal_id
    assert review["status"] == "CONFIRMED_CANDIDATE"


def test_auditor_nao_registra_review(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    animal_id = _animal(ambiente, operador)
    artifact_id = _capture(ambiente)

    response = auditor.post(
        f"/v1/livestock/external-source-captures/{artifact_id}/reviews",
        json={
            "candidate_animal_id": animal_id,
            "status": "NEEDS_MORE_EVIDENCE",
            "basis_code": "DOCUMENTACAO_INSUFICIENTE",
        },
        headers=_headers(ambiente),
    )

    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_review_para_captura_inexistente_retorna_404(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _animal(ambiente, operador)

    response = operador.post(
        f"/v1/livestock/external-source-captures/{TypedId.new('external_source_capture_artifact').value}/reviews",
        json={
            "candidate_animal_id": animal_id,
            "status": "NEEDS_MORE_EVIDENCE",
            "basis_code": "CAPTURA_NAO_LOCALIZADA",
        },
        headers=_headers(ambiente),
    )

    assert response.status_code == 404


def test_captura_404_nao_pode_confirmar_candidato(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _animal(ambiente, operador)
    artifact_id = _capture(
        ambiente,
        response_status_code=404,
        transport_outcome="NOT_FOUND",
        parsing_diagnostic_code="HTTP_NOT_FOUND",
    )

    response = operador.post(
        f"/v1/livestock/external-source-captures/{artifact_id}/reviews",
        json={
            "candidate_animal_id": animal_id,
            "status": "CONFIRMED_CANDIDATE",
            "basis_code": "IDENTIFICADOR_SISBOV_CONFERIDO",
        },
        headers=_headers(ambiente),
    )

    assert response.status_code == 409
    assert "CONFIRMED_CANDIDATE" in response.json()["detail"]


def test_lista_nao_vaza_captura_de_outra_organization(
    ambiente: Ambiente, auditor: ClienteAutenticado
) -> None:
    artifact_a = _capture(ambiente)
    artifact_b = _capture(ambiente, organization_id=ambiente.org_b.organization_id)

    response = auditor.get("/v1/livestock/external-source-captures", headers=_headers(ambiente))

    assert response.status_code == 200
    returned_ids = {item["artifact_id"] for item in response.json()["items"]}
    assert artifact_a in returned_ids
    assert artifact_b not in returned_ids
