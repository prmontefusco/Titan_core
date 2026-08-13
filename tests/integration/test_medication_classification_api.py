from datetime import UTC, datetime

import pytest

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from tests.livestock_api_support import DATABASE_URL, Ambiente, ClienteAutenticado, _cliente

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada.")


def headers(ambiente: Ambiente) -> dict[str, str]:
    return {ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)}


def medication(ambiente: Ambiente, client: ClienteAutenticado) -> str:
    response = client.post(
        "/v1/livestock/medications",
        json={
            "trade_name": "Produto fictício antimicrobiano",
            "active_ingredient": "Ingrediente fictício",
            "manufacturer": "Laboratório fictício",
            "withdrawal_period_days": 10,
        },
        headers=headers(ambiente),
    )
    assert response.status_code == 201, response.text
    return str(response.json()["medication_id"])


def test_records_unknown_distinct_from_absence_and_lists(ambiente: Ambiente) -> None:
    client = _cliente(ambiente, ambiente.operador)
    medication_id = medication(ambiente, client)
    before = client.get(
        f"/v1/livestock/medications/{medication_id}/sanitary-classifications",
        headers=headers(ambiente),
    )
    assert before.status_code == 200 and before.json() == []
    now = datetime.now(UTC).isoformat()
    created = client.post(
        f"/v1/livestock/medications/{medication_id}/sanitary-classifications",
        json={"status": "UNKNOWN", "observed_at": now, "known_at": now},
        headers=headers(ambiente),
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "UNKNOWN"
    assert created.json()["confidence_tier"] == "DOCUMENTED"
    assert created.json()["validation_status"] == "STRUCTURALLY_VALIDATED"
    assert created.json()["known_at"] is not None
    listed = client.get(
        f"/v1/livestock/medications/{medication_id}/sanitary-classifications",
        headers=headers(ambiente),
    )
    assert listed.status_code == 200 and len(listed.json()) == 1


def test_auditor_cannot_record_classification(ambiente: Ambiente) -> None:
    operator = _cliente(ambiente, ambiente.operador)
    auditor = _cliente(ambiente, ambiente.auditor)
    medication_id = medication(ambiente, operator)
    now = datetime.now(UTC).isoformat()
    response = auditor.post(
        f"/v1/livestock/medications/{medication_id}/sanitary-classifications",
        json={"status": "APPLIES", "observed_at": now, "known_at": now},
        headers=headers(ambiente),
    )
    assert response.status_code == 403


def test_classification_requires_explicit_knowledge_time(ambiente: Ambiente) -> None:
    client = _cliente(ambiente, ambiente.operador)
    medication_id = medication(ambiente, client)

    response = client.post(
        f"/v1/livestock/medications/{medication_id}/sanitary-classifications",
        json={"status": "UNKNOWN", "observed_at": datetime.now(UTC).isoformat()},
        headers=headers(ambiente),
    )

    assert response.status_code == 422
