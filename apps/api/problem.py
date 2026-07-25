"""Tradução de falhas para `application/problem+json` (Passo 10.4a).

Um cliente precisa distinguir o que ele pode corrigir do que não pode, e por isso
cada resposta de erro carrega um `reason_code` estável — a mensagem humana pode
mudar de redação sem quebrar quem programa contra ela.

A distinção que o Titan mantém explícita:

- **401** — não sei quem você é.
- **403** — sei quem você é, e você não pode fazer isso.

Colapsar as duas esconderia do integrador se falta credencial ou falta permissão.

Erro não previsto vira **500 sanitizado**: o cliente recebe um código estável e
nada do que aconteceu por dentro. Vazar exceção em resposta de API é entregar
mapa da casa a quem bateu na porta.
"""

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

PROBLEM_MEDIA_TYPE = "application/problem+json"

# Respostas de erro que toda rota autenticada da vertical pode produzir. Ficam
# num só lugar porque contrato repetido em cada rota diverge com o tempo — e o
# que o OpenAPI publica é o que o integrador programa contra.
RESPOSTAS_PADRAO: dict[int | str, dict[str, Any]] = {
    401: {"description": "Token ausente, inválido ou expirado"},
    403: {"description": "Sem vínculo com a organização, ou sem a permissão exigida"},
    404: {"description": "Recurso não encontrado nesta organização"},
    409: {"description": "Conflito com o estado atual do domínio"},
    422: {"description": "Entrada inválida"},
}


class DomainProblem(Exception):
    """Falha prevista, com código estável e status deliberado."""

    def __init__(
        self,
        *,
        status_code: int,
        reason_code: str,
        title: str,
        detail: str,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.reason_code = reason_code
        self.title = title
        self.detail = detail


def problem_response(
    *,
    request: Request,
    status_code: int,
    reason_code: str,
    title: str,
    detail: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    corpo: dict[str, Any] = {
        "type": f"urn:titan:problema:{reason_code.lower().replace('_', '-')}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
        "reason_code": reason_code,
    }
    if extra:
        corpo.update(extra)
    return JSONResponse(content=corpo, media_type=PROBLEM_MEDIA_TYPE, status_code=status_code)


async def domain_problem_handler(request: Request, exception: Exception) -> JSONResponse:
    assert isinstance(exception, DomainProblem)
    return problem_response(
        request=request,
        status_code=exception.status_code,
        reason_code=exception.reason_code,
        title=exception.title,
        detail=exception.detail,
    )


async def validation_problem_handler(request: Request, exception: Exception) -> JSONResponse:
    """Entrada malformada é falha do cliente, e ele precisa saber onde."""
    assert isinstance(exception, RequestValidationError)
    campos = [
        {
            "campo": ".".join(str(parte) for parte in erro.get("loc", ())),
            "mensagem": erro.get("msg", ""),
        }
        for erro in exception.errors()
    ]
    return problem_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        reason_code="ENTRADA_INVALIDA",
        title="Entrada inválida",
        detail="A requisição não atende ao contrato declarado.",
        extra={"errors": campos},
    )


async def unexpected_error_handler(request: Request, exception: Exception) -> JSONResponse:
    """Sanitiza o inesperado: código estável, e nenhum detalhe interno."""
    return problem_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        reason_code="ERRO_INTERNO",
        title="Erro interno",
        detail="A requisição não pôde ser concluída.",
    )
