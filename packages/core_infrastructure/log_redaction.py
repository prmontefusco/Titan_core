"""Módulo de mascaramento de logs para prevencão de vazamento (ADR-0039)."""

import logging
import re
from typing import Any

_SECRET_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "client_secret",
        "id_token",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "token",
    }
)

_CPF_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b")
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[a-zA-Z0-9\-\._~\+\/]+=*", re.IGNORECASE)


def redact_data(data: Any) -> Any:
    """Higieniza recursivamente dicionários e strings omitindo segredos e tokens de acesso."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if str(k).casefold() in _SECRET_KEYS:
                cleaned[k] = "[REDACTED_SECRET]"
            else:
                cleaned[k] = redact_data(v)
        return cleaned
    if isinstance(data, list):
        return [redact_data(item) for item in data]
    if isinstance(data, str):
        result = _BEARER_PATTERN.sub("Bearer [REDACTED_TOKEN]", data)
        return result
    return data


class RedactingLogFormatter(logging.Formatter):
    """Formatter customizado que intercepta e higieniza a mensagem do log antes de emitir."""

    def format(self, record: logging.LogRecord) -> str:
        original_msg = super().format(record)
        redacted = redact_data(original_msg)
        return str(redacted)
