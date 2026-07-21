from dataclasses import fields
from datetime import UTC, datetime

from packages.core_domain import AuthenticatedPrincipal, PrincipalType


def test_authenticated_principal_contains_no_token_or_credential() -> None:
    principal = AuthenticatedPrincipal(
        issuer="https://issuer.example",
        subject="subject-1",
        principal_type=PrincipalType.USER,
        authenticated_at=datetime(2026, 7, 21, tzinfo=UTC),
        client_id="client",
        technical_scopes=frozenset({"openid"}),
    )
    names = {field.name for field in fields(principal)}
    assert principal.subject == "subject-1"
    assert not names.intersection({"token", "access_token", "id_token", "refresh_token"})
