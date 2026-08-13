from datetime import UTC, datetime, timedelta

import pytest

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
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


def _payload() -> dict[str, object]:
    end = datetime.now(UTC)
    return {
        "dimension": "treatment_history",
        "covered_from": (end - timedelta(days=45)).isoformat(),
        "covered_until": end.isoformat(),
        "validation": "NOT_VALIDATED",
        "admissibility": "INSUFFICIENT",
        "accessible": True,
        "conflicting": False,
        "known_at": end.isoformat(),
    }


def test_importa_e_lista_contribuicao_source_neutral(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _animal(ambiente, operador)
    created = operador.post(
        f"/v1/livestock/animals/{animal_id}/coverage-contributions",
        json=_payload(),
        headers=_headers(ambiente),
    )
    assert created.status_code == 201, created.text
    assert created.json()["source_id"] is None
    listed = operador.get(
        f"/v1/livestock/animals/{animal_id}/coverage-contributions", headers=_headers(ambiente)
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["dimension"] == "treatment_history"


def test_intervalo_invalido_retorna_conflito(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _animal(ambiente, operador)
    payload = _payload()
    payload["covered_from"], payload["covered_until"] = (
        payload["covered_until"],
        payload["covered_from"],
    )
    response = operador.post(
        f"/v1/livestock/animals/{animal_id}/coverage-contributions",
        json=payload,
        headers=_headers(ambiente),
    )
    assert response.status_code == 409


def test_auditor_nao_importa_contribuicao(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    animal_id = _animal(ambiente, operador)
    response = auditor.post(
        f"/v1/livestock/animals/{animal_id}/coverage-contributions",
        json=_payload(),
        headers=_headers(ambiente),
    )
    assert response.status_code == 403


def test_animal_inexistente_retorna_404(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    response = operador.post(
        "/v1/livestock/animals/00000000-0000-0000-0000-000000000001/coverage-contributions",
        json=_payload(),
        headers=_headers(ambiente),
    )
    assert response.status_code == 404


def test_fonte_inexistente_nao_sustenta_coverage_admissivel(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _animal(ambiente, operador)
    payload = _payload() | {
        "validation": "VALIDATED",
        "admissibility": "ADMISSIBLE",
        "source_entity_type": "received_transfer_artifact",
        "source_id": "00000000-0000-0000-0000-000000000001",
    }
    response = operador.post(
        f"/v1/livestock/animals/{animal_id}/coverage-contributions",
        json=payload,
        headers=_headers(ambiente),
    )
    assert response.status_code == 409
