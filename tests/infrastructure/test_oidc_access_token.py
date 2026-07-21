from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from packages.core_infrastructure.authentication import (
    AccessTokenValidationError,
    AccessTokenValidator,
    OidcJwtSettings,
)

ISSUER = "https://issuer.example/realms/titan"
AUDIENCE = "titan-api"


@pytest.fixture
def keys() -> tuple[RSAPrivateKey, RSAPublicKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _token(private_key: RSAPrivateKey, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "iss": ISSUER,
        "sub": "external-subject",
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "azp": "titan-swagger",
        "scope": "openid profile",
        "token_use": "access",
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"typ": "JWT"})


def _validator(public_key: RSAPublicKey) -> AccessTokenValidator:
    settings = OidcJwtSettings(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://issuer.example/jwks",
        leeway_seconds=0,
    )
    return AccessTokenValidator(settings, key_resolver=lambda _token: public_key)


def test_valid_access_token_produces_normalized_principal(
    keys: tuple[RSAPrivateKey, RSAPublicKey],
) -> None:
    private_key, public_key = keys
    principal = _validator(public_key).validate(_token(private_key))
    assert principal.issuer == ISSUER
    assert principal.subject == "external-subject"
    assert principal.technical_scopes == {"openid", "profile"}


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://unknown.example"},
        {"aud": "titan-swagger"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"sub": ""},
    ],
)
def test_invalid_issuer_audience_expiration_or_subject_is_rejected(
    keys: tuple[RSAPrivateKey, RSAPublicKey], claims: dict[str, object]
) -> None:
    private_key, public_key = keys
    with pytest.raises(AccessTokenValidationError):
        _validator(public_key).validate(_token(private_key, **claims))


def test_id_token_for_swagger_is_not_accepted_as_api_token(
    keys: tuple[RSAPrivateKey, RSAPublicKey],
) -> None:
    private_key, public_key = keys
    id_token = _token(private_key, aud=AUDIENCE, token_use="id")
    with pytest.raises(AccessTokenValidationError):
        _validator(public_key).validate(id_token)


def test_tampered_signature_is_rejected(
    keys: tuple[RSAPrivateKey, RSAPublicKey],
) -> None:
    private_key, public_key = keys
    token = _token(private_key)
    encoded_header, encoded_payload, encoded_signature = token.split(".")
    replacement = "A" if encoded_signature[-1] != "A" else "B"
    tampered = f"{encoded_header}.{encoded_payload}.{encoded_signature[:-1]}{replacement}"
    with pytest.raises(AccessTokenValidationError):
        _validator(public_key).validate(tampered)
