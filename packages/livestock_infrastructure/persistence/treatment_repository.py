"""Repositório PostgreSQL com RLS para TreatmentApplication (Passo 9.3 - Titan Livestock)."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Table,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.treatment_service import TreatmentApplicationRepositoryPort
from packages.livestock_domain.treatment import TreatmentApplication
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

treatment_applications_table = Table(
    "treatment_applications",
    livestock_metadata,
    Column("application_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("animal_id", PG_UUID(as_uuid=True), nullable=False),
    Column("medication_batch_id", PG_UUID(as_uuid=True), nullable=False),
    Column("actor_id", PG_UUID(as_uuid=True), nullable=False),
    Column("applied_at", DateTime(timezone=True), nullable=False),
    Column("dose", String(255), nullable=True),
    Column("evidence_references", JSONB, nullable=False, server_default="[]"),
    Column("evidence_notes", JSONB, nullable=False, server_default="[]"),
    Column("prescription_id", PG_UUID(as_uuid=True), nullable=True),
    Column("sanitary_campaign_id", PG_UUID(as_uuid=True), nullable=True),
    Column("corrects_application_id", PG_UUID(as_uuid=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_treatment_applications_organization",
    ),
    ForeignKeyConstraint(
        ["animal_id"],
        ["core_audit.animals.animal_id"],
        name="fk_treatment_applications_animal",
    ),
    ForeignKeyConstraint(
        ["medication_batch_id"],
        ["core_audit.medication_batches.batch_id"],
        name="fk_treatment_applications_batch",
    ),
    ForeignKeyConstraint(
        ["prescription_id"],
        ["core_audit.prescriptions.prescription_id"],
        name="fk_treatment_applications_prescription",
    ),
    ForeignKeyConstraint(
        ["sanitary_campaign_id"],
        ["core_audit.sanitary_campaigns.campaign_id"],
        name="fk_treatment_applications_sanitary_campaign",
    ),
    ForeignKeyConstraint(
        ["corrects_application_id"],
        ["core_audit.treatment_applications.application_id"],
        name="fk_treatment_applications_corrects",
    ),
    Index("ix_treatment_applications_animal", "record_owner_organization_id", "animal_id"),
    Index("ix_treatment_applications_batch", "record_owner_organization_id", "medication_batch_id"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalTreatmentApplicationRepository(TreatmentApplicationRepositoryPort):
    connection: Connection

    def save(self, application: TreatmentApplication) -> None:
        stmt = insert(treatment_applications_table).values(
            application_id=application.application_id.value,
            record_owner_organization_id=application.organization_id.value,
            animal_id=application.animal_id.value,
            medication_batch_id=application.medication_batch_id.value,
            actor_id=application.actor_id.value,
            applied_at=application.applied_at,
            dose=application.dose,
            evidence_references=json.dumps(
                [reference_to_dict(r) for r in application.evidence_references]
            ),
            evidence_notes=json.dumps(list(application.evidence_notes)),
            prescription_id=(
                application.prescription_id.value if application.prescription_id else None
            ),
            sanitary_campaign_id=(
                application.sanitary_campaign_id.value if application.sanitary_campaign_id else None
            ),
            corrects_application_id=(
                application.corrects_application_id.value
                if application.corrects_application_id
                else None
            ),
            created_at=application.created_at,
        )
        self.connection.execute(stmt)

    def get_by_id(self, application_id: TypedId) -> TreatmentApplication | None:
        if application_id.entity_type != "treatment_application":
            return None
        stmt = select(treatment_applications_table).where(
            treatment_applications_table.c.application_id == application_id.value
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map(row)

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[TreatmentApplication]:
        stmt = (
            select(treatment_applications_table)
            .where(
                treatment_applications_table.c.record_owner_organization_id
                == organization_id.value,
                treatment_applications_table.c.animal_id == animal_id.value,
            )
            .order_by(treatment_applications_table.c.applied_at.asc())
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map(row) for row in rows]

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[TreatmentApplication]:
        """Aplicações da organização, da mais recente à mais antiga.

        Inclui as corrigidas: elas continuam sendo registros válidos do que foi
        lançado, e omiti-las aqui esconderia da listagem o que a linha do tempo
        mostra. Quem quer saber o que vale hoje consulta a carência.
        """
        stmt = (
            select(treatment_applications_table)
            .where(
                treatment_applications_table.c.record_owner_organization_id == organization_id.value
            )
            .order_by(treatment_applications_table.c.applied_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map(row) for row in rows]

    def list_by_batch(
        self, organization_id: OrganizationId, medication_batch_id: TypedId
    ) -> list[TreatmentApplication]:
        stmt = (
            select(treatment_applications_table)
            .where(
                treatment_applications_table.c.record_owner_organization_id
                == organization_id.value,
                treatment_applications_table.c.medication_batch_id == medication_batch_id.value,
            )
            .order_by(treatment_applications_table.c.applied_at.asc())
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map(row) for row in rows]

    def _map(self, row: Row[Any]) -> TreatmentApplication:
        def _aware(value: datetime | None) -> datetime | None:
            if value is None:
                return None
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        applied = _aware(row.applied_at)
        created = _aware(row.created_at)
        assert applied is not None
        assert created is not None

        def _json(value: Any) -> list[Any]:
            loaded = json.loads(value) if isinstance(value, str) else value
            return list(loaded) if loaded else []

        evidence = _json(row.evidence_references)
        notes = _json(row.evidence_notes)

        return TreatmentApplication(
            application_id=TypedId(entity_type="treatment_application", value=row.application_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            animal_id=TypedId(entity_type="animal", value=row.animal_id),
            medication_batch_id=TypedId(
                entity_type="medication_batch", value=row.medication_batch_id
            ),
            actor_id=TypedId(entity_type="actor", value=row.actor_id),
            applied_at=applied,
            dose=row.dose,
            evidence_references=tuple(
                reference
                for reference in (reference_from_dict(item) for item in evidence)
                if reference is not None
            ),
            evidence_notes=tuple(notes),
            prescription_id=(
                TypedId(entity_type="prescription", value=row.prescription_id)
                if row.prescription_id is not None
                else None
            ),
            sanitary_campaign_id=(
                TypedId(entity_type="sanitary_campaign", value=row.sanitary_campaign_id)
                if row.sanitary_campaign_id is not None
                else None
            ),
            corrects_application_id=(
                TypedId(entity_type="treatment_application", value=row.corrects_application_id)
                if row.corrects_application_id is not None
                else None
            ),
            created_at=created,
        )
