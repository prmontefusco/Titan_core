"""Append-only PostgreSQL storage for byte-identical VerificationBundles."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Table,
    UniqueConstraint,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_application.verification_service import VerificationBundleService
from packages.core_domain.dossier import Dossier
from packages.core_domain.verification import VerificationBundle
from packages.core_infrastructure.persistence.dossier import dossiers_table
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

VERIFICATION_BUNDLE_CONTENT_TYPE = "application/json"
VERIFICATION_BUNDLE_SERIALIZATION_VERSION = "titan-verification-bundle-json-v1"
MAX_VERIFICATION_BUNDLE_BYTES = 2 * 1024 * 1024

verification_bundles_table = Table(
    "verification_bundles",
    organization_metadata,
    Column("bundle_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("dossier_id", PG_UUID(as_uuid=True), nullable=False),
    Column("purpose", String(255), nullable=False),
    Column("audience", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("format_version", Integer, nullable=False),
    Column("serialization_version", String(80), nullable=False),
    Column("manifest_digest", String(64), nullable=False),
    Column("content_type", String(100), nullable=False),
    Column("serialized_payload_digest", String(64), nullable=False),
    Column("serialized_size_bytes", BigInteger, nullable=False),
    Column("payload_bytes", LargeBinary, nullable=False),
    CheckConstraint("serialized_size_bytes > 0", name="ck_verification_bundle_size"),
    CheckConstraint(
        "octet_length(payload_bytes) = serialized_size_bytes",
        name="ck_verification_bundle_payload_size",
    ),
    CheckConstraint(
        "content_type = 'application/json'",
        name="ck_verification_bundle_content_type",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_verification_bundles_organization",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id", "dossier_id"],
        [
            "core_audit.dossiers.record_owner_organization_id",
            "core_audit.dossiers.dossier_id",
        ],
        name="fk_verification_bundles_owner_dossier",
    ),
    UniqueConstraint(
        "record_owner_organization_id",
        "bundle_id",
        name="uq_verification_bundles_owner_bundle",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class StoredVerificationBundle:
    bundle: VerificationBundle
    dossier_id: TypedId
    payload_bytes: bytes
    content_type: str
    serialization_version: str
    serialized_payload_digest: str


@dataclass(frozen=True, slots=True)
class TransactionalVerificationBundleRepository:
    connection: Connection
    maximum_size_bytes: int = MAX_VERIFICATION_BUNDLE_BYTES

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalVerificationBundleRepository exige transação ativa.")
        if self.maximum_size_bytes <= 0:
            raise ValueError("maximum_size_bytes deve ser positivo.")

    def save(self, *, bundle: VerificationBundle, dossier: Dossier) -> StoredVerificationBundle:
        if bundle.manifest.organization_id != dossier.organization_id:
            raise ValueError("VerificationBundle e Dossier pertencem a Organizations distintas.")
        if bundle.manifest.purpose != dossier.purpose:
            raise ValueError("VerificationBundle e Dossier possuem purposes distintos.")
        payload_bytes = VerificationBundleService().export_bytes(bundle)
        if len(payload_bytes) > self.maximum_size_bytes:
            raise ValueError("VerificationBundle excede o limite de tamanho do perfil interno.")
        payload_digest = hashlib.sha256(payload_bytes).hexdigest()
        self.connection.execute(
            verification_bundles_table.insert().values(
                bundle_id=bundle.manifest.bundle_id.value,
                record_owner_organization_id=bundle.manifest.organization_id.value,
                dossier_id=dossier.dossier_id.value,
                purpose=bundle.manifest.purpose,
                audience=bundle.manifest.audience,
                created_at=bundle.manifest.created_at,
                format_version=bundle.manifest.format_version,
                serialization_version=VERIFICATION_BUNDLE_SERIALIZATION_VERSION,
                manifest_digest=bundle.manifest.manifest_digest,
                content_type=VERIFICATION_BUNDLE_CONTENT_TYPE,
                serialized_payload_digest=payload_digest,
                serialized_size_bytes=len(payload_bytes),
                payload_bytes=payload_bytes,
            )
        )
        return StoredVerificationBundle(
            bundle=bundle,
            dossier_id=dossier.dossier_id,
            payload_bytes=payload_bytes,
            content_type=VERIFICATION_BUNDLE_CONTENT_TYPE,
            serialization_version=VERIFICATION_BUNDLE_SERIALIZATION_VERSION,
            serialized_payload_digest=payload_digest,
        )

    def get_by_id(
        self, organization_id: OrganizationId, bundle_id: TypedId
    ) -> StoredVerificationBundle | None:
        if bundle_id.entity_type != "verification_bundle":
            raise ValueError("bundle_id deve identificar VerificationBundle.")
        row = self.connection.execute(
            select(
                verification_bundles_table,
                dossiers_table.c.purpose.label("dossier_purpose"),
                dossiers_table.c.document.label("dossier_document"),
            )
            .select_from(
                verification_bundles_table.join(
                    dossiers_table,
                    (
                        verification_bundles_table.c.record_owner_organization_id
                        == dossiers_table.c.record_owner_organization_id
                    )
                    & (verification_bundles_table.c.dossier_id == dossiers_table.c.dossier_id),
                )
            )
            .where(
                verification_bundles_table.c.record_owner_organization_id == organization_id.value,
                verification_bundles_table.c.bundle_id == bundle_id.value,
            )
        ).first()
        if row is None:
            return None
        payload_bytes = bytes(row.payload_bytes)
        if len(payload_bytes) != row.serialized_size_bytes:
            raise RuntimeError("VERIFICATION_BUNDLE_TAMANHO_DIVERGENTE")
        payload_digest = hashlib.sha256(payload_bytes).hexdigest()
        if payload_digest != row.serialized_payload_digest:
            raise RuntimeError("VERIFICATION_BUNDLE_PAYLOAD_DIGEST_DIVERGENTE")
        bundle = VerificationBundleService.load_bytes(payload_bytes)
        manifest = bundle.manifest
        if (
            manifest.bundle_id.value != row.bundle_id
            or manifest.organization_id.value != row.record_owner_organization_id
            or manifest.purpose != row.purpose
            or manifest.purpose != row.dossier_purpose
            or manifest.audience != row.audience
            or manifest.manifest_digest != row.manifest_digest
            or manifest.format_version != row.format_version
            or row.content_type != VERIFICATION_BUNDLE_CONTENT_TYPE
            or row.serialization_version != VERIFICATION_BUNDLE_SERIALIZATION_VERSION
        ):
            raise RuntimeError("VERIFICATION_BUNDLE_METADATA_DIVERGENTE")
        dossier_payload = bundle.payloads.get("dossier.json")
        expected_dossier_payload = json.dumps(
            row.dossier_document,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if dossier_payload != expected_dossier_payload:
            raise RuntimeError("VERIFICATION_BUNDLE_DOSSIER_DIVERGENTE")
        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        if manifest.created_at != created_at:
            raise RuntimeError("VERIFICATION_BUNDLE_CREATED_AT_DIVERGENTE")
        return StoredVerificationBundle(
            bundle=bundle,
            dossier_id=TypedId("dossier", row.dossier_id),
            payload_bytes=payload_bytes,
            content_type=row.content_type,
            serialization_version=row.serialization_version,
            serialized_payload_digest=payload_digest,
        )
