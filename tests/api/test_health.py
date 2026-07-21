from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_health_reports_process_as_healthy() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok"}


def test_unknown_route_uses_problem_details() -> None:
    response = client.get("/route-that-does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "urn:titan:problema:rota-nao-encontrada",
        "title": "Rota não encontrada",
        "status": 404,
        "detail": "O recurso solicitado não existe.",
        "instance": "/route-that-does-not-exist",
        "reason_code": "ROTA_NAO_ENCONTRADA",
    }


def test_openapi_marks_health_as_technical_endpoint() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    health_operation = response.json()["paths"]["/health"]["get"]
    assert health_operation["tags"] == ["técnico"]
