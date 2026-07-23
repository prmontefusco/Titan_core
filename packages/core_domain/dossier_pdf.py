"""Modelo de domínio para representação PDF verificável do Dossier (Passo 7.8).

O Dossier continua sendo o modelo conceitual primário de prova auditável em
JSON canônico (Passo 7.5). A representação PDF é um derivado autocontido visual,
que empacota o resumo executivo, tabela de fatos/regras/decisão, QR Code com a
impressão digital do VerificationBundle e selo criptográfico opcional.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from packages.core_domain.crypto import CryptographicSignature
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


@dataclass(frozen=True, slots=True)
class DossierPdfRepresentation:
    dossier_id: TypedId
    organization_id: OrganizationId
    pdf_bytes: bytes
    pdf_hash: str
    generated_at: datetime
    verification_qr_payload: str
    layout_version: str = "1.0"
    signature: CryptographicSignature | None = None

    def __post_init__(self) -> None:
        if self.dossier_id.entity_type != "dossier":
            raise ValueError("dossier_id deve ser do tipo 'dossier'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.pdf_bytes, bytes) or not self.pdf_bytes:
            raise ValueError("pdf_bytes não pode ser vazio.")
        if not isinstance(self.pdf_hash, str) or not self.pdf_hash.strip():
            raise ValueError("pdf_hash deve ser uma string não vazia.")
        if (
            not isinstance(self.verification_qr_payload, str)
            or not self.verification_qr_payload.strip()
        ):
            raise ValueError("verification_qr_payload deve ser uma string não vazia.")

        computed = hashlib.sha256(self.pdf_bytes).hexdigest()
        if self.pdf_hash != computed:
            raise ValueError(
                f"pdf_hash informado ({self.pdf_hash}) não confere "
                f"com o hash calculado dos bytes ({computed})."
            )

        require_utc(self.generated_at, field_name="generated_at")

    def verify_integrity(self) -> bool:
        """Verifica se os bytes do PDF conferem com o hash SHA-256."""
        return hashlib.sha256(self.pdf_bytes).hexdigest() == self.pdf_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "dossier_id": str(self.dossier_id.value),
            "organization_id": str(self.organization_id.value),
            "pdf_hash": self.pdf_hash,
            "generated_at": self.generated_at.isoformat(),
            "layout_version": self.layout_version,
            "verification_qr_payload": self.verification_qr_payload,
            "byte_count": len(self.pdf_bytes),
            "is_signed": self.signature is not None,
            "signature": {
                "signature_id": str(self.signature.signature_id.value),
                "profile": self.signature.profile.value,
                "algorithm": self.signature.algorithm,
                "key_id": str(self.signature.key_identifier.key_id.value),
                "signed_at": self.signature.signed_at.isoformat(),
            }
            if self.signature
            else None,
        }
