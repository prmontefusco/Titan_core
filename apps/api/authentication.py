"""Autenticação OIDC da API (Passo 10.4a).

Vive em módulo próprio para que tanto o `main` quanto a raiz de composição da
vertical dependam **da mesma dependência declarada**, sem ciclo de importação.

A tentativa anterior usava um marcador substituído por `dependency_overrides`, e
isso tinha um custo invisível: override não entra no OpenAPI. O endpoint não
declarava segurança, o Swagger não anexava o token do botão "Authorize", e a
requisição autenticada chegava sem credencial. Fiação de produção não se faz por
override — override é ferramenta de teste.
"""

import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer

from apps.api.problem import DomainProblem
from packages.core_domain import AuthenticatedPrincipal
from packages.core_infrastructure.authentication import (
    AccessTokenValidationError,
    AccessTokenValidator,
    OidcJwtSettings,
)

_local_issuer = os.environ.get("TITAN_OIDC_ISSUER", "http://localhost:8080/realms/titan").rstrip(
    "/"
)

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=os.environ.get(
        "TITAN_OIDC_AUTHORIZATION_URL",
        f"{_local_issuer}/protocol/openid-connect/auth",
    ),
    tokenUrl=os.environ.get(
        "TITAN_OIDC_TOKEN_URL",
        f"{_local_issuer}/protocol/openid-connect/token",
    ),
    scopes={"openid": "Identificar o principal autenticado"},
)


@lru_cache(maxsize=1)
def get_access_token_validator() -> AccessTokenValidator:
    return AccessTokenValidator(OidcJwtSettings.from_environment())


def require_authenticated_principal(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> AuthenticatedPrincipal:
    try:
        validator = get_access_token_validator()
    except RuntimeError as error:
        # Servidor sem configuração de OIDC não é credencial ruim do cliente.
        # Responder 401 aqui mandaria o integrador conferir o token dele durante
        # horas, enquanto o defeito está do nosso lado — foi o que aconteceu na
        # validação manual do Passo 10.4a.
        raise DomainProblem(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            reason_code="AUTENTICACAO_NAO_CONFIGURADA",
            title="Autenticação não configurada",
            detail="O serviço de autenticação não está configurado neste ambiente.",
        ) from error

    try:
        return validator.validate(token)
    except AccessTokenValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access Token ausente ou inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


AuthenticatedPrincipalDependency = Annotated[
    AuthenticatedPrincipal, Depends(require_authenticated_principal)
]
