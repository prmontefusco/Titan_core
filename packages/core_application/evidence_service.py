"""Caso de uso e porta do serviço de Evidências (ADR-0038/Passo 5.6)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.core_application.crypto import KeyRegistryPort, SigningProviderPort
from packages.core_domain.crypto import CryptographicProfile
from packages.core_domain.evidence import (
    ConfidenceLevel,
    Evidence,
    EvidenceRevocation,
    Source,
    ValidityPeriod,
    VerificationOutcome,
    VerificationRecord,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class EvidenceRepositoryPort(Protocol):
    def save(self, evidence: Evidence) -> None: ...

    def update(self, evidence: Evidence) -> None: ...

    def get_by_id(self, evidence_id: TypedId) -> Evidence | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Evidence]: ...


@dataclass(frozen=True, slots=True)
class EvidenceService:
    repository: EvidenceRepositoryPort
    signing_provider: SigningProviderPort | None = None
    key_registry: KeyRegistryPort | None = None

    def register_evidence(
        self,
        organization_id: OrganizationId,
        source: Source,
        author_reference: UniversalReference,
        content: bytes,
        confidence_level: ConfidenceLevel,
        validity_period: ValidityPeriod | None = None,
    ) -> Evidence:
        evidence = Evidence.create(
            organization_id=organization_id,
            source=source,
            author_reference=author_reference,
            content=content,
            confidence_level=confidence_level,
            validity_period=validity_period,
        )
        self.repository.save(evidence)
        return evidence

    def verify_evidence(
        self,
        evidence_id: TypedId,
        verifier_reference: UniversalReference,
        outcome: VerificationOutcome,
        notes: str | None = None,
    ) -> Evidence:
        evidence = self.get_evidence(evidence_id)
        if evidence is None:
            raise KeyError(f"Evidência {evidence_id.value} não encontrada.")

        verification = VerificationRecord(
            verification_id=TypedId.new("verification"),
            verified_at=datetime.now(UTC),
            verifier_reference=verifier_reference,
            outcome=outcome,
            notes=notes,
        )

        updated_evidence = evidence.add_verification(verification)
        self.repository.update(updated_evidence)
        return updated_evidence

    def sign_evidence(
        self,
        evidence_id: TypedId,
        profile: CryptographicProfile,
        key_purpose: str = "Integridade e Assinatura de Evidências",
    ) -> Evidence:
        if self.signing_provider is None or self.key_registry is None:
            raise RuntimeError("Provedor de assinatura ou registro de chaves não configurado.")

        evidence = self.get_evidence(evidence_id)
        if evidence is None:
            raise KeyError(f"Evidência {evidence_id.value} não encontrada.")

        active_key = self.key_registry.get_active_key(
            organization_id=evidence.organization_id,
            purpose=key_purpose,
        )
        if active_key is None:
            raise KeyError(
                f"Nenhuma chave ativa com finalidade '{key_purpose}' encontrada para a "
                f"organização {evidence.organization_id.value}."
            )

        signature = self.signing_provider.sign(
            content_hash=evidence.content_hash,
            key_identifier=active_key.key_identifier,
            profile=profile,
        )

        signed_evidence = evidence.sign_evidence(signature)
        self.repository.update(signed_evidence)
        return signed_evidence

    def revoke_evidence(
        self,
        evidence_id: TypedId,
        revoking_actor: UniversalReference,
        reason: str,
    ) -> Evidence:
        evidence = self.get_evidence(evidence_id)
        if evidence is None:
            raise KeyError(f"Evidência {evidence_id.value} não encontrada.")

        revocation = EvidenceRevocation(
            revoked_at=datetime.now(UTC),
            revoking_actor=revoking_actor,
            reason=reason,
        )

        updated_evidence = evidence.revoke(revocation)
        self.repository.update(updated_evidence)
        return updated_evidence

    def get_evidence(self, evidence_id: TypedId) -> Evidence | None:
        return self.repository.get_by_id(evidence_id)

    def list_evidences(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Evidence]:
        return self.repository.list_by_organization(
            organization_id=organization_id, limit=limit, offset=offset
        )
