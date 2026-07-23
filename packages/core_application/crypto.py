"""Portas de abstração criptográfica e serviço de gestão de chaves (ADR-0038/Passo 5.5)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.core_domain.crypto import (
    CryptographicProfile,
    CryptographicSignature,
    KeyIdentifier,
    KeyRecord,
    KeyState,
    ValidationResult,
)
from packages.shared_kernel import OrganizationId, TypedId


class KeyProviderPort(Protocol):
    def get_public_key(self, key_identifier: KeyIdentifier) -> bytes | None: ...


class SigningProviderPort(Protocol):
    def sign(
        self,
        content_hash: bytes,
        key_identifier: KeyIdentifier,
        profile: CryptographicProfile,
    ) -> CryptographicSignature: ...


class TrustValidatorPort(Protocol):
    def validate(
        self,
        content_hash: bytes,
        signature: CryptographicSignature,
        scope: str,
    ) -> ValidationResult: ...


class KeyRegistryPort(Protocol):
    def save(self, key_record: KeyRecord) -> None: ...

    def update(self, key_record: KeyRecord) -> None: ...

    def get_by_id(self, key_id: TypedId) -> KeyRecord | None: ...

    def get_active_key(self, organization_id: OrganizationId, purpose: str) -> KeyRecord | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[KeyRecord]: ...


@dataclass(frozen=True, slots=True)
class KeyManagementService:
    registry: KeyRegistryPort

    def register_key(
        self,
        organization_id: OrganizationId,
        purpose: str,
        public_key_fingerprint: str,
        expires_at: datetime | None = None,
    ) -> KeyRecord:
        now = datetime.now(UTC)
        key_identifier = KeyIdentifier(key_id=TypedId.new("key"), purpose=purpose)

        # Se já houver chave ativa para o mesmo propósito na mesma organização, desativa via rotação
        active_key = self.registry.get_active_key(organization_id, purpose)
        if active_key is not None:
            rotated_key = active_key.rotate(rotated_at=now)
            self.registry.update(rotated_key)

        new_key = KeyRecord(
            key_identifier=key_identifier,
            organization_id=organization_id,
            public_key_fingerprint=public_key_fingerprint,
            state=KeyState.ACTIVE,
            activated_at=now,
            expires_at=expires_at,
        )
        self.registry.save(new_key)
        return new_key

    def rotate_key(self, key_id: TypedId) -> KeyRecord:
        now = datetime.now(UTC)
        key_record = self.registry.get_by_id(key_id)
        if key_record is None:
            raise KeyError(f"Chave {key_id.value} não encontrada.")

        rotated = key_record.rotate(rotated_at=now)
        self.registry.update(rotated)
        return rotated

    def revoke_key(self, key_id: TypedId, reason: str) -> KeyRecord:
        now = datetime.now(UTC)
        key_record = self.registry.get_by_id(key_id)
        if key_record is None:
            raise KeyError(f"Chave {key_id.value} não encontrada.")

        revoked = key_record.revoke(revoked_at=now, reason=reason)
        self.registry.update(revoked)
        return revoked

    def get_key(self, key_id: TypedId) -> KeyRecord | None:
        return self.registry.get_by_id(key_id)

    def get_active_key(self, organization_id: OrganizationId, purpose: str) -> KeyRecord | None:
        return self.registry.get_active_key(organization_id, purpose)
