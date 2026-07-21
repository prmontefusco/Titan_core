from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class HealthResponse(BaseModel):
    status: Literal["ok"]


app = FastAPI(title="Titan API", version="0.0.0")


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
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Verificar a saúde do processo",
    tags=["técnico"],
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
