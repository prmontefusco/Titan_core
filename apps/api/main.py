import os
from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2AuthorizationCodeBearer
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.verification import public_contract_schemas
from apps.api.verification import router as verification_router
from packages.core_domain import AuthenticatedPrincipal
from packages.core_infrastructure.authentication import (
    AccessTokenValidationError,
    AccessTokenValidator,
    OidcJwtSettings,
)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class AuthenticationResponse(BaseModel):
    issuer: str
    subject: str
    scopes: list[str]


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

app = FastAPI(
    title="Titan API",
    version="0.0.0",
    swagger_ui_init_oauth={
        "clientId": os.environ.get("TITAN_OIDC_SWAGGER_CLIENT_ID", "titan-swagger"),
        "usePkceWithAuthorizationCodeGrant": True,
    },
)


# Verificação externa é deliberadamente anônima: verifica apenas o material que o
# próprio chamador enviou e não consulta registro algum do Titan.
app.include_router(verification_router)


def _openapi_com_contrato_publico() -> dict[str, Any]:
    """Publica no OpenAPI os schemas que o FastAPI não consegue inferir.

    O endpoint de verificação lê o corpo cru para controlar os códigos de erro,
    e sem esta injeção o `$ref` do seu `requestBody` ficaria pendurado — o
    contrato existiria na ADR e não na documentação que o integrador consulta.
    """
    if app.openapi_schema is not None:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("schemas", {}).update(public_contract_schemas())
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_com_contrato_publico  # type: ignore[method-assign]


@lru_cache(maxsize=1)
def get_access_token_validator() -> AccessTokenValidator:
    return AccessTokenValidator(OidcJwtSettings.from_environment())


def require_authenticated_principal(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> AuthenticatedPrincipal:
    try:
        return get_access_token_validator().validate(token)
    except (AccessTokenValidationError, RuntimeError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access Token ausente ou inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


AuthenticatedPrincipalDependency = Annotated[
    AuthenticatedPrincipal, Depends(require_authenticated_principal)
]


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exception: StarletteHTTPException
) -> JSONResponse:
    if exception.status_code == 404:
        return JSONResponse(
            content={
                "type": "urn:titan:problema:rota-nao-encontrada",
                "title": "Rota não encontrada",
                "status": 404,
                "detail": "O recurso solicitado não existe.",
                "instance": request.url.path,
                "reason_code": "ROTA_NAO_ENCONTRADA",
            },
            media_type="application/problem+json",
            status_code=404,
        )

    return JSONResponse(
        content={
            "type": "urn:titan:problema:erro-http",
            "title": "Erro HTTP",
            "status": exception.status_code,
            "detail": "A requisição não pôde ser processada.",
            "instance": request.url.path,
            "reason_code": "ERRO_HTTP",
        },
        media_type="application/problem+json",
        status_code=exception.status_code,
        headers=exception.headers,
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Verificar a saúde do processo",
    tags=["técnico"],
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get(
    "/technical/authentication",
    response_model=AuthenticationResponse,
    summary="Validar autenticação técnica",
    tags=["técnico"],
    # A negação faz parte do contrato: rota protegida cujo 401 não é declarado
    # deixa o consumidor descobrir o comportamento por tentativa e erro.
    responses={401: {"description": "Token ausente, inválido, expirado ou de outro recurso"}},
)
async def technical_authentication(
    principal: AuthenticatedPrincipalDependency,
) -> AuthenticationResponse:
    return AuthenticationResponse(
        issuer=principal.issuer,
        subject=principal.subject,
        scopes=sorted(principal.technical_scopes),
    )
