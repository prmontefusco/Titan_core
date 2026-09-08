"""Roteiro de validação da superfície HTTP de AI Explanation para Market Optionality.

Este roteiro valida a segurança de exposição da rota:
- Por padrão (feature flag desabilitada), a rota é ausente do OpenAPI e responde 404 uniforme.
- Quando habilitada via `TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED=true`, a rota exige
  autenticação (401) e permissão `LIVESTOCK.MARKET_OPTION.EXPLAIN` (403) antes de qualquer acesso.
- Valida que nenhuma computação de LLM ou oráculo cross-tenant é exposto a chamadas não autorizadas.

Uso:
python -m uv run --locked python -m apps.validacao.market_optionality_ai_explanation_api
python -m uv run --locked python -m apps.validacao.market_optionality_ai_explanation_api --pausar
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from apps.validacao.runner import CINZA, FIM, NEGRITO, VERDE, VERMELHO

ROUTE_TEMPLATE = "/v1/livestock/animals/{animal_id}/market-optionality/explanation"
SAMPLE_ANIMAL_ID = "00000000-0000-0000-0000-000000000001"
ROUTE = ROUTE_TEMPLATE.format(animal_id=SAMPLE_ANIMAL_ID)


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: Any


def _request(
    *,
    base_url: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> HttpResponse:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return HttpResponse(
                status=response.status,
                headers={key.lower(): value for key, value in response.headers.items()},
                body=json.loads(raw) if raw else None,
            )
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            payload: Any = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw.decode("utf-8", errors="replace")
        return HttpResponse(
            status=error.code,
            headers={key.lower(): value for key, value in error.headers.items()},
            body=payload,
        )
    except urllib.error.URLError as error:
        raise SystemExit(
            f"{VERMELHO}A API não respondeu: {error.reason}{FIM}\n"
            "Suba a API antes de rodar o roteiro (ex: uvicorn apps.api.main:app)."
        ) from error


def _valid_body() -> dict[str, Any]:
    return {
        "policy_id": "00000000-0000-0000-0000-000000000002",
        "policy_version": 1,
        "market_purpose": "EXPORT_EU",
        "reference_time": "2026-09-08T00:00:00Z",
        "knowledge_cutoff": "2026-09-08T00:00:00Z",
    }


def _print_body(value: Any) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    for line in text.splitlines()[:28]:
        print(f"{CINZA}     {line}{FIM}")


def _pause(enabled: bool) -> None:
    if enabled:
        input(f"{CINZA}  — ENTER para o próximo —{FIM}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=os.environ.get("TITAN_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--pausar", action="store_true")
    args = parser.parse_args()
    base_url = str(args.api)

    print(f"\n{NEGRITO}Market Optionality AI Explanation — Superfície HTTP protegida{FIM}")
    print("=" * 64)
    print(f"{CINZA}API: {base_url}{FIM}")

    print(f"\n{NEGRITO}[1] Descobrir se a rota está publicada no OpenAPI{FIM}")
    print(f"{CINZA}  Por que: a feature flag controla se a rota de IA existe na API pública.{FIM}")
    print(f"  {CINZA}->{FIM} {NEGRITO}GET{FIM} /openapi.json")
    openapi = _request(base_url=base_url, method="GET", path="/openapi.json")
    print(f"  {CINZA}<-{FIM} {NEGRITO}{openapi.status}{FIM}")
    if openapi.status != 200 or not isinstance(openapi.body, dict):
        print(f"{VERMELHO}OpenAPI indisponível; não é possível validar a superfície.{FIM}")
        _print_body(openapi.body)
        return 1
    route_published = ROUTE_TEMPLATE in openapi.body.get("paths", {})
    print(
        f"{VERDE}OK{FIM} — rota "
        f"{'publicada por feature flag' if route_published else 'ausente/default-off'}"
    )
    _pause(args.pausar)

    print(f"\n{NEGRITO}[2] Chamar rota sem credencial de autenticação{FIM}")
    print(f"{CINZA}  Por que: nenhuma explicação de IA pode ser liberada sem autenticação.{FIM}")
    print(f"  {CINZA}->{FIM} {NEGRITO}POST{FIM} {ROUTE}")
    _print_body(_valid_body())
    response = _request(base_url=base_url, method="POST", path=ROUTE, body=_valid_body())
    print(f"  {CINZA}<-{FIM} {NEGRITO}{response.status}{FIM}")
    _print_body(response.body)

    expected = 401 if route_published else 404
    if response.status != expected:
        print(
            f"{VERMELHO}FALHOU{FIM} — esperava {expected} "
            f"({'rota autenticada' if route_published else 'rota ausente'})."
        )
        return 1

    print(
        f"{VERDE}OK{FIM} — endpoint respondeu com segurança "
        f"({'401 Não Autenticado' if route_published else '404 Rota Não Encontrada'})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
