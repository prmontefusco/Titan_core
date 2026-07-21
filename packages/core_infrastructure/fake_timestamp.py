"""Provider temporal sintético, gratuito e não confiável para desenvolvimento."""

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from packages.core_application import (
    TimestampAttempt,
    TimestampAttemptStatus,
    TimestampProviderResponse,
    TimestampRequest,
    TimestampValidation,
    TimestampValidationStatus,
)
from packages.shared_kernel import Clock, TypedId
from packages.shared_kernel.temporal import require_utc

MAX_FAKE_TOKEN_SIZE = 16_384
FAKE_SIGNATURE_ALGORITHM = "HMAC-SHA256-FAKE-ONLY"


@dataclass(frozen=True, slots=True)
class FakeTimestampProfile:
    provider_id: str
    policy: str
    authority_id: str
    trust_chain: tuple[str, ...]
    secret: bytes = field(repr=False)
    token_lifetime: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if not all((self.provider_id, self.policy, self.authority_id, self.trust_chain)):
            raise ValueError("O perfil falso exige provider, policy, authority e trust_chain.")
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise ValueError("O segredo sintético deve possuir ao menos 32 bytes.")
        if self.token_lifetime <= timedelta(0):
            raise ValueError("token_lifetime deve ser positivo.")


@dataclass(frozen=True, slots=True)
class FakeTimestampProvider:
    profile: FakeTimestampProfile
    clock: Clock
    available: bool = True
    unknown_outcome: bool = False

    @property
    def provider_id(self) -> str:
        return self.profile.provider_id

    def issue(self, request: TimestampRequest) -> TimestampProviderResponse:
        from packages.core_application import (
            TimestampProviderUnavailable,
            TimestampProviderUnknownOutcome,
        )

        if not self.available:
            raise TimestampProviderUnavailable("PROVIDER_INDISPONIVEL")
        if self.unknown_outcome:
            raise TimestampProviderUnknownOutcome("RESULTADO_DESCONHECIDO")
        issued_at = require_utc(self.clock.now(), field_name="clock.now()")
        body = {
            "algoritmo_assinatura": FAKE_SIGNATURE_ALGORITHM,
            "algoritmo_digest": request.digest_algorithm,
            "authority_id": self.profile.authority_id,
            "emitido_em": issued_at.isoformat(),
            "finalidade": "TIMESTAMP_DE_DESENVOLVIMENTO",
            "imprint_hex": request.message_imprint.hex(),
            "nonce_hex": request.nonce.hex(),
            "policy": request.policy,
            "provider_id": self.profile.provider_id,
            "trust_chain": list(self.profile.trust_chain),
            "valido_ate": (issued_at + self.profile.token_lifetime).isoformat(),
        }
        body_bytes = _body_bytes(body)
        signature = hmac.new(self.profile.secret, body_bytes, hashlib.sha256).hexdigest()
        token = _token_bytes(body, signature)
        return TimestampProviderResponse(self.provider_id, token, issued_at)


@dataclass(frozen=True, slots=True)
class FakeTimestampTokenValidator:
    profile: FakeTimestampProfile

    def validate(
        self,
        *,
        validation_id: TypedId,
        attempt: TimestampAttempt,
        validated_at: datetime,
    ) -> TimestampValidation:
        require_utc(validated_at, field_name="validated_at")
        if attempt.status is not TimestampAttemptStatus.TOKEN_RECEBIDO or attempt.raw_token is None:
            return _validation(
                validation_id,
                attempt,
                TimestampValidationStatus.INDETERMINADO,
                "TOKEN_NAO_RECEBIDO",
                validated_at,
                None,
                b"\x00" * 32,
            )
        token_digest = hashlib.sha256(attempt.raw_token).digest()
        try:
            body, signature = _parse_token(attempt.raw_token)
        except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
            return _validation(
                validation_id,
                attempt,
                TimestampValidationStatus.INVALIDO,
                "FORMATO_INVALIDO",
                validated_at,
                None,
                token_digest,
            )
        checks = (
            (body.get("algoritmo_assinatura") == FAKE_SIGNATURE_ALGORITHM, "ALGORITMO_INVALIDO"),
            (body.get("provider_id") == self.profile.provider_id, "PROVIDER_DIVERGENTE"),
            (
                body.get("policy") == attempt.request.policy == self.profile.policy,
                "POLITICA_DIVERGENTE",
            ),
            (
                body.get("imprint_hex") == attempt.request.message_imprint.hex(),
                "IMPRINT_DIVERGENTE",
            ),
            (body.get("nonce_hex") == attempt.request.nonce.hex(), "NONCE_DIVERGENTE"),
            (body.get("authority_id") == self.profile.authority_id, "AUTORIDADE_DIVERGENTE"),
            (tuple(body.get("trust_chain", ())) == self.profile.trust_chain, "CADEIA_DIVERGENTE"),
        )
        for valid, reason in checks:
            if not valid:
                return _validation(
                    validation_id,
                    attempt,
                    TimestampValidationStatus.INVALIDO,
                    reason,
                    validated_at,
                    None,
                    token_digest,
                )
        expected = hmac.new(self.profile.secret, _body_bytes(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return _validation(
                validation_id,
                attempt,
                TimestampValidationStatus.INVALIDO,
                "ASSINATURA_INVALIDA",
                validated_at,
                None,
                token_digest,
            )
        try:
            issued_at = datetime.fromisoformat(str(body["emitido_em"])).astimezone(UTC)
            valid_until = datetime.fromisoformat(str(body["valido_ate"])).astimezone(UTC)
        except (KeyError, ValueError):
            return _validation(
                validation_id,
                attempt,
                TimestampValidationStatus.INVALIDO,
                "VALIDADE_INVALIDA",
                validated_at,
                None,
                token_digest,
            )
        if issued_at > validated_at or validated_at > valid_until:
            return _validation(
                validation_id,
                attempt,
                TimestampValidationStatus.INVALIDO,
                "VALIDADE_INVALIDA",
                validated_at,
                None,
                token_digest,
            )
        return _validation(
            validation_id,
            attempt,
            TimestampValidationStatus.VALIDO,
            "TOKEN_VALIDO_PARA_DESENVOLVIMENTO",
            validated_at,
            issued_at,
            token_digest,
        )


def _body_bytes(body: dict[str, Any]) -> bytes:
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _token_bytes(body: dict[str, Any], signature: str) -> bytes:
    return json.dumps(
        {"body": body, "signature": signature},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _parse_token(raw_token: bytes) -> tuple[dict[str, Any], str]:
    if len(raw_token) > MAX_FAKE_TOKEN_SIZE:
        raise ValueError("Token excede limite.")
    parsed = json.loads(raw_token.decode("utf-8"))
    if not isinstance(parsed, dict) or set(parsed) != {"body", "signature"}:
        raise ValueError("Envelope inválido.")
    body = parsed["body"]
    signature = parsed["signature"]
    if not isinstance(body, dict) or not isinstance(signature, str):
        raise TypeError("Tipos inválidos.")
    return body, signature


def _validation(
    validation_id: TypedId,
    attempt: TimestampAttempt,
    status: TimestampValidationStatus,
    reason_code: str,
    validated_at: datetime,
    proved_at: datetime | None,
    token_digest: bytes,
) -> TimestampValidation:
    return TimestampValidation(
        validation_id,
        attempt.request.attempt_id,
        status,
        reason_code,
        validated_at,
        proved_at,
        token_digest,
    )
