"""Repositórios PostgreSQL com RLS para Medication e Prescription (Passo 9.1 - Titan Livestock)."""

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.medication_service import (
    MedicationRepositoryPort,
    PrescriptionRepositoryPort,
)
from packages.livestock_domain.medication import Medication
from packages.livestock_domain.prescription import Prescription, PrescriptionTargetType
from packages.shared_kernel import OrganizationId, TypedId

livestock_metadata = MetaData(schema=CORE_AUDIT_SCHEMA)

medications_table = Table(
    "medications",
    livestock_metadata,
    Column("medication_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("trade_name", String(255), nullable=False),
    Column("active_ingredient", String(255), nullable=False),
    Column("manufacturer", String(255), nullable=False),
    Column("withdrawal_period_days", Integer, nullable=False),
    Column("dosage_instruction", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "record_owner_organization_id",
        "trade_name",
        name="uq_medications_org_trade_name",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_medications_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)

prescriptions_table = Table(
    "prescriptions",
    livestock_metadata,
    Column("prescription_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("veterinarian_id", PG_UUID(as_uuid=True), nullable=False),
    Column("medication_id", PG_UUID(as_uuid=True), nullable=False),
    Column("property_id", PG_UUID(as_uuid=True), nullable=False),
    Column("prescribed_date", DateTime(timezone=True), nullable=False),
    Column("dosage", String(255), nullable=False),
    Column("administration_route", String(100), nullable=False),
    Column("target_type", String(50), nullable=False),
    Column("reason", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_prescriptions_organization",
    ),
    ForeignKeyConstraint(
        ["veterinarian_id"],
        ["core_audit.veterinarians.veterinarian_id"],
        name="fk_prescriptions_veterinarian",
    ),
    ForeignKeyConstraint(
        ["medication_id"],
        ["core_audit.medications.medication_id"],
        name="fk_prescriptions_medication",
    ),
    ForeignKeyConstraint(
        ["property_id"],
        ["core_audit.rural_properties.property_id"],
        name="fk_prescriptions_property",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)

prescription_targets_table = Table(
    "prescription_targets",
    livestock_metadata,
    Column("prescription_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("target_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_prescription_targets_organization",
    ),
    ForeignKeyConstraint(
        ["prescription_id"],
        ["core_audit.prescriptions.prescription_id"],
        name="fk_prescription_targets_prescription",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalMedicationRepository(MedicationRepositoryPort):
    connection: Connection

    def save(self, medication: Medication) -> None:
        stmt = insert(medications_table).values(
            medication_id=medication.medication_id.value,
            record_owner_organization_id=medication.organization_id.value,
            trade_name=medication.trade_name,
            active_ingredient=medication.active_ingredient,
            manufacturer=medication.manufacturer,
            withdrawal_period_days=medication.withdrawal_period_days,
            dosage_instruction=medication.dosage_instruction,
            created_at=medication.created_at,
        )
        self.connection.execute(stmt)

    def get_by_id(self, medication_id: TypedId) -> Medication | None:
        if medication_id.entity_type != "medication":
            return None
        stmt = select(medications_table).where(
            medications_table.c.medication_id == medication_id.value
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_medication(row)

    def get_by_trade_name(
        self, organization_id: OrganizationId, trade_name: str
    ) -> Medication | None:
        stmt = select(medications_table).where(
            medications_table.c.record_owner_organization_id == organization_id.value,
            medications_table.c.trade_name == trade_name,
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_medication(row)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Medication]:
        stmt = (
            select(medications_table)
            .where(medications_table.c.record_owner_organization_id == organization_id.value)
            .order_by(medications_table.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map_medication(row) for row in rows]

    def _map_medication(self, row: Row[Any]) -> Medication:
        c_at = row.created_at
        if c_at.tzinfo is None:
            c_at = c_at.replace(tzinfo=UTC)

        return Medication(
            medication_id=TypedId(entity_type="medication", value=row.medication_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            trade_name=row.trade_name,
            active_ingredient=row.active_ingredient,
            manufacturer=row.manufacturer,
            withdrawal_period_days=row.withdrawal_period_days,
            dosage_instruction=row.dosage_instruction,
            created_at=c_at,
        )


@dataclass(frozen=True, slots=True)
class TransactionalPrescriptionRepository(PrescriptionRepositoryPort):
    connection: Connection

    def save(self, prescription: Prescription) -> None:
        stmt = insert(prescriptions_table).values(
            prescription_id=prescription.prescription_id.value,
            record_owner_organization_id=prescription.organization_id.value,
            veterinarian_id=prescription.veterinarian_id.value,
            medication_id=prescription.medication_id.value,
            property_id=prescription.property_id.value,
            prescribed_date=prescription.prescribed_date,
            dosage=prescription.dosage,
            administration_route=prescription.administration_route,
            target_type=prescription.target_type.value,
            reason=prescription.reason,
            created_at=prescription.created_at,
        )
        self.connection.execute(stmt)

        for tid in prescription.target_ids:
            stmt_target = insert(prescription_targets_table).values(
                prescription_id=prescription.prescription_id.value,
                target_id=tid.value,
                record_owner_organization_id=prescription.organization_id.value,
            )
            self.connection.execute(stmt_target)

    def get_by_id(self, prescription_id: TypedId) -> Prescription | None:
        if prescription_id.entity_type != "prescription":
            return None
        stmt = select(prescriptions_table).where(
            prescriptions_table.c.prescription_id == prescription_id.value
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_prescription(row)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Prescription]:
        stmt = (
            select(prescriptions_table)
            .where(prescriptions_table.c.record_owner_organization_id == organization_id.value)
            .order_by(prescriptions_table.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map_prescription(row) for row in rows]

    def _map_prescription(self, row: Row[Any]) -> Prescription:
        p_id = row.prescription_id
        stmt_targets = select(prescription_targets_table.c.target_id).where(
            prescription_targets_table.c.prescription_id == p_id
        )
        target_rows = self.connection.execute(stmt_targets).fetchall()

        t_type = PrescriptionTargetType(row.target_type)
        e_type = "animal" if t_type == PrescriptionTargetType.ANIMAL else "livestock_lot"
        target_ids = tuple(TypedId(entity_type=e_type, value=tr.target_id) for tr in target_rows)

        p_date = row.prescribed_date
        if p_date.tzinfo is None:
            p_date = p_date.replace(tzinfo=UTC)

        c_at = row.created_at
        if c_at.tzinfo is None:
            c_at = c_at.replace(tzinfo=UTC)

        return Prescription(
            prescription_id=TypedId(entity_type="prescription", value=p_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            veterinarian_id=TypedId(entity_type="veterinarian", value=row.veterinarian_id),
            medication_id=TypedId(entity_type="medication", value=row.medication_id),
            property_id=TypedId(entity_type="rural_property", value=row.property_id),
            prescribed_date=p_date,
            dosage=row.dosage,
            administration_route=row.administration_route,
            target_type=t_type,
            target_ids=target_ids,
            reason=row.reason,
            created_at=c_at,
        )
