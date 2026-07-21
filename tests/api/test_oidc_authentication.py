from datetime import UTC, datetime

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from apps.api import main
from packages.core_domain import AuthenticatedPrincipal, PrincipalType

client = TestClient(main.app)


class _Validator:
    def validate(self, token: str) -> AuthenticatedPrincipal:
        assert token == "valid-access-token"
        return AuthenticatedPrincipal(
            issuer="https://issuer.example",
            subject="subject-1",
            principal_type=PrincipalType.USER,
            authenticated_at=datetime(2026, 7, 21, tzinfo=UTC),
            client_id="titan-swagger",
            technical_scopes=frozenset({"openid"}),
        )


def test_protected_route_rejects_missing_token() -> None:
    response = client.get("/technical/authentication")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_protected_route_returns_normalized_principal(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "get_access_token_validator", lambda: _Validator())
    response = client.get(
        "/technical/authentication",
        headers={"Authorization": "Bearer valid-access-token"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "issuer": "https://issuer.example",
        "subject": "subject-1",
        "scopes": ["openid"],
    }


def test_openapi_uses_authorization_code_flow() -> None:
    scheme = client.get("/openapi.json").json()["components"]["securitySchemes"]
    flow = scheme["OAuth2AuthorizationCodeBearer"]["flows"]["authorizationCode"]
    assert flow["authorizationUrl"].endswith("/protocol/openid-connect/auth")
    assert flow["tokenUrl"].endswith("/protocol/openid-connect/token")
