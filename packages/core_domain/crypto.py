"""Modelo canônico de Contratos Criptográficos do Domínio Titan (ADR-0038/Passo 5.5)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId


class CryptographicProfile(StrEnum):
    INTERNAL_INTEGRITY = "INTERNAL_INTEGRITY"
    INSTITUTIONAL_SIGNATURE = "INSTITUTIONAL_SIGNATURE"
    JURISDICTION_QUALIFIED = "JURISDICTION_QUALIFIED"


class SignatureStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    INDETERMINATE = "INDETERMINATE"


class KeyState(StrEnum):
    ACTIVE = "ACTIVE"
    ROTATED = "ROTATED"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class KeyIdentifier:
    key_id: TypedId
    purpose: str

    def __post_init__(self) -> None:
        if self.key_id.entity_type != "key":
            raise ValueError("key_id deve ser do tipo 'key'.")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ValueError("purpose de KeyIdentifier deve ser uma string não vazia.")


@dataclass(frozen=True, slots=True)
class KeyRecord:
    key_identifier: KeyIdentifier
    organization_id: OrganizationId
    public_key_fingerprint: str
    state: KeyState
    activated_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.key_identifier, KeyIdentifier):
            raise TypeError("key_identifier deve ser uma instância de KeyIdentifier.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser uma instância de OrganizationId.")
        if (
            not isinstance(self.public_key_fingerprint, str)
            or not self.public_key_fingerprint.strip()
        ):
            raise ValueError("public_key_fingerprint deve ser uma string não vazia.")
        if not isinstance(self.state, KeyState):
            raise TypeError("state deve ser um KeyState válido.")
        if self.state == KeyState.REVOKED:
            if self.revoked_at is None:
                raise ValueError("Chave no estado REVOKED exige revoked_at preenchido.")
            if not isinstance(self.revocation_reason, str) or not self.revocation_reason.strip():
                raise ValueError("Chave no estado REVOKED exige revocation_reason não vazio.")
        if self.version < 1:
            raise ValueError("A versão do KeyRecord deve ser >= 1.")

    def rotate(self, rotated_at: datetime) -> "KeyRecord":
        if self.state != KeyState.ACTIVE:
            raise ValueError("Apenas chaves no estado ACTIVE podem ser rotacionadas.")
        return KeyRecord(
            key_identifier=self.key_identifier,
            organization_id=self.organization_id,
            public_key_fingerprint=self.public_key_fingerprint,
            state=KeyState.ROTATED,
            activated_at=self.activated_at,
            expires_at=rotated_at,
            revoked_at=self.revoked_at,
            revocation_reason=self.revocation_reason,
            version=self.version + 1,
        )

    def revoke(self, revoked_at: datetime, reason: str) -> "KeyRecord":
        if self.state == KeyState.REVOKED:
            raise ValueError("Chave já se encontra no estado REVOKED.")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Motivo de revogação da chave deve ser uma string não vazia.")
        return KeyRecord(
            key_identifier=self.key_identifier,
            organization_id=self.organization_id,
            public_key_fingerprint=self.public_key_fingerprint,
            state=KeyState.REVOKED,
            activated_at=self.activated_at,
            expires_at=self.expires_at,
            revoked_at=revoked_at,
            revocation_reason=reason,
            version=self.version + 1,
        )


@dataclass(frozen=True, slots=True)
class CryptographicSignature:
    signature_id: TypedId
    profile: CryptographicProfile
    algorithm: str
    raw_signature: bytes
    key_identifier: KeyIdentifier
    signed_at: datetime

    def __post_init__(self) -> None:
        if self.signature_id.entity_type != "signature":
            raise ValueError("signature_id deve ser do tipo 'signature'.")
        if not isinstance(self.profile, CryptographicProfile):
            raise TypeError("profile deve ser um CryptographicProfile válido.")
        if not isinstance(self.algorithm, str) or not self.algorithm.strip():
            raise ValueError("algorithm deve ser uma string não vazia.")
        if not isinstance(self.raw_signature, bytes) or not self.raw_signature:
            raise ValueError("raw_signature deve ser um objeto bytes não vazio.")
        if not isinstance(self.key_identifier, KeyIdentifier):
            raise TypeError("key_identifier deve ser uma instância de KeyIdentifier.")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    status: SignatureStatus
    profile: CryptographicProfile
    validated_at: datetime
    key_identifier: KeyIdentifier
    scope: str
    details: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, SignatureStatus):
            raise TypeError("status deve ser um SignatureStatus válido.")
        if not isinstance(self.profile, CryptographicProfile):
            raise TypeError("profile deve ser um CryptographicProfile válido.")
        if not isinstance(self.key_identifier, KeyIdentifier):
            raise TypeError("key_identifier deve ser uma instância de KeyIdentifier.")
        if not isinstance(self.scope, str) or not self.scope.strip():
            raise ValueError("scope deve ser uma string não vazia.")
        if not isinstance(self.details, str) or not self.details.strip():
            raise ValueError("details deve ser uma string não vazia.")
