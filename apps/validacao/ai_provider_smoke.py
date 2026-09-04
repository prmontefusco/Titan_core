"""Roteiro local de fumaça para provider de IA com payload sintético.

Este roteiro não integra IA ao Titan. Ele apenas valida que uma chave local,
mantida fora do Git em `.env.ai.local`, consegue chamar a Gemini API com um
prompt sintético sem dados do Titan, produtores, animais, Organizations ou
artefatos reais.

Uso:
python -m uv run --locked python -m apps.validacao.ai_provider_smoke
python -m uv run --locked python -m apps.validacao.ai_provider_smoke --pausar
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.validacao.runner import CINZA, FIM, NEGRITO, VERDE, VERMELHO

ENV_FILE = Path(".env.ai.local")
MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=50"
PREFERRED_GENERATE_MODELS = (
    "models/gemini-3.8-flash",
    "models/gemini-3.7-flash",
    "models/gemini-3.5-flash-lite",
)


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: Any


def _load_api_key() -> str:
    if "GOOGLE_AI_API_KEY" in os.environ and os.environ["GOOGLE_AI_API_KEY"].strip():
        return os.environ["GOOGLE_AI_API_KEY"].strip()
    if not ENV_FILE.exists():
        raise SystemExit(
            f"{VERMELHO}Arquivo {ENV_FILE} não encontrado.{FIM}\n"
            "Crie o arquivo local e defina GOOGLE_AI_API_KEY sem commitar secrets."
        )
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("GOOGLE_AI_API_KEY="):
            _, value = line.split("=", 1)
            key = value.strip()
            if key:
                return key
    raise SystemExit(
        f"{VERMELHO}GOOGLE_AI_API_KEY está ausente ou vazia em {ENV_FILE}.{FIM}\n"
        "Cole uma chave nova no arquivo local ignorado pelo Git e rode novamente."
    )


def _request(
    *,
    url: str,
    api_key: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> HttpResponse:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "X-goog-api-key": api_key,
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return HttpResponse(
                status=response.status,
                body=json.loads(raw) if raw else None,
            )
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            payload: Any = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw.decode("utf-8", errors="replace")
        return HttpResponse(status=error.code, body=_safe_error(payload))
    except urllib.error.URLError as error:
        raise SystemExit(f"{VERMELHO}Provider indisponível: {error.reason}{FIM}") from error


def _generate_with_first_available(
    *,
    api_key: str,
    model_names: tuple[str, ...],
) -> tuple[str, HttpResponse]:
    last_response: HttpResponse | None = None
    for model_name in model_names:
        generated = _request(
            url=f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent",
            api_key=api_key,
            method="POST",
            body=_synthetic_prompt_body(),
        )
        if generated.status == 200:
            return model_name, generated
        last_response = generated
    if last_response is None:
        return "", HttpResponse(status=0, body={"error": "NO_MODEL_CANDIDATES"})
    return model_names[-1], last_response


def _safe_error(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return "PROVIDER_ERROR_PAYLOAD_REDACTED"
    error = payload.get("error")
    if not isinstance(error, dict):
        return {"error": "PROVIDER_ERROR_PAYLOAD_REDACTED"}
    return {
        "error": {
            "code": error.get("code"),
            "status": error.get("status"),
            "message": error.get("message"),
        }
    }


def _safe_preview(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: (
                "REDACTED_PROVIDER_INTERNAL_FIELD"
                if key in {"thoughtSignature", "executableCode", "codeExecutionResult"}
                else _safe_preview(value)
            )
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [_safe_preview(value) for value in payload]
    return payload


def _synthetic_prompt_body() -> dict[str, Any]:
    return {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Return exactly: TITAN_AI_PROVIDER_SMOKE_OK. "
                            "This is a synthetic connectivity test."
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 128,
        },
    }


def _extract_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    content = candidates[0].get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    return "".join(texts).strip()


def _select_generate_model(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    models = payload.get("models")
    if not isinstance(models, list):
        return None
    candidates: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        methods = item.get("supportedGenerationMethods")
        if not isinstance(name, str) or not isinstance(methods, list):
            continue
        if "generateContent" in methods and "gemini" in name:
            candidates.append(name)
    return sorted(candidates, key=_model_preference)[0] if candidates else None


def _model_preference(name: str) -> tuple[int, str]:
    if "flash" in name and "tts" not in name and "image" not in name:
        return (0, name)
    if "pro" in name and "tts" not in name and "image" not in name:
        return (1, name)
    return (2, name)


def _print_body(value: Any) -> None:
    text = json.dumps(_safe_preview(value), indent=2, ensure_ascii=False, default=str)
    for line in text.splitlines()[:18]:
        print(f"{CINZA}     {line}{FIM}")


def _pause(enabled: bool) -> None:
    if enabled:
        input(f"{CINZA}  — ENTER para o próximo —{FIM}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pausar", action="store_true")
    args = parser.parse_args()

    print(f"\n{NEGRITO}AI provider smoke — Gemini API sintética{FIM}")
    print("=" * 52)
    print(
        f"{CINZA}A chave é carregada de variável de ambiente ou .env.ai.local "
        f"e nunca impressa.{FIM}"
    )

    api_key = _load_api_key()

    print(f"\n{NEGRITO}[1] Listar modelos disponíveis{FIM}")
    print(
        f"{CINZA}  Por que: confirma autenticação básica sem enviar dados Titan ao provider.{FIM}"
    )
    models = _request(url=MODELS_URL, api_key=api_key)
    print(f"  {CINZA}<-{FIM} {NEGRITO}{models.status}{FIM}")
    if models.status != 200 or not isinstance(models.body, dict):
        print(f"{VERMELHO}FALHOU{FIM} — a Gemini API não aceitou a chave para listar modelos.")
        _print_body(models.body)
        return 1
    names = [
        name
        for item in models.body.get("models", [])
        if isinstance(item, dict) and isinstance((name := item.get("name")), str)
    ]
    listed_model = _select_generate_model(models.body)
    if listed_model is None:
        print(f"{VERMELHO}FALHOU{FIM} — nenhum modelo Gemini com generateContent foi listado.")
        return 1
    print(f"{VERDE}OK{FIM} — provider alcançável; modelos vistos: {', '.join(names[:5])}")
    model_candidates = tuple(dict.fromkeys((*PREFERRED_GENERATE_MODELS, listed_model)))
    print(f"{CINZA}Candidatos sintéticos: {', '.join(model_candidates)}{FIM}")
    _pause(args.pausar)

    print(f"\n{NEGRITO}[2] Gerar resposta com prompt sintético mínimo{FIM}")
    print(
        f"{CINZA}  Por que: valida generateContent sem dados de domínio, tenant ou produtor.{FIM}"
    )
    selected_model, generated = _generate_with_first_available(
        api_key=api_key,
        model_names=model_candidates,
    )
    print(f"  {CINZA}<-{FIM} {NEGRITO}{generated.status}{FIM}")
    if generated.status != 200:
        print(f"{VERMELHO}FALHOU{FIM} — generateContent não foi aceito pelo provider.")
        _print_body(generated.body)
        return 1

    print(f"{VERDE}OK{FIM} — generateContent respondeu ao payload sintético.")
    text = _extract_text(generated.body)
    if text:
        print(f"{CINZA}Texto recebido e omitido; este roteiro valida só conectividade.{FIM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
