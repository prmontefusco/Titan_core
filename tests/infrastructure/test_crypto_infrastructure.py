"""Testes dos adapters criptográficos de software (Passo 5.4)."""

import hashlib

from packages.core_domain.crypto import (
    CryptographicProfile,
    KeyIdentifier,
    SignatureStatus,
)
from packages.core_infrastructure.crypto import (
    SoftwareKeyProvider,
    SoftwareSigningProvider,
    SoftwareTrustValidator,
)
from packages.shared_kernel import TypedId


def test_software_crypto_provider_signing_and_verification_flow() -> None:
    key_provider = SoftwareKeyProvider()
    key_id = KeyIdentifier(
        key_id=TypedId.new("key"),
        purpose="Integridade de evidências",
    )
    secret_key = b"super_secret_dev_key_32_bytes_len!"
    key_provider.register_key(key_id, secret_key)

    signer = SoftwareSigningProvider(key_provider=key_provider)
    validator = SoftwareTrustValidator(key_provider=key_provider)

    content = b"Documento de teste imutavel do Titan Core"
    content_hash = hashlib.sha256(content).digest()

    # 1. Assina o conteúdo
    signature = signer.sign(
        content_hash=content_hash,
        key_identifier=key_id,
        profile=CryptographicProfile.INTERNAL_INTEGRITY,
    )

    assert signature.algorithm == "HMAC-SHA256"
    assert signature.key_identifier == key_id

    # 2. Valida a assinatura com o mesmo conteúdo
    res_valid = validator.validate(
        content_hash=content_hash,
        signature=signature,
        scope="evidences",
    )
    assert res_valid.status == SignatureStatus.VALID
    assert res_valid.profile == CryptographicProfile.INTERNAL_INTEGRITY

    # 3. Altera o conteúdo e tenta validar (deve retornar INVALID)
    altered_hash = hashlib.sha256(b"Conteudo alterado ilicitamente").digest()
    res_invalid = validator.validate(
        content_hash=altered_hash,
        signature=signature,
        scope="evidences",
    )
    assert res_invalid.status == SignatureStatus.INVALID

    # 4. Tenta validar com uma chave desconhecida (deve retornar INDETERMINATE)
    unknown_key_id = KeyIdentifier(key_id=TypedId.new("key"), purpose="Outra chave")
    unknown_signer = SoftwareSigningProvider(key_provider=SoftwareKeyProvider())

    # Registra a chave no signer desconhecido para conseguir assinar
    unknown_signer.key_provider.register_key(unknown_key_id, b"outro_segredo_12345678901234567890")
    unknown_sig = unknown_signer.sign(
        content_hash=content_hash,
        key_identifier=unknown_key_id,
        profile=CryptographicProfile.INSTITUTIONAL_SIGNATURE,
    )

    res_indet = validator.validate(
        content_hash=content_hash,
        signature=unknown_sig,
        scope="evidences",
    )
    assert res_indet.status == SignatureStatus.INDETERMINATE
