"""Adapters criptográficos de software para desenvolvimento e testes (ADR-0038/Passo 5.4)."""

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.core_domain.crypto import (
    CryptographicProfile,
    CryptographicSignature,
    KeyIdentifier,
    SignatureStatus,
    ValidationResult,
)
from packages.shared_kernel import TypedId


@dataclass(slots=True)
class SoftwareKeyProvider:
    """Provedor in-memory de chaves públicas/secretas para ambientes de desenvolvimento e teste."""

    _keys: dict[str, bytes] = field(default_factory=dict)

    def register_key(self, key_identifier: KeyIdentifier, secret_key: bytes) -> None:
        if not isinstance(secret_key, bytes) or not secret_key:
            raise ValueError("secret_key deve ser bytes não vazio.")
        self._keys[str(key_identifier.key_id.value)] = secret_key

    def get_public_key(self, key_identifier: KeyIdentifier) -> bytes | None:
        secret = self._keys.get(str(key_identifier.key_id.value))
        if secret is None:
            return None
        # Para HMAC/dev, a chave pública e derivada como SHA-256 do segredo
        return hashlib.sha256(secret).digest()


@dataclass(slots=True)
class SoftwareSigningProvider:
    key_provider: SoftwareKeyProvider

    def sign(
        self,
        content_hash: bytes,
        key_identifier: KeyIdentifier,
        profile: CryptographicProfile,
    ) -> CryptographicSignature:
        secret = self.key_provider._keys.get(str(key_identifier.key_id.value))
        if secret is None:
            raise KeyError(f"Chave {key_identifier.key_id.value} não encontrada no provedor.")

        raw_sig = hmac.new(secret, content_hash, hashlib.sha256).digest()
        return CryptographicSignature(
            signature_id=TypedId.new("signature"),
            profile=profile,
            algorithm="HMAC-SHA256",
            raw_signature=raw_sig,
            key_identifier=key_identifier,
            signed_at=datetime.now(UTC),
        )


@dataclass(slots=True)
class SoftwareTrustValidator:
    key_provider: SoftwareKeyProvider

    def validate(
        self,
        content_hash: bytes,
        signature: CryptographicSignature,
        scope: str,
    ) -> ValidationResult:
        now = datetime.now(UTC)
        secret = self.key_provider._keys.get(str(signature.key_identifier.key_id.value))

        if secret is None:
            return ValidationResult(
                status=SignatureStatus.INDETERMINATE,
                profile=signature.profile,
                validated_at=now,
                key_identifier=signature.key_identifier,
                scope=scope,
                details="Chave pública ou autoridade emissora desconhecida.",
            )

        expected_sig = hmac.new(secret, content_hash, hashlib.sha256).digest()
        if hmac.compare_digest(expected_sig, signature.raw_signature):
            return ValidationResult(
                status=SignatureStatus.VALID,
                profile=signature.profile,
                validated_at=now,
                key_identifier=signature.key_identifier,
                scope=scope,
                details="Assinatura validada com sucesso.",
            )

        return ValidationResult(
            status=SignatureStatus.INVALID,
            profile=signature.profile,
            validated_at=now,
            key_identifier=signature.key_identifier,
            scope=scope,
            details="Assinatura inválida: o conteúdo foi adulterado ou a chave diverge.",
        )
