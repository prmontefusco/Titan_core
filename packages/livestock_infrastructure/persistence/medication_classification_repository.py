"""Persistência das Assertions sanitárias de medicamento."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Column, Connection, DateTime, ForeignKey, String, Table, Text, insert, select
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from packages.core_domain.evidence import ConfidenceTier
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_domain.medication_classification import (
    MedicationClassificationStatus,
    MedicationClassificationValidation,
    MedicationSanitaryCategory,
    MedicationSanitaryClassificationAssertion,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

medication_classification_assertions_table = Table(
    "medication_classification_assertions",
    livestock_metadata,
    Column("assertion_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "record_owner_organization_id",
        UUID(as_uuid=True),
        ForeignKey("core_identity.organizations.organization_id"),
        nullable=False,
    ),
    Column(
        "medication_id",
        UUID(as_uuid=True),
        ForeignKey("core_audit.medications.medication_id"),
        nullable=False,
    ),
    Column("category", String(60), nullable=False),
    Column("status", String(40), nullable=False),
    Column("valid_from", DateTime(timezone=True)),
    Column("valid_to", DateTime(timezone=True)),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("source_entity_type", String(80), nullable=False),
    Column("source_id", UUID(as_uuid=True), nullable=False),
    Column("confidence_tier", String(50), nullable=False),
    Column("validation_status", String(50), nullable=False),
    Column("limitations", ARRAY(Text), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalMedicationClassificationRepository:
    connection: Connection

    def save(self, item: MedicationSanitaryClassificationAssertion) -> None:
        self.connection.execute(
            insert(medication_classification_assertions_table).values(
                assertion_id=item.assertion_id.value,
                record_owner_organization_id=item.organization_id.value,
                medication_id=item.medication_id.value,
                category=item.category.value,
                status=item.status.value,
                valid_from=item.valid_from,
                valid_to=item.valid_to,
                observed_at=item.observed_at,
                source_entity_type=item.source_reference.target_id.entity_type,
                source_id=item.source_reference.target_id.value,
                confidence_tier=item.confidence_tier.value,
                validation_status=item.validation_status.value,
                limitations=list(item.limitations),
                recorded_at=item.recorded_at,
            )
        )

    def list_by_medication(
        self, organization_id: OrganizationId, medication_id: TypedId
    ) -> list[MedicationSanitaryClassificationAssertion]:
        rows = self.connection.execute(
            select(medication_classification_assertions_table).where(
                medication_classification_assertions_table.c.record_owner_organization_id
                == organization_id.value,
                medication_classification_assertions_table.c.medication_id == medication_id.value,
            )
        ).all()

        def aware(value: datetime | None) -> datetime | None:
            return (
                value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value
            )

        items = []
        for row in rows:
            observed_at = aware(row.observed_at)
            recorded_at = aware(row.recorded_at)
            assert observed_at is not None and recorded_at is not None
            items.append(
                MedicationSanitaryClassificationAssertion(
                    assertion_id=TypedId("medication_classification_assertion", row.assertion_id),
                    organization_id=OrganizationId(row.record_owner_organization_id),
                    medication_id=TypedId("medication", row.medication_id),
                    category=MedicationSanitaryCategory(row.category),
                    status=MedicationClassificationStatus(row.status),
                    valid_from=aware(row.valid_from),
                    valid_to=aware(row.valid_to),
                    observed_at=observed_at,
                    source_reference=UniversalReference(
                        TypedId(row.source_entity_type, row.source_id), organization_id, 1
                    ),
                    confidence_tier=ConfidenceTier(row.confidence_tier),
                    validation_status=MedicationClassificationValidation(row.validation_status),
                    limitations=tuple(row.limitations),
                    recorded_at=recorded_at,
                )
            )
        return items
