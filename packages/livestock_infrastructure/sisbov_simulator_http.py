"""Adapter HTTP exclusivo do simulador local SISBOV.

Credenciais existem somente na instância em memória. Tokens e corpos não são logados
nem persistidos por este adapter.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from packages.livestock_application.sisbov_simulator import (
    SisbovSimulatorRequest,
    SisbovSimulatorTransportPort,
    SisbovSimulatorTransportResponse,
)


class SisbovSimulatorHttpClientPort(Protocol):
    def request(self, method: str, path: str, headers: dict[str, str]) -> tuple[int, bytes]: ...


@dataclass(frozen=True, slots=True)
class UrllibSisbovSimulatorHttpClient:
    base_url: str
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not self.base_url.startswith("http://127.0.0.1:"):
            raise ValueError("O adapter do Corte 3 aceita apenas simulador em loopback.")

    def request(self, method: str, path: str, headers: dict[str, str]) -> tuple[int, bytes]:
        request = Request(f"{self.base_url.rstrip('/')}{path}", method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()
        except URLError:
            return 503, b""


@dataclass(frozen=True, slots=True)
class SisbovSimulatorHttpTransport(SisbovSimulatorTransportPort):
    """Obtém JWT efêmero por requisição e executa somente GET allowlisted."""

    client: SisbovSimulatorHttpClientPort
    access_key: str
    secret_key: str

    def __post_init__(self) -> None:
        if not self.access_key.strip() or not self.secret_key.strip():
            raise ValueError("Credenciais de desenvolvimento do simulador são obrigatórias.")

    def get(self, request: SisbovSimulatorRequest) -> SisbovSimulatorTransportResponse:
        try:
            status, body = self.client.request(
                "POST",
                "/auth/system",
                {"X-ACCESS-KEY": self.access_key, "X-SECRET-KEY": self.secret_key},
            )
            token = _token(status, body)
            if token is None:
                return SisbovSimulatorTransportResponse(status, body, datetime.now(UTC))
            status, body = self.client.request(
                "GET", request.path, {"Authorization": f"Bearer {token}"}
            )
            return SisbovSimulatorTransportResponse(status, body, datetime.now(UTC))
        except (OSError, ValueError):
            return SisbovSimulatorTransportResponse(503, b"", datetime.now(UTC))


def _token(status: int, body: bytes) -> str | None:
    if status != 200:
        return None
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    token = value.get("access_token") if isinstance(value, dict) else None
    return token if isinstance(token, str) and token else None
