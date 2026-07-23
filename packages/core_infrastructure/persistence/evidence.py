"""Persistência de Evidence, Validity, Revocation e Signature sob RLS (ADR-0038/Passo 5.6)."""

import json
from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Connection

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
)
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

CORE_AUDIT_SCHEMA = "core_audit"

evidences_table = Table(
    "evidences",
    organization_metadata,
    Column("evidence_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("source_id", PG_UUID(as_uuid=True), nullable=False),
    Column("source_type", String(50), nullable=False),
    Column("source_uri", String(255), nullable=True),
    Column("source_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("author_id", PG_UUID(as_uuid=True), nullable=False),
    Column("author_org_id", PG_UUID(as_uuid=True), nullable=False),
    Column("author_contract_version", Integer, nullable=False, server_default="1"),
    Column("content_hash", LargeBinary, nullable=False),
    Column("registered_at", DateTime(timezone=True), nullable=False),
    Column("confidence_tier", String(50), nullable=False),
    Column("confidence_reason", Text, nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=True),
    Column("valid_until", DateTime(timezone=True), nullable=True),
    Column("is_revoked", Boolean, nullable=False, server_default=text("false")),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    Column("revoking_actor_id", PG_UUID(as_uuid=True), nullable=True),
    Column("revoking_actor_org_id", PG_UUID(as_uuid=True), nullable=True),
    Column("revoking_actor_contract_version", Integer, nullable=True),
    Column("revocation_reason", Text, nullable=True),
    Column("signature_id", PG_UUID(as_uuid=True), nullable=True),
    Column("signature_profile", String(50), nullable=True),
    Column("signature_algorithm", String(50), nullable=True),
    Column("signature_raw_bytes", LargeBinary, nullable=True),
    Column("signature_key_id", PG_UUID(as_uuid=True), nullable=True),
    Column("signature_key_purpose", String(100), nullable=True),
    Column("signature_signed_at", DateTime(timezone=True), nullable=True),
    Column("version", Integer, nullable=False, server_default="1"),
    CheckConstraint("version >= 1", name="ck_evidences_version"),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_evidences_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

evidence_verifications_table = Table(
    "evidence_verifications",
    organization_metadata,
    Column("verification_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("evidence_id", PG_UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("verified_at", DateTime(timezone=True), nullable=False),
    Column("verifier_id", PG_UUID(as_uuid=True), nullable=False),
    Column("verifier_org_id", PG_UUID(as_uuid=True), nullable=False),
    Column("verifier_contract_version", Integer, nullable=False, server_default="1"),
    Column("outcome", String(50), nullable=False),
    Column("notes", Text, nullable=True),
    ForeignKeyConstraint(
        ["evidence_id"],
        ["core_audit.evidences.evidence_id"],
        name="fk_evidence_verifications_evidence",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_evidence_verifications_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TransactionalEvidenceRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalEvidenceRepository exige transacao ativa.")

    def save(self, evidence: Evidence) -> None:
        valid_from = evidence.validity_period.valid_from if evidence.validity_period else None
        valid_until = evidence.validity_period.valid_until if evidence.validity_period else None

        is_revoked = evidence.is_revoked
        revoked_at = evidence.revocation.revoked_at if evidence.revocation else None
        revoking_actor_id = (
            evidence.revocation.revoking_actor.target_id.value if evidence.revocation else None
        )
        revoking_actor_org_id = (
            evidence.revocation.revoking_actor.organization_id.value
            if evidence.revocation and evidence.revocation.revoking_actor.organization_id
            else (evidence.organization_id.value if evidence.revocation else None)
        )
        revoking_actor_contract_version = (
            evidence.revocation.revoking_actor.contract_version if evidence.revocation else None
        )
        revocation_reason = evidence.revocation.reason if evidence.revocation else None

        sig_id = evidence.signature.signature_id.value if evidence.signature else None
        sig_profile = evidence.signature.profile.value if evidence.signature else None
        sig_alg = evidence.signature.algorithm if evidence.signature else None
        sig_bytes = evidence.signature.raw_signature if evidence.signature else None
        sig_key_id = evidence.signature.key_identifier.key_id.value if evidence.signature else None
        sig_key_purpose = evidence.signature.key_identifier.purpose if evidence.signature else None
        sig_signed_at = evidence.signature.signed_at if evidence.signature else None

        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.evidences (
                    evidence_id,
                    record_owner_organization_id,
                    source_id,
                    source_type,
                    source_uri,
                    source_metadata,
                    author_id,
                    author_org_id,
                    author_contract_version,
                    content_hash,
                    registered_at,
                    confidence_tier,
                    confidence_reason,
                    valid_from,
                    valid_until,
                    is_revoked,
                    revoked_at,
                    revoking_actor_id,
                    revoking_actor_org_id,
                    revoking_actor_contract_version,
                    revocation_reason,
                    signature_id,
                    signature_profile,
                    signature_algorithm,
                    signature_raw_bytes,
                    signature_key_id,
                    signature_key_purpose,
                    signature_signed_at,
                    version
                ) VALUES (
                    :evidence_id,
                    :org_id,
                    :source_id,
                    :source_type,
                    :source_uri,
                    :source_metadata,
                    :author_id,
                    :author_org_id,
                    :author_contract_version,
                    :content_hash,
                    :registered_at,
                    :confidence_tier,
                    :confidence_reason,
                    :valid_from,
                    :valid_until,
                    :is_revoked,
                    :revoked_at,
                    :revoking_actor_id,
                    :revoking_actor_org_id,
                    :revoking_actor_contract_version,
                    :revocation_reason,
                    :signature_id,
                    :signature_profile,
                    :signature_algorithm,
                    :signature_raw_bytes,
                    :signature_key_id,
                    :signature_key_purpose,
                    :signature_signed_at,
                    :version
                )
                """
            ),
            {
                "evidence_id": evidence.evidence_id.value,
                "org_id": evidence.organization_id.value,
                "source_id": evidence.source.source_id.value,
                "source_type": evidence.source.source_type.value,
                "source_uri": evidence.source.identifier_uri,
                "source_metadata": json.dumps(evidence.source.metadata),
                "author_id": evidence.author_reference.target_id.value,
                "author_org_id": (
                    evidence.author_reference.organization_id.value
                    if evidence.author_reference.organization_id
                    else evidence.organization_id.value
                ),
                "author_contract_version": evidence.author_reference.contract_version,
                "content_hash": evidence.content_hash,
                "registered_at": evidence.registered_at,
                "confidence_tier": evidence.confidence_level.tier.value,
                "confidence_reason": evidence.confidence_level.reason,
                "valid_from": valid_from,
                "valid_until": valid_until,
                "is_revoked": is_revoked,
                "revoked_at": revoked_at,
                "revoking_actor_id": revoking_actor_id,
                "revoking_actor_org_id": revoking_actor_org_id,
                "revoking_actor_contract_version": revoking_actor_contract_version,
                "revocation_reason": revocation_reason,
                "signature_id": sig_id,
                "signature_profile": sig_profile,
                "signature_algorithm": sig_alg,
                "signature_raw_bytes": sig_bytes,
                "signature_key_id": sig_key_id,
                "signature_key_purpose": sig_key_purpose,
                "signature_signed_at": sig_signed_at,
                "version": evidence.version,
            },
        )

        self._save_verifications(evidence)

    def update(self, evidence: Evidence) -> None:
        valid_from = evidence.validity_period.valid_from if evidence.validity_period else None
        valid_until = evidence.validity_period.valid_until if evidence.validity_period else None

        is_revoked = evidence.is_revoked
        revoked_at = evidence.revocation.revoked_at if evidence.revocation else None
        revoking_actor_id = (
            evidence.revocation.revoking_actor.target_id.value if evidence.revocation else None
        )
        revoking_actor_org_id = (
            evidence.revocation.revoking_actor.organization_id.value
            if evidence.revocation and evidence.revocation.revoking_actor.organization_id
            else (evidence.organization_id.value if evidence.revocation else None)
        )
        revoking_actor_contract_version = (
            evidence.revocation.revoking_actor.contract_version if evidence.revocation else None
        )
        revocation_reason = evidence.revocation.reason if evidence.revocation else None

        sig_id = evidence.signature.signature_id.value if evidence.signature else None
        sig_profile = evidence.signature.profile.value if evidence.signature else None
        sig_alg = evidence.signature.algorithm if evidence.signature else None
        sig_bytes = evidence.signature.raw_signature if evidence.signature else None
        sig_key_id = evidence.signature.key_identifier.key_id.value if evidence.signature else None
        sig_key_purpose = evidence.signature.key_identifier.purpose if evidence.signature else None
        sig_signed_at = evidence.signature.signed_at if evidence.signature else None

        self.connection.execute(
            text(
                """
                UPDATE core_audit.evidences
                SET
                    valid_from = :valid_from,
                    valid_until = :valid_until,
                    is_revoked = :is_revoked,
                    revoked_at = :revoked_at,
                    revoking_actor_id = :revoking_actor_id,
                    revoking_actor_org_id = :revoking_actor_org_id,
                    revoking_actor_contract_version = :revoking_actor_contract_version,
                    revocation_reason = :revocation_reason,
                    signature_id = :signature_id,
                    signature_profile = :signature_profile,
                    signature_algorithm = :signature_algorithm,
                    signature_raw_bytes = :signature_raw_bytes,
                    signature_key_id = :signature_key_id,
                    signature_key_purpose = :signature_key_purpose,
                    signature_signed_at = :signature_signed_at,
                    version = :version
                WHERE evidence_id = :evidence_id
                """
            ),
            {
                "evidence_id": evidence.evidence_id.value,
                "valid_from": valid_from,
                "valid_until": valid_until,
                "is_revoked": is_revoked,
                "revoked_at": revoked_at,
                "revoking_actor_id": revoking_actor_id,
                "revoking_actor_org_id": revoking_actor_org_id,
                "revoking_actor_contract_version": revoking_actor_contract_version,
                "revocation_reason": revocation_reason,
                "signature_id": sig_id,
                "signature_profile": sig_profile,
                "signature_algorithm": sig_alg,
                "signature_raw_bytes": sig_bytes,
                "signature_key_id": sig_key_id,
                "signature_key_purpose": sig_key_purpose,
                "signature_signed_at": sig_signed_at,
                "version": evidence.version,
            },
        )

        self._save_verifications(evidence)

    def _save_verifications(self, evidence: Evidence) -> None:
        for v in evidence.verifications:
            self.connection.execute(
                text(
                    """
                    INSERT INTO core_audit.evidence_verifications (
                        verification_id,
                        evidence_id,
                        record_owner_organization_id,
                        verified_at,
                        verifier_id,
                        verifier_org_id,
                        verifier_contract_version,
                        outcome,
                        notes
                    ) VALUES (
                        :verification_id,
                        :evidence_id,
                        :org_id,
                        :verified_at,
                        :verifier_id,
                        :verifier_org_id,
                        :verifier_contract_version,
                        :outcome,
                        :notes
                    )
                    ON CONFLICT (verification_id) DO NOTHING
                    """
                ),
                {
                    "verification_id": v.verification_id.value,
                    "evidence_id": evidence.evidence_id.value,
                    "org_id": evidence.organization_id.value,
                    "verified_at": v.verified_at,
                    "verifier_id": v.verifier_reference.target_id.value,
                    "verifier_org_id": (
                        v.verifier_reference.organization_id.value
                        if v.verifier_reference.organization_id
                        else evidence.organization_id.value
                    ),
                    "verifier_contract_version": v.verifier_reference.contract_version,
                    "outcome": v.outcome.value,
                    "notes": v.notes,
                },
            )

    def get_by_id(self, evidence_id: TypedId) -> Evidence | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    evidence_id,
                    record_owner_organization_id,
                    source_id,
                    source_type,
                    source_uri,
                    source_metadata,
                    author_id,
                    author_org_id,
                    author_contract_version,
                    content_hash,
                    registered_at,
                    confidence_tier,
                    confidence_reason,
                    valid_from,
                    valid_until,
                    is_revoked,
                    revoked_at,
                    revoking_actor_id,
                    revoking_actor_org_id,
                    revoking_actor_contract_version,
                    revocation_reason,
                    signature_id,
                    signature_profile,
                    signature_algorithm,
                    signature_raw_bytes,
                    signature_key_id,
                    signature_key_purpose,
                    signature_signed_at,
                    version
                FROM core_audit.evidences
                WHERE evidence_id = :evidence_id
                """
            ),
            {"evidence_id": evidence_id.value},
        ).first()

        if row is None:
            return None

        verifications = self._load_verifications(evidence_id.value)
        return self._map_row_to_evidence(row, verifications)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Evidence]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    evidence_id,
                    record_owner_organization_id,
                    source_id,
                    source_type,
                    source_uri,
                    source_metadata,
                    author_id,
                    author_org_id,
                    author_contract_version,
                    content_hash,
                    registered_at,
                    confidence_tier,
                    confidence_reason,
                    valid_from,
                    valid_until,
                    is_revoked,
                    revoked_at,
                    revoking_actor_id,
                    revoking_actor_org_id,
                    revoking_actor_contract_version,
                    revocation_reason,
                    signature_id,
                    signature_profile,
                    signature_algorithm,
                    signature_raw_bytes,
                    signature_key_id,
                    signature_key_purpose,
                    signature_signed_at,
                    version
                FROM core_audit.evidences
                WHERE record_owner_organization_id = :org_id
                ORDER BY registered_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"org_id": organization_id.value, "limit": limit, "offset": offset},
        ).fetchall()

        evidences: list[Evidence] = []
        for row in rows:
            verifications = self._load_verifications(row.evidence_id)
            evidences.append(self._map_row_to_evidence(row, verifications))
        return evidences

    def list_by_source(self, source_id: TypedId) -> list[Evidence]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    evidence_id,
                    record_owner_organization_id,
                    source_id,
                    source_type,
                    source_uri,
                    source_metadata,
                    author_id,
                    author_org_id,
                    author_contract_version,
                    content_hash,
                    registered_at,
                    confidence_tier,
                    confidence_reason,
                    valid_from,
                    valid_until,
                    is_revoked,
                    revoked_at,
                    revoking_actor_id,
                    revoking_actor_org_id,
                    revoking_actor_contract_version,
                    revocation_reason,
                    signature_id,
                    signature_profile,
                    signature_algorithm,
                    signature_raw_bytes,
                    signature_key_id,
                    signature_key_purpose,
                    signature_signed_at,
                    version
                FROM core_audit.evidences
                WHERE source_id = :source_id
                ORDER BY registered_at DESC
                """
            ),
            {"source_id": source_id.value},
        ).fetchall()

        evidences: list[Evidence] = []
        for row in rows:
            verifications = self._load_verifications(row.evidence_id)
            evidences.append(self._map_row_to_evidence(row, verifications))
        return evidences

    def _load_verifications(self, evidence_id_val: object) -> tuple[VerificationRecord, ...]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    verification_id,
                    verified_at,
                    verifier_id,
                    verifier_org_id,
                    verifier_contract_version,
                    outcome,
                    notes
                FROM core_audit.evidence_verifications
                WHERE evidence_id = :evidence_id
                ORDER BY verified_at ASC
                """
            ),
            {"evidence_id": evidence_id_val},
        ).fetchall()

        verifications: list[VerificationRecord] = []
        for r in rows:
            v_at = (
                r.verified_at.replace(tzinfo=UTC) if r.verified_at.tzinfo is None else r.verified_at
            )
            v_ref = UniversalReference(
                target_id=TypedId(entity_type="user", value=r.verifier_id),
                organization_id=OrganizationId(r.verifier_org_id),
                contract_version=r.verifier_contract_version,
            )
            verifications.append(
                VerificationRecord(
                    verification_id=TypedId(entity_type="verification", value=r.verification_id),
                    verified_at=v_at,
                    verifier_reference=v_ref,
                    outcome=VerificationOutcome(r.outcome),
                    notes=r.notes,
                )
            )
        return tuple(verifications)

    def _map_row_to_evidence(
        self, row: object, verifications: tuple[VerificationRecord, ...]
    ) -> Evidence:
        reg_at = (
            row.registered_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
            if row.registered_at.tzinfo is None  # type: ignore[attr-defined]
            else row.registered_at  # type: ignore[attr-defined]
        )

        source = Source(
            source_id=TypedId(entity_type="source", value=row.source_id),  # type: ignore[attr-defined]
            source_type=SourceType(row.source_type),  # type: ignore[attr-defined]
            identifier_uri=row.source_uri,  # type: ignore[attr-defined]
            metadata=dict(row.source_metadata) if row.source_metadata else {},  # type: ignore[attr-defined]
        )

        author_ref = UniversalReference(
            target_id=TypedId(entity_type="user", value=row.author_id),  # type: ignore[attr-defined]
            organization_id=OrganizationId(row.author_org_id),  # type: ignore[attr-defined]
            contract_version=row.author_contract_version,  # type: ignore[attr-defined]
        )

        confidence_level = ConfidenceLevel(
            tier=ConfidenceTier(row.confidence_tier),  # type: ignore[attr-defined]
            reason=row.confidence_reason,  # type: ignore[attr-defined]
        )

        valid_from = (
            row.valid_from.replace(tzinfo=UTC)  # type: ignore[attr-defined]
            if row.valid_from and row.valid_from.tzinfo is None  # type: ignore[attr-defined]
            else row.valid_from  # type: ignore[attr-defined]
        )
        valid_until = (
            row.valid_until.replace(tzinfo=UTC)  # type: ignore[attr-defined]
            if row.valid_until and row.valid_until.tzinfo is None  # type: ignore[attr-defined]
            else row.valid_until  # type: ignore[attr-defined]
        )
        validity_period = (
            ValidityPeriod(valid_from=valid_from, valid_until=valid_until)
            if (valid_from or valid_until)
            else None
        )

        revocation = None
        if row.is_revoked:  # type: ignore[attr-defined]
            rev_at = (
                row.revoked_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
                if row.revoked_at and row.revoked_at.tzinfo is None  # type: ignore[attr-defined]
                else row.revoked_at  # type: ignore[attr-defined]
            )
            rev_actor = UniversalReference(
                target_id=TypedId(entity_type="user", value=row.revoking_actor_id),  # type: ignore[attr-defined]
                organization_id=OrganizationId(row.revoking_actor_org_id),  # type: ignore[attr-defined]
                contract_version=row.revoking_actor_contract_version,  # type: ignore[attr-defined]
            )
            revocation = EvidenceRevocation(
                revoked_at=rev_at,
                revoking_actor=rev_actor,
                reason=row.revocation_reason,  # type: ignore[attr-defined]
            )

        signature = None
        if row.signature_id is not None:  # type: ignore[attr-defined]
            sig_signed_at = (
                row.signature_signed_at.replace(tzinfo=UTC)  # type: ignore[attr-defined]
                if row.signature_signed_at and row.signature_signed_at.tzinfo is None  # type: ignore[attr-defined]
                else row.signature_signed_at  # type: ignore[attr-defined]
            )
            key_identifier = KeyIdentifier(
                key_id=TypedId(entity_type="key", value=row.signature_key_id),  # type: ignore[attr-defined]
                purpose=row.signature_key_purpose,  # type: ignore[attr-defined]
            )
            signature = CryptographicSignature(
                signature_id=TypedId(entity_type="signature", value=row.signature_id),  # type: ignore[attr-defined]
                profile=CryptographicProfile(row.signature_profile),  # type: ignore[attr-defined]
                algorithm=row.signature_algorithm,  # type: ignore[attr-defined]
                raw_signature=bytes(row.signature_raw_bytes),  # type: ignore[attr-defined]
                key_identifier=key_identifier,
                signed_at=sig_signed_at,
            )

        return Evidence(
            evidence_id=TypedId(entity_type="evidence", value=row.evidence_id),  # type: ignore[attr-defined]
            organization_id=OrganizationId(row.record_owner_organization_id),  # type: ignore[attr-defined]
            source=source,
            author_reference=author_ref,
            content_hash=bytes(row.content_hash),  # type: ignore[attr-defined]
            registered_at=reg_at,
            confidence_level=confidence_level,
            validity_period=validity_period,
            verifications=verifications,
            revocation=revocation,
            signature=signature,
            version=row.version,  # type: ignore[attr-defined]
        )


attachments_table = Table(
    "attachments",
    organization_metadata,
    Column("attachment_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("filename", String(255), nullable=False),
    Column("content_type", String(100), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("content_hash", LargeBinary, nullable=False),
    Column("blob_uri", String(512), nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
    Column("version", Integer, nullable=False, server_default="1"),
    CheckConstraint("version >= 1", name="ck_attachments_version"),
    CheckConstraint("size_bytes > 0", name="ck_attachments_size_bytes"),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_attachments_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TransactionalAttachmentRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalAttachmentRepository exige transacao ativa.")

    def save(self, attachment: Attachment) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.attachments (
                    attachment_id,
                    record_owner_organization_id,
                    filename,
                    content_type,
                    size_bytes,
                    content_hash,
                    blob_uri,
                    uploaded_at,
                    version
                ) VALUES (
                    :attachment_id,
                    :org_id,
                    :filename,
                    :content_type,
                    :size_bytes,
                    :content_hash,
                    :blob_uri,
                    :uploaded_at,
                    :version
                )
                """
            ),
            {
                "attachment_id": attachment.attachment_id.value,
                "org_id": attachment.organization_id.value,
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "size_bytes": attachment.size_bytes,
                "content_hash": attachment.content_hash,
                "blob_uri": attachment.blob_uri,
                "uploaded_at": attachment.uploaded_at,
                "version": attachment.version,
            },
        )

    def get_by_id(self, attachment_id: TypedId) -> Attachment | None:
        row = self.connection.execute(
            text(
                """
                SELECT
                    attachment_id,
                    record_owner_organization_id,
                    filename,
                    content_type,
                    size_bytes,
                    content_hash,
                    blob_uri,
                    uploaded_at,
                    version
                FROM core_audit.attachments
                WHERE attachment_id = :attachment_id
                """
            ),
            {"attachment_id": attachment_id.value},
        ).first()

        if row is None:
            return None

        up_at = (
            row.uploaded_at.replace(tzinfo=UTC)
            if row.uploaded_at.tzinfo is None
            else row.uploaded_at
        )

        return Attachment(
            attachment_id=TypedId(entity_type="attachment", value=row.attachment_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            filename=row.filename,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
            content_hash=bytes(row.content_hash),
            blob_uri=row.blob_uri,
            uploaded_at=up_at,
            version=row.version,
        )

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Attachment]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    attachment_id,
                    record_owner_organization_id,
                    filename,
                    content_type,
                    size_bytes,
                    content_hash,
                    blob_uri,
                    uploaded_at,
                    version
                FROM core_audit.attachments
                WHERE record_owner_organization_id = :org_id
                ORDER BY uploaded_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"org_id": organization_id.value, "limit": limit, "offset": offset},
        ).fetchall()

        attachments: list[Attachment] = []
        for row in rows:
            up_at = (
                row.uploaded_at.replace(tzinfo=UTC)
                if row.uploaded_at.tzinfo is None
                else row.uploaded_at
            )
            attachments.append(
                Attachment(
                    attachment_id=TypedId(entity_type="attachment", value=row.attachment_id),
                    organization_id=OrganizationId(row.record_owner_organization_id),
                    filename=row.filename,
                    content_type=row.content_type,
                    size_bytes=row.size_bytes,
                    content_hash=bytes(row.content_hash),
                    blob_uri=row.blob_uri,
                    uploaded_at=up_at,
                    version=row.version,
                )
            )
        return attachments
