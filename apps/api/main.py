import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.authentication import (
    AuthenticatedPrincipalDependency,
)
from apps.api.configuration import exigir_configuracao
from apps.api.core_rule_governance import router as core_rule_governance_router
from apps.api.livestock_animals import router as livestock_animals_router
from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from apps.api.livestock_medications import router as livestock_medications_router
from apps.api.livestock_queries import router as livestock_queries_router
from apps.api.livestock_reads import router as livestock_reads_router
from apps.api.livestock_sanitary_campaigns import router as livestock_sanitary_campaigns_router
from apps.api.livestock_treatments import router as livestock_treatments_router
from apps.api.livestock_writes import router as livestock_writes_router
from apps.api.problem import (
    DomainProblem,
    domain_problem_handler,
    unexpected_error_handler,
    validation_problem_handler,
)
from apps.api.verification import public_contract_schemas
from apps.api.verification import router as verification_router


class HealthResponse(BaseModel):
    status: Literal["ok"]


class AuthenticationResponse(BaseModel):
    issuer: str
    subject: str
    scopes: list[str]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Recusa subir sem configuração, em vez de falhar na primeira requisição."""
    exigir_configuracao()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Titan API",
    version="0.0.0",
    swagger_ui_init_oauth={
        "clientId": os.environ.get("TITAN_OIDC_SWAGGER_CLIENT_ID", "titan-swagger"),
        "usePkceWithAuthorizationCodeGrant": True,
    },
)


# Um frontend em outra origem é bloqueado pelo navegador antes de a requisição
# sair. As origens permitidas vêm do ambiente e **não** têm curinga por padrão:
# `*` com credenciais é recusado pelo próprio navegador, e liberar tudo num
# serviço que carrega prova auditável não é conveniência, é falha.
_origens = [
    origem.strip()
    for origem in os.environ.get("TITAN_CORS_ORIGINS", "").split(",")
    if origem.strip()
]
if _origens:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origens,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", ORGANIZATION_HEADER],
    )


# Verificação externa é deliberadamente anônima: verifica apenas o material que o
# próprio chamador enviou e não consulta registro algum do Titan.
app.include_router(verification_router)
app.include_router(core_rule_governance_router)


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


for livestock_router in (
    livestock_animals_router,
    livestock_medications_router,
    livestock_sanitary_campaigns_router,
    livestock_treatments_router,
    livestock_queries_router,
    livestock_reads_router,
    livestock_writes_router,
):
    app.include_router(livestock_router)

app.add_exception_handler(DomainProblem, domain_problem_handler)
app.add_exception_handler(RequestValidationError, validation_problem_handler)
# Handler de último recurso: o cliente recebe código estável e nada do que
# aconteceu por dentro.
app.add_exception_handler(Exception, unexpected_error_handler)


# Um `reason_code` genérico obriga o cliente a adivinhar o que houve. A
# distinção que mais importa é entre "não sei quem você é" (401) e "sei, e você
# não pode" (403) — colapsá-las esconderia se falta credencial ou permissão.
# O terceiro item, quando presente, substitui a mensagem da exceção. No 401 isso
# é deliberado por dois motivos: o esquema OAuth2 do FastAPI responde antes da
# nossa dependência, com texto em inglês que destoaria do resto da API; e
# distinguir "token ausente" de "token inválido" na resposta não ajuda o
# integrador e informa quem sonda.
_RESPOSTAS_CONHECIDAS: dict[int, tuple[str, str, str | None]] = {
    401: ("Não autenticado", "NAO_AUTENTICADO", "Access Token ausente, inválido ou expirado."),
    403: ("Acesso negado", "ACESSO_NEGADO", None),
    405: ("Método não permitido", "METODO_NAO_PERMITIDO", None),
    409: ("Conflito", "CONFLITO", None),
}


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

    conhecida = _RESPOSTAS_CONHECIDAS.get(exception.status_code)
    titulo, codigo, fixo = conhecida or ("Erro HTTP", "ERRO_HTTP", None)
    # A mensagem da exceção só viaja quando o status é um que nós mesmos
    # emitimos deliberadamente. Para o resto, texto genérico: repassar detalhe de
    # erro desconhecido é por onde vaza informação interna.
    if fixo is not None:
        detalhe = fixo
    elif conhecida is not None and exception.detail:
        detalhe = str(exception.detail)
    else:
        detalhe = "A requisição não pôde ser processada."
    return JSONResponse(
        content={
            "type": f"urn:titan:problema:{codigo.lower().replace('_', '-')}",
            "title": titulo,
            "status": exception.status_code,
            "detail": detalhe,
            "instance": request.url.path,
            "reason_code": codigo,
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
