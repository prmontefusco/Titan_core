"""Persistencia de artefato recebido de transferencia (ADR-0042)."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    String,
    Table,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.transfer_artifact_service import (
    ReceivedTransferArtifactRepositoryPort,
)
from packages.livestock_domain.transfer_artifact import (
    HistoryCoverage,
    ReceivedTransferArtifact,
    TransferArtifactGap,
    TransferArtifactGapCode,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

received_transfer_artifacts_table = Table(
    "received_transfer_artifacts",
    livestock_metadata,
    Column("artifact_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("animal_id", PG_UUID(as_uuid=True), nullable=False),
    Column("source_counterparty_id", PG_UUID(as_uuid=True), nullable=False),
    Column("bundle_digest", String(128), nullable=False),
    Column("bundle_issued_at", DateTime(timezone=True), nullable=False),
    Column("transfer_effective_at", DateTime(timezone=True), nullable=False),
    Column("coverage_known_from", DateTime(timezone=True), nullable=True),
    Column("coverage_known_until", DateTime(timezone=True), nullable=True),
    Column("coverage_gaps", JSONB, nullable=False, server_default="[]"),
    Column("issuer_name", String(255), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_received_transfer_artifacts_organization",
    ),
    ForeignKeyConstraint(
        ["animal_id"],
        ["core_audit.animals.animal_id"],
        name="fk_received_transfer_artifacts_animal",
    ),
    ForeignKeyConstraint(
        ["source_counterparty_id"],
        ["core_audit.external_counterparties.counterparty_id"],
        name="fk_received_transfer_artifacts_counterparty",
    ),
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    schema=CORE_AUDIT_SCHEMA,
)


@dataclass(frozen=True, slots=True)
class TransactionalReceivedTransferArtifactRepository(ReceivedTransferArtifactRepositoryPort):
    connection: Connection

    def save(self, artifact: ReceivedTransferArtifact) -> None:
        self.connection.execute(
            insert(received_transfer_artifacts_table).values(
                artifact_id=artifact.artifact_id.value,
                record_owner_organization_id=artifact.organization_id.value,
                animal_id=artifact.animal_id.value,
                source_counterparty_id=artifact.source_counterparty_id.value,
                bundle_digest=artifact.bundle_digest,
                bundle_issued_at=artifact.bundle_issued_at,
                transfer_effective_at=artifact.transfer_effective_at,
                coverage_known_from=artifact.coverage.known_from,
                coverage_known_until=artifact.coverage.known_until,
                coverage_gaps=json.dumps([_gap_to_dict(gap) for gap in artifact.coverage.gaps]),
                issuer_name=artifact.issuer_name,
                created_at=artifact.created_at,
            )
        )

    def get_by_id(self, artifact_id: TypedId) -> ReceivedTransferArtifact | None:
        if artifact_id.entity_type != "received_transfer_artifact":
            return None
        row = self.connection.execute(
            select(received_transfer_artifacts_table).where(
                received_transfer_artifacts_table.c.artifact_id == artifact_id.value
            )
        ).first()
        return None if row is None else self._map(row)

    def list_by_animal(self, animal_id: TypedId) -> list[ReceivedTransferArtifact]:
        rows = self.connection.execute(
            select(received_transfer_artifacts_table)
            .where(received_transfer_artifacts_table.c.animal_id == animal_id.value)
            .order_by(received_transfer_artifacts_table.c.created_at)
        ).all()
        return [self._map(row) for row in rows]

    def _map(self, row: Row[Any]) -> ReceivedTransferArtifact:
        def _aware(value: datetime | None) -> datetime | None:
            if value is None:
                return None
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        gaps = row.coverage_gaps
        if isinstance(gaps, str):
            gaps = json.loads(gaps)

        return ReceivedTransferArtifact(
            artifact_id=TypedId(entity_type="received_transfer_artifact", value=row.artifact_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            animal_id=TypedId(entity_type="animal", value=row.animal_id),
            source_counterparty_id=TypedId(
                entity_type="external_counterparty", value=row.source_counterparty_id
            ),
            bundle_digest=row.bundle_digest,
            bundle_issued_at=_aware(row.bundle_issued_at) or row.bundle_issued_at,
            transfer_effective_at=_aware(row.transfer_effective_at) or row.transfer_effective_at,
            coverage=HistoryCoverage(
                known_from=_aware(row.coverage_known_from),
                known_until=_aware(row.coverage_known_until),
                gaps=tuple(_gap_from_dict(item) for item in (gaps or [])),
            ),
            issuer_name=row.issuer_name,
            created_at=_aware(row.created_at) or row.created_at,
        )


def _gap_to_dict(gap: TransferArtifactGap) -> dict[str, str | None]:
    return {
        "code": gap.code.value,
        "starts_at": None if gap.starts_at is None else gap.starts_at.isoformat(),
        "ends_at": None if gap.ends_at is None else gap.ends_at.isoformat(),
        "description": gap.description,
    }


def _gap_from_dict(data: dict[str, Any]) -> TransferArtifactGap:
    return TransferArtifactGap(
        code=TransferArtifactGapCode(data["code"]),
        starts_at=(
            None if data.get("starts_at") is None else datetime.fromisoformat(data["starts_at"])
        ),
        ends_at=None if data.get("ends_at") is None else datetime.fromisoformat(data["ends_at"]),
        description=data["description"],
    )
