"""Testes unitários do domínio Evidence, Validity, Revocation e Signature (Passo 5.6)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_domain.crypto import (
    CryptographicProfile,
    CryptographicSignature,
    KeyIdentifier,
)
from packages.core_domain.evidence import (
    Attachment,
    ConfidenceLevel,
    ConfidenceTier,
    Evidence,
    EvidenceRevocation,
    Source,
    SourceType,
    ValidityPeriod,
    VerificationOutcome,
    VerificationRecord,
    compute_content_hash,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def test_validity_period_bounds_and_validity_check() -> None:
    now = datetime.now(UTC)
    start = now - timedelta(days=1)
    end = now + timedelta(days=1)

    vp = ValidityPeriod(valid_from=start, valid_until=end)
    assert vp.is_valid_at(now) is True
    assert vp.is_valid_at(start - timedelta(hours=1)) is False
    assert vp.is_valid_at(end + timedelta(hours=1)) is False

    with pytest.raises(ValueError, match="valid_from não pode ser posterior a valid_until"):
        ValidityPeriod(valid_from=end, valid_until=start)


def test_evidence_verification_flow() -> None:
    org_id = OrganizationId.new()
    source = Source(source_id=TypedId.new("source"), source_type=SourceType.DOCUMENT)
    author_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )
    cl = ConfidenceLevel(tier=ConfidenceTier.DOCUMENTED, reason="Documento anexado")
    evidence = Evidence.create(
        organization_id=org_id,
        source=source,
        author_reference=author_ref,
        content=b"Licenca sanitaria v1",
        confidence_level=cl,
    )

    verifier_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )
    v_record = VerificationRecord(
        verification_id=TypedId.new("verification"),
        verified_at=datetime.now(UTC),
        verifier_reference=verifier_ref,
        outcome=VerificationOutcome.VERIFIED,
        notes="Auditado e verificado",
    )

    updated = evidence.add_verification(v_record)
    assert len(updated.verifications) == 1
    assert updated.verifications[0] == v_record
    assert updated.version == 2


def test_evidence_revocation_flow() -> None:
    org_id = OrganizationId.new()
    source = Source(source_id=TypedId.new("source"), source_type=SourceType.MANUAL_ENTRY)
    author_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )
    cl = ConfidenceLevel(tier=ConfidenceTier.INFORMED, reason="Declarado")
    evidence = Evidence.create(
        organization_id=org_id,
        source=source,
        author_reference=author_ref,
        content=b"Dados incorretos",
        confidence_level=cl,
    )

    rev_actor = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )
    revocation = EvidenceRevocation(
        revoked_at=datetime.now(UTC),
        revoking_actor=rev_actor,
        reason="Erro na declaracao manual de origem",
    )

    revoked_evidence = evidence.revoke(revocation)
    assert revoked_evidence.is_revoked is True
    assert revoked_evidence.is_valid_at(datetime.now(UTC)) is False
    assert revoked_evidence.revocation == revocation
    assert revoked_evidence.version == 2

    # Tentar revogar novamente deve falhar
    with pytest.raises(ValueError, match="Evidência já foi revogada anteriormente"):
        revoked_evidence.revoke(revocation)

    # Tentar adicionar verificação a evidência revogada deve falhar
    v_record = VerificationRecord(
        verification_id=TypedId.new("verification"),
        verified_at=datetime.now(UTC),
        verifier_reference=rev_actor,
        outcome=VerificationOutcome.REJECTED,
    )
    with pytest.raises(ValueError, match="Não é possível adicionar verificação"):
        revoked_evidence.add_verification(v_record)


def test_evidence_signing_flow() -> None:
    org_id = OrganizationId.new()
    source = Source(source_id=TypedId.new("source"), source_type=SourceType.DOCUMENT)
    author_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )
    cl = ConfidenceLevel(tier=ConfidenceTier.VERIFIED_SOURCE, reason="Fonte confiável")
    evidence = Evidence.create(
        organization_id=org_id,
        source=source,
        author_reference=author_ref,
        content=b"snapshot de evidencias de auditoria",
        confidence_level=cl,
    )

    ki = KeyIdentifier(key_id=TypedId.new("key"), purpose="Assinatura de Evidências")
    sig = CryptographicSignature(
        signature_id=TypedId.new("signature"),
        profile=CryptographicProfile.INSTITUTIONAL_SIGNATURE,
        algorithm="HMAC-SHA256",
        raw_signature=b"raw_signature_bytes_12345",
        key_identifier=ki,
        signed_at=datetime.now(UTC),
    )

    signed_ev = evidence.sign_evidence(sig)
    assert signed_ev.signature == sig
    assert signed_ev.version == 2


def test_attachment_invariants() -> None:
    org_id = OrganizationId.new()
    content = b"Conteudo do laudo tecnico PDF"
    att = Attachment(
        attachment_id=TypedId.new("attachment"),
        organization_id=org_id,
        filename="laudo_sanitario.pdf",
        content_type="application/pdf",
        size_bytes=len(content),
        content_hash=compute_content_hash(content),
        blob_uri="blob://attachments/laudo_sanitario.pdf",
        uploaded_at=datetime.now(UTC),
    )

    assert att.filename == "laudo_sanitario.pdf"
    assert att.content_type == "application/pdf"
    assert att.size_bytes == len(content)

    with pytest.raises(ValueError, match="size_bytes deve ser um inteiro positivo > 0"):
        Attachment(
            attachment_id=TypedId.new("attachment"),
            organization_id=org_id,
            filename="invalid.pdf",
            content_type="application/pdf",
            size_bytes=0,
            content_hash=compute_content_hash(content),
            blob_uri="blob://attachments/invalid.pdf",
            uploaded_at=datetime.now(UTC),
        )
