"""Persistência de Evidence, Validity, Revocation e Signature sob RLS (ADR-0038/Passo 5.6)."""

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

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
    UniqueConstraint,
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
    UniqueConstraint(
        "record_owner_organization_id",
        "evidence_id",
        name="uq_evidences_owner_id",
    ),
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
    Column("evidence_version", Integer, nullable=True),
    Column("recorded_at", DateTime(timezone=True), nullable=True),
    Column("verified_at", DateTime(timezone=True), nullable=False),
    Column("verifier_id", PG_UUID(as_uuid=True), nullable=False),
    Column("verifier_org_id", PG_UUID(as_uuid=True), nullable=False),
    Column("verifier_contract_version", Integer, nullable=False, server_default="1"),
    Column("outcome", String(50), nullable=False),
    Column("notes", Text, nullable=True),
    CheckConstraint(
        "evidence_version IS NULL OR evidence_version > 1",
        name="ck_evidence_verifications_version",
    ),
    UniqueConstraint(
        "evidence_id",
        "evidence_version",
        name="uq_evidence_verifications_version",
    ),
    ForeignKeyConstraint(
        ["evidence_id"],
        ["core_audit.evidences.evidence_id"],
        name="fk_evidence_verifications_evidence",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id", "evidence_id"],
        ["core_audit.evidences.record_owner_organization_id", "core_audit.evidences.evidence_id"],
        name="fk_evidence_verifications_owner_evidence",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_evidence_verifications_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

evidence_signatures_table = Table(
    "evidence_signatures",
    organization_metadata,
    Column("signature_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("evidence_id", PG_UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("evidence_version", Integer, nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("profile", String(50), nullable=False),
    Column("algorithm", String(50), nullable=False),
    Column("raw_bytes", LargeBinary, nullable=False),
    Column("key_id", PG_UUID(as_uuid=True), nullable=False),
    Column("key_purpose", String(100), nullable=False),
    Column("signed_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("evidence_version > 1", name="ck_evidence_signatures_version"),
    UniqueConstraint("evidence_id", "evidence_version", name="uq_evidence_signatures_version"),
    ForeignKeyConstraint(
        ["record_owner_organization_id", "evidence_id"],
        ["core_audit.evidences.record_owner_organization_id", "core_audit.evidences.evidence_id"],
        name="fk_evidence_signatures_owner_evidence",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

evidence_revocations_table = Table(
    "evidence_revocations",
    organization_metadata,
    Column("revocation_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("evidence_id", PG_UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("evidence_version", Integer, nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True), nullable=False),
    Column("revoking_actor_id", PG_UUID(as_uuid=True), nullable=False),
    Column("revoking_actor_org_id", PG_UUID(as_uuid=True), nullable=False),
    Column("revoking_actor_contract_version", Integer, nullable=False),
    Column("reason", Text, nullable=False),
    CheckConstraint("evidence_version > 1", name="ck_evidence_revocations_version"),
    UniqueConstraint("evidence_id", "evidence_version", name="uq_evidence_revocations_version"),
    UniqueConstraint("evidence_id", name="uq_evidence_revocations_evidence"),
    ForeignKeyConstraint(
        ["record_owner_organization_id", "evidence_id"],
        ["core_audit.evidences.record_owner_organization_id", "core_audit.evidences.evidence_id"],
        name="fk_evidence_revocations_owner_evidence",
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
        if evidence.verifications:
            raise ValueError("Verificações exigem append_verification após registrar a Evidence.")
        if evidence.signature is not None:
            raise ValueError("Assinatura exige append_signature após registrar a Evidence.")
        if evidence.revocation is not None:
            raise ValueError("Revogação exige append_revocation após registrar a Evidence.")
        valid_from = evidence.validity_period.valid_from if evidence.validity_period else None
        valid_until = evidence.validity_period.valid_until if evidence.validity_period else None

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
                "is_revoked": False,
                "revoked_at": None,
                "revoking_actor_id": None,
                "revoking_actor_org_id": None,
                "revoking_actor_contract_version": None,
                "revocation_reason": None,
                "signature_id": None,
                "signature_profile": None,
                "signature_algorithm": None,
                "signature_raw_bytes": None,
                "signature_key_id": None,
                "signature_key_purpose": None,
                "signature_signed_at": None,
                "version": evidence.version,
            },
        )

    def _lock_current(self, evidence: Evidence) -> Evidence:
        self.connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:id AS text), 0))"),
            {"id": str(evidence.evidence_id.value)},
        )
        current = self.get_by_id(evidence.evidence_id)
        if current is None or current.organization_id != evidence.organization_id:
            raise KeyError("Evidência não encontrada na Organization ativa.")
        if evidence.version != current.version + 1:
            raise ValueError("Versão de ciclo de vida da Evidence desatualizada.")
        return current

    def append_verification(self, evidence: Evidence) -> None:
        current = self._lock_current(evidence)
        if len(evidence.verifications) != len(current.verifications) + 1:
            raise ValueError("A operação exige exatamente uma nova verificação.")
        verification = evidence.verifications[-1]
        if current.add_verification(verification) != evidence:
            raise ValueError("A verificação não pode alterar o conteúdo da Evidence.")
        self.connection.execute(
            text("""
                INSERT INTO core_audit.evidence_verifications (
                    verification_id, evidence_id, record_owner_organization_id,
                    evidence_version, recorded_at, verified_at, verifier_id,
                    verifier_org_id, verifier_contract_version, outcome, notes
                ) VALUES (:id, :evidence_id, :owner, :version, clock_timestamp(),
                          :verified_at, :actor, :actor_org, :contract, :outcome, :notes)
            """),
            {
                "id": verification.verification_id.value,
                "evidence_id": evidence.evidence_id.value,
                "owner": evidence.organization_id.value,
                "version": evidence.version,
                "verified_at": verification.verified_at,
                "actor": verification.verifier_reference.target_id.value,
                "actor_org": (
                    verification.verifier_reference.organization_id or evidence.organization_id
                ).value,
                "contract": verification.verifier_reference.contract_version,
                "outcome": verification.outcome.value,
                "notes": verification.notes,
            },
        )

    def append_signature(self, evidence: Evidence) -> None:
        current = self._lock_current(evidence)
        signature = evidence.signature
        if signature is None or current.sign_evidence(signature) != evidence:
            raise ValueError("A assinatura não pode alterar o conteúdo da Evidence.")
        self.connection.execute(
            text("""
                INSERT INTO core_audit.evidence_signatures (
                    signature_id, evidence_id, record_owner_organization_id,
                    evidence_version, recorded_at, profile, algorithm, raw_bytes,
                    key_id, key_purpose, signed_at
                ) VALUES (:id, :evidence_id, :owner, :version, clock_timestamp(),
                          :profile, :algorithm, :raw, :key, :purpose, :signed_at)
            """),
            {
                "id": signature.signature_id.value,
                "evidence_id": evidence.evidence_id.value,
                "owner": evidence.organization_id.value,
                "version": evidence.version,
                "profile": signature.profile.value,
                "algorithm": signature.algorithm,
                "raw": signature.raw_signature,
                "key": signature.key_identifier.key_id.value,
                "purpose": signature.key_identifier.purpose,
                "signed_at": signature.signed_at,
            },
        )

    def append_revocation(self, evidence: Evidence) -> None:
        current = self._lock_current(evidence)
        revocation = evidence.revocation
        if revocation is None or current.revoke(revocation) != evidence:
            raise ValueError("A revogação não pode alterar o conteúdo da Evidence.")
        self.connection.execute(
            text("""
                INSERT INTO core_audit.evidence_revocations (
                    revocation_id, evidence_id, record_owner_organization_id,
                    evidence_version, recorded_at, revoked_at, revoking_actor_id,
                    revoking_actor_org_id, revoking_actor_contract_version, reason
                ) VALUES (:id, :evidence_id, :owner, :version, clock_timestamp(),
                          :revoked_at, :actor, :actor_org, :contract, :reason)
            """),
            {
                "id": TypedId.new("evidence_revocation").value,
                "evidence_id": evidence.evidence_id.value,
                "owner": evidence.organization_id.value,
                "version": evidence.version,
                "revoked_at": revocation.revoked_at,
                "actor": revocation.revoking_actor.target_id.value,
                "actor_org": (
                    revocation.revoking_actor.organization_id or evidence.organization_id
                ).value,
                "contract": revocation.revoking_actor.contract_version,
                "reason": revocation.reason,
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

        return self._compose_lifecycle(self._map_row_to_evidence(row, ()))

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
            evidences.append(self._compose_lifecycle(self._map_row_to_evidence(row, ())))
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
            evidences.append(self._compose_lifecycle(self._map_row_to_evidence(row, ())))
        return evidences

    def _compose_lifecycle(self, base: Evidence) -> Evidence:
        # A base é imutável. Um único snapshot SQL das três tabelas impede
        # combinar a versão de uma operação concorrente com conteúdo anterior.
        rows = self.connection.execute(
            text("""
                SELECT 'verification' AS kind, to_jsonb(v) AS payload
                FROM core_audit.evidence_verifications v WHERE evidence_id = :id
                UNION ALL
                SELECT 'signature', to_jsonb(s)
                FROM core_audit.evidence_signatures s WHERE evidence_id = :id
                UNION ALL
                SELECT 'revocation', to_jsonb(r)
                FROM core_audit.evidence_revocations r WHERE evidence_id = :id
            """),
            {"id": base.evidence_id.value},
        ).all()
        events = sorted(
            rows,
            key=lambda row: (
                row.payload["evidence_version"] or 0,
                row.payload.get("verified_at", ""),
            ),
        )
        result = base
        verifications: list[VerificationRecord] = []
        for row in events:
            data = row.payload
            version = data["evidence_version"] or base.version
            if row.kind == "verification":
                verifications.append(
                    VerificationRecord(
                        verification_id=TypedId("verification", UUID(data["verification_id"])),
                        verified_at=_parse_datetime(data["verified_at"]),
                        verifier_reference=_lifecycle_actor(data, "verifier"),
                        outcome=VerificationOutcome(data["outcome"]),
                        notes=data["notes"],
                    )
                )
            elif row.kind == "signature":
                result = replace(
                    result,
                    signature=CryptographicSignature(
                        signature_id=TypedId("signature", UUID(data["signature_id"])),
                        profile=CryptographicProfile(data["profile"]),
                        algorithm=data["algorithm"],
                        raw_signature=_parse_bytea(data["raw_bytes"]),
                        key_identifier=KeyIdentifier(
                            TypedId("key", UUID(data["key_id"])), data["key_purpose"]
                        ),
                        signed_at=_parse_datetime(data["signed_at"]),
                    ),
                )
            else:
                result = replace(
                    result,
                    revocation=EvidenceRevocation(
                        revoked_at=_parse_datetime(data["revoked_at"]),
                        revoking_actor=_lifecycle_actor(data, "revoking_actor"),
                        reason=data["reason"],
                    ),
                )
            result = replace(result, version=max(result.version, version))
        return replace(result, verifications=tuple(verifications))

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


def _lifecycle_actor(data: dict[str, Any], prefix: str) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId("user", UUID(data[f"{prefix}_id"])),
        organization_id=OrganizationId(UUID(data[f"{prefix}_org_id"])),
        contract_version=data[f"{prefix}_contract_version"],
    )


def _parse_datetime(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _parse_bytea(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        return value
    return bytes.fromhex(value[2:] if value.startswith("\\x") else value)


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
