"""Testes unitários dos contratos criptográficos do domínio (ADR-0038/Passo 5.4 e 5.5)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.core_domain.crypto import (
    CryptographicProfile,
    CryptographicSignature,
    KeyIdentifier,
    KeyRecord,
    KeyState,
    SignatureStatus,
    ValidationResult,
)
from packages.shared_kernel import OrganizationId, TypedId


def test_key_identifier_validation() -> None:
    key_id = TypedId.new("key")
    ki = KeyIdentifier(key_id=key_id, purpose="Assinatura institucional de documentos")
    assert ki.key_id == key_id
    assert ki.purpose == "Assinatura institucional de documentos"

    with pytest.raises(ValueError, match="key_id deve ser do tipo 'key'"):
        KeyIdentifier(key_id=TypedId.new("user"), purpose="Invalid")

    with pytest.raises(ValueError, match="purpose de KeyIdentifier deve ser uma string não vazia"):
        KeyIdentifier(key_id=key_id, purpose="   ")


def test_cryptographic_signature_creation() -> None:
    ki = KeyIdentifier(key_id=TypedId.new("key"), purpose="Integridade interna")
    sig = CryptographicSignature(
        signature_id=TypedId.new("signature"),
        profile=CryptographicProfile.INTERNAL_INTEGRITY,
        algorithm="HMAC-SHA256",
        raw_signature=b"raw_bytes_signature_12345",
        key_identifier=ki,
        signed_at=datetime.now(UTC),
    )

    assert sig.profile == CryptographicProfile.INTERNAL_INTEGRITY
    assert sig.algorithm == "HMAC-SHA256"
    assert sig.raw_signature == b"raw_bytes_signature_12345"
    assert sig.key_identifier == ki


def test_validation_result_creation() -> None:
    ki = KeyIdentifier(key_id=TypedId.new("key"), purpose="Assinatura qualificada")
    vr = ValidationResult(
        status=SignatureStatus.VALID,
        profile=CryptographicProfile.JURISDICTION_QUALIFIED,
        validated_at=datetime.now(UTC),
        key_identifier=ki,
        scope="core_audit.evidences",
        details="Assinatura validada com sucesso",
    )

    assert vr.status == SignatureStatus.VALID
    assert vr.profile == CryptographicProfile.JURISDICTION_QUALIFIED
    assert vr.scope == "core_audit.evidences"


def test_key_record_lifecycle_and_invariants() -> None:
    ki = KeyIdentifier(key_id=TypedId.new("key"), purpose="Assinaturas auditadas")
    org_id = OrganizationId(uuid4())
    now = datetime.now(UTC)

    kr = KeyRecord(
        key_identifier=ki,
        organization_id=org_id,
        public_key_fingerprint="sha256:abc123def456",
        state=KeyState.ACTIVE,
        activated_at=now,
    )

    assert kr.state == KeyState.ACTIVE
    assert kr.version == 1

    # Rotação da chave
    rotated = kr.rotate(rotated_at=now)
    assert rotated.state == KeyState.ROTATED
    assert rotated.expires_at == now
    assert rotated.version == 2

    # Tentativa de rotacionar chave já rotacionada lança ValueError
    with pytest.raises(ValueError, match="Apenas chaves no estado ACTIVE podem ser rotacionadas"):
        rotated.rotate(rotated_at=now)

    # Revogação da chave
    revoked = kr.revoke(revoked_at=now, reason="Suspeita de vazamento de credencial")
    assert revoked.state == KeyState.REVOKED
    assert revoked.revoked_at == now
    assert revoked.revocation_reason == "Suspeita de vazamento de credencial"
    assert revoked.version == 2

    # Invariante: estado REVOKED sem motivo lança erro
    msg = "Chave no estado REVOKED exige revocation_reason não vazio"
    with pytest.raises(ValueError, match=msg):
        KeyRecord(
            key_identifier=ki,
            organization_id=org_id,
            public_key_fingerprint="sha256:abc123def456",
            state=KeyState.REVOKED,
            activated_at=now,
            revoked_at=now,
            revocation_reason="   ",
        )
