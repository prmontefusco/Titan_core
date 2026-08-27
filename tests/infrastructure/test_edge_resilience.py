"""Testes para Rate Limiting 429 e Log Redaction (ADR-0039)."""

import logging
from uuid import uuid4

from packages.core_infrastructure.log_redaction import RedactingLogFormatter, redact_data
from packages.core_infrastructure.rate_limiter import (
    SHARED_POLICY_EVALUATIONS_PER_MINUTE,
    InMemoryRateLimiter,
    shared_policy_evaluation_key,
    shared_policy_evaluation_rate_limiter,
)


def test_in_memory_rate_limiter_exceeds_quota() -> None:
    limiter = InMemoryRateLimiter(requests_per_minute=3)
    key = "192.168.1.100"
    base_time = 1000.0

    # 3 requisições permitidas
    r1 = limiter.check_rate_limit(key, current_time=base_time)
    assert r1.is_allowed is True
    assert r1.remaining == 2

    r2 = limiter.check_rate_limit(key, current_time=base_time + 1)
    assert r2.is_allowed is True
    assert r2.remaining == 1

    r3 = limiter.check_rate_limit(key, current_time=base_time + 2)
    assert r3.is_allowed is True
    assert r3.remaining == 0

    # 4ª requisição é bloqueada (429)
    r4 = limiter.check_rate_limit(key, current_time=base_time + 3)
    assert r4.is_allowed is False
    assert r4.remaining == 0
    assert r4.reset_after_seconds > 0

    # Após expirar a janela de 60s, volta a ser permitida
    r5 = limiter.check_rate_limit(key, current_time=base_time + 61.0)
    assert r5.is_allowed is True


def test_log_redaction_removes_secrets() -> None:
    payload = {
        "user_id": "usr_12345",
        "password": "my_super_secret_password",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "nested": {
            "api_key": "sk-1234567890",
            "normal_field": "public_data",
        },
    }

    cleaned = redact_data(payload)

    assert cleaned["user_id"] == "usr_12345"
    assert cleaned["password"] == "[REDACTED_SECRET]"
    assert cleaned["access_token"] == "[REDACTED_SECRET]"
    assert cleaned["nested"]["api_key"] == "[REDACTED_SECRET]"
    assert cleaned["nested"]["normal_field"] == "public_data"


def test_log_redaction_formatter() -> None:
    formatter = RedactingLogFormatter("%(levelname)s: %(message)s")
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Authorization header: Bearer eyJhbGciOi...",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    assert "[REDACTED_TOKEN]" in formatted
    assert "eyJhbGciOi..." not in formatted


def test_limitador_de_avaliacao_compartilhada_separa_baldes_por_grant() -> None:
    limiter = InMemoryRateLimiter(requests_per_minute=SHARED_POLICY_EVALUATIONS_PER_MINUTE)
    primeiro = shared_policy_evaluation_key(uuid4())
    segundo = shared_policy_evaluation_key(uuid4())
    base = 1000.0

    for passo in range(SHARED_POLICY_EVALUATIONS_PER_MINUTE):
        assert limiter.check_rate_limit(primeiro, current_time=base + passo).is_allowed

    excedido = limiter.check_rate_limit(primeiro, current_time=base + 11)
    assert excedido.is_allowed is False
    assert excedido.limit == SHARED_POLICY_EVALUATIONS_PER_MINUTE
    assert excedido.reset_after_seconds > 0

    # O grant vizinho tem cota propria: um contrato exaurido nao bloqueia o outro.
    assert limiter.check_rate_limit(segundo, current_time=base + 11).is_allowed


def test_limitador_de_avaliacao_compartilhada_e_unico_no_processo() -> None:
    assert shared_policy_evaluation_rate_limiter() is shared_policy_evaluation_rate_limiter()
    assert (
        shared_policy_evaluation_rate_limiter().requests_per_minute
        == SHARED_POLICY_EVALUATIONS_PER_MINUTE
    )
