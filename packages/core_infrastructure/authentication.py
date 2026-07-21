"""Validação estrita de Access Token JWT emitido por OIDC Provider confiável."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import jwt
from jwt import PyJWKClient

from packages.core_domain import AuthenticatedPrincipal, PrincipalType


class AccessTokenValidationError(ValueError):
    """Falha segura de autenticação sem conteúdo sensível."""


@dataclass(frozen=True, slots=True)
class OidcJwtSettings:
    issuer: str
    audience: str
    jwks_url: str
    algorithms: tuple[str, ...] = ("RS256",)
    leeway_seconds: int = 30

    @classmethod
    def from_environment(cls) -> "OidcJwtSettings":
        issuer = os.environ.get("TITAN_OIDC_ISSUER", "").rstrip("/")
        audience = os.environ.get("TITAN_OIDC_AUDIENCE", "")
        if not issuer or not audience:
            raise RuntimeError("TITAN_OIDC_ISSUER e TITAN_OIDC_AUDIENCE são obrigatórios.")
        jwks_url = os.environ.get("TITAN_OIDC_JWKS_URL", f"{issuer}/protocol/openid-connect/certs")
        return cls(issuer=issuer, audience=audience, jwks_url=jwks_url)


class JwksSigningKeyResolver:
    def __init__(self, jwks_url: str) -> None:
        self._client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300)

    def __call__(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token).key


class AccessTokenValidator:
    def __init__(
        self,
        settings: OidcJwtSettings,
        key_resolver: Callable[[str], Any] | None = None,
    ) -> None:
        self._settings = settings
        self._key_resolver = key_resolver or JwksSigningKeyResolver(settings.jwks_url)

    def validate(self, token: str) -> AuthenticatedPrincipal:
        if not isinstance(token, str) or not token:
            raise AccessTokenValidationError("TOKEN_AUSENTE")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in self._settings.algorithms:
                raise AccessTokenValidationError("ALGORITMO_NAO_PERMITIDO")
            if header.get("typ") not in {"JWT", "at+jwt"}:
                raise AccessTokenValidationError("TIPO_DE_TOKEN_INVALIDO")
            claims = jwt.decode(
                token,
                self._key_resolver(token),
                algorithms=list(self._settings.algorithms),
                audience=self._settings.audience,
                issuer=self._settings.issuer,
                leeway=self._settings.leeway_seconds,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except AccessTokenValidationError:
            raise
        except jwt.PyJWTError as error:
            raise AccessTokenValidationError("ACCESS_TOKEN_INVALIDO") from error
        except Exception as error:
            raise AccessTokenValidationError("CHAVE_NAO_DISPONIVEL") from error

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AccessTokenValidationError("SUBJECT_INVALIDO")
        if claims.get("token_use") != "access":
            raise AccessTokenValidationError("FINALIDADE_DE_TOKEN_INVALIDA")
        authentication_time = claims.get("auth_time")
        authenticated_at = (
            datetime.fromtimestamp(authentication_time, tz=UTC)
            if isinstance(authentication_time, int)
            else None
        )
        client_id = claims.get("azp") or claims.get("client_id")
        scope = claims.get("scope", "")
        scopes = frozenset(scope.split()) if isinstance(scope, str) else frozenset()
        return AuthenticatedPrincipal(
            issuer=self._settings.issuer,
            subject=subject,
            principal_type=PrincipalType.USER,
            authenticated_at=authenticated_at,
            client_id=client_id if isinstance(client_id, str) else None,
            technical_scopes=scopes,
        )
