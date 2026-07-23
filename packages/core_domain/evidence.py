"""Modelo canônico de Evidência (Evidence) e Fonte de Origem (Source) (ADR-0038/Passo 5.1)."""

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.core_domain.crypto import CryptographicSignature
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class SourceType(StrEnum):
    DOCUMENT = "DOCUMENT"
    MANUAL_ENTRY = "MANUAL_ENTRY"
    IOT_SENSOR = "IOT_SENSOR"
    EXTERNAL_API = "EXTERNAL_API"
    SYSTEM_LOG = "SYSTEM_LOG"


class ConfidenceTier(StrEnum):
    INFORMED = "INFORMED"
    DOCUMENTED = "DOCUMENTED"
    VERIFIED_SOURCE = "VERIFIED_SOURCE"
    HARDENED_SYSTEM = "HARDENED_SYSTEM"
    CRYPTOGRAPHICALLY_ATTESTED = "CRYPTOGRAPHICALLY_ATTESTED"


@dataclass(frozen=True, slots=True)
class ConfidenceLevel:
    tier: ConfidenceTier
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.tier, ConfidenceTier):
            raise TypeError("tier deve ser um ConfidenceTier válido.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason de ConfidenceLevel deve ser uma string não vazia.")


@dataclass(frozen=True, slots=True)
class ValidityPeriod:
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("valid_from não pode ser posterior a valid_until.")

    def is_valid_at(self, at: datetime) -> bool:
        if self.valid_from and at < self.valid_from:
            return False
        if self.valid_until and at > self.valid_until:
            return False
        return True


class VerificationOutcome(StrEnum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True, slots=True)
class VerificationRecord:
    verification_id: TypedId
    verified_at: datetime
    verifier_reference: UniversalReference
    outcome: VerificationOutcome
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.verification_id.entity_type != "verification":
            raise ValueError("verification_id deve ser do tipo 'verification'.")
        if not isinstance(self.verifier_reference, UniversalReference):
            raise TypeError("verifier_reference deve ser UniversalReference.")
        if not isinstance(self.outcome, VerificationOutcome):
            raise TypeError("outcome deve ser um VerificationOutcome válido.")


@dataclass(frozen=True, slots=True)
class EvidenceRevocation:
    revoked_at: datetime
    revoking_actor: UniversalReference
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.revoking_actor, UniversalReference):
            raise TypeError("revoking_actor deve ser UniversalReference.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason da revogação deve ser uma string não vazia.")


@dataclass(frozen=True, slots=True)
class Source:
    source_id: TypedId
    source_type: SourceType
    identifier_uri: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source_id.entity_type != "source":
            raise ValueError("source_id deve ser do tipo 'source'.")
        if not isinstance(self.source_type, SourceType):
            raise TypeError("source_type deve ser um SourceType válido.")


def compute_content_hash(content: bytes) -> bytes:
    if not isinstance(content, bytes):
        raise TypeError("O conteúdo para cálculo de hash deve ser do tipo bytes.")
    return hashlib.sha256(content).digest()


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: TypedId
    organization_id: OrganizationId
    source: Source
    author_reference: UniversalReference
    content_hash: bytes
    registered_at: datetime
    confidence_level: ConfidenceLevel
    validity_period: ValidityPeriod | None = None
    verifications: tuple[VerificationRecord, ...] = ()
    revocation: EvidenceRevocation | None = None
    signature: CryptographicSignature | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if self.evidence_id.entity_type != "evidence":
            raise ValueError("evidence_id deve ser do tipo 'evidence'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.source, Source):
            raise TypeError("source deve ser uma instância válida de Source.")
        if not isinstance(self.author_reference, UniversalReference):
            raise TypeError("author_reference deve ser UniversalReference.")
        if not isinstance(self.content_hash, bytes) or len(self.content_hash) != 32:
            raise ValueError("content_hash deve ser um hash SHA-256 de 32 bytes.")
        if not isinstance(self.confidence_level, ConfidenceLevel):
            raise TypeError("confidence_level deve ser uma instância de ConfidenceLevel.")
        if self.validity_period is not None and not isinstance(
            self.validity_period, ValidityPeriod
        ):
            raise TypeError("validity_period deve ser uma instância de ValidityPeriod.")
        if self.revocation is not None and not isinstance(self.revocation, EvidenceRevocation):
            raise TypeError("revocation deve ser uma instância de EvidenceRevocation.")
        if self.signature is not None and not isinstance(self.signature, CryptographicSignature):
            raise TypeError("signature deve ser uma instância de CryptographicSignature.")
        if self.version < 1:
            raise ValueError("A versão da evidência deve ser >= 1.")

    @property
    def is_revoked(self) -> bool:
        return self.revocation is not None

    def is_valid_at(self, at: datetime) -> bool:
        if self.is_revoked:
            return False
        if self.validity_period is not None:
            return self.validity_period.is_valid_at(at)
        return True

    def add_verification(self, verification: VerificationRecord) -> "Evidence":
        if self.is_revoked:
            raise ValueError("Não é possível adicionar verificação a uma evidência revogada.")
        return Evidence(
            evidence_id=self.evidence_id,
            organization_id=self.organization_id,
            source=self.source,
            author_reference=self.author_reference,
            content_hash=self.content_hash,
            registered_at=self.registered_at,
            confidence_level=self.confidence_level,
            validity_period=self.validity_period,
            verifications=(*self.verifications, verification),
            revocation=self.revocation,
            signature=self.signature,
            version=self.version + 1,
        )

    def sign_evidence(self, signature: CryptographicSignature) -> "Evidence":
        if self.is_revoked:
            raise ValueError("Não é possível assinar uma evidência revogada.")
        return Evidence(
            evidence_id=self.evidence_id,
            organization_id=self.organization_id,
            source=self.source,
            author_reference=self.author_reference,
            content_hash=self.content_hash,
            registered_at=self.registered_at,
            confidence_level=self.confidence_level,
            validity_period=self.validity_period,
            verifications=self.verifications,
            revocation=self.revocation,
            signature=signature,
            version=self.version + 1,
        )

    def revoke(self, revocation: EvidenceRevocation) -> "Evidence":
        if self.is_revoked:
            raise ValueError("Evidência já foi revogada anteriormente.")
        return Evidence(
            evidence_id=self.evidence_id,
            organization_id=self.organization_id,
            source=self.source,
            author_reference=self.author_reference,
            content_hash=self.content_hash,
            registered_at=self.registered_at,
            confidence_level=self.confidence_level,
            validity_period=self.validity_period,
            verifications=self.verifications,
            revocation=revocation,
            signature=self.signature,
            version=self.version + 1,
        )

    @classmethod
    def create(
        cls,
        organization_id: OrganizationId,
        source: Source,
        author_reference: UniversalReference,
        content: bytes,
        confidence_level: ConfidenceLevel,
        validity_period: ValidityPeriod | None = None,
    ) -> "Evidence":
        return cls(
            evidence_id=TypedId.new("evidence"),
            organization_id=organization_id,
            source=source,
            author_reference=author_reference,
            content_hash=compute_content_hash(content),
            registered_at=datetime.now(UTC),
            confidence_level=confidence_level,
            validity_period=validity_period,
            verifications=(),
            revocation=None,
            version=1,
        )


@dataclass(frozen=True, slots=True)
class Attachment:
    attachment_id: TypedId
    organization_id: OrganizationId
    filename: str
    content_type: str
    size_bytes: int
    content_hash: bytes
    blob_uri: str
    uploaded_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        if self.attachment_id.entity_type != "attachment":
            raise ValueError("attachment_id deve ser do tipo 'attachment'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.filename, str) or not self.filename.strip():
            raise ValueError("filename de Attachment deve ser uma string não vazia.")
        if not isinstance(self.content_type, str) or not self.content_type.strip():
            raise ValueError("content_type de Attachment deve ser uma string não vazia.")
        if not isinstance(self.size_bytes, int) or self.size_bytes <= 0:
            raise ValueError("size_bytes deve ser um inteiro positivo > 0.")
        if not isinstance(self.content_hash, bytes) or len(self.content_hash) != 32:
            raise ValueError("content_hash deve ser um hash SHA-256 de 32 bytes.")
        if not isinstance(self.blob_uri, str) or not self.blob_uri.strip():
            raise ValueError("blob_uri deve ser uma string não vazia.")
        if self.version < 1:
            raise ValueError("A versão do Attachment deve ser >= 1.")
