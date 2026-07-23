"""Repositório PostgreSQL com RLS para Veterinarian (Passo 8.5 - Titan Livestock)."""

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.veterinarian_service import VeterinarianRepositoryPort
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.veterinarian import Veterinarian
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

veterinarians_table = Table(
    "veterinarians",
    livestock_metadata,
    Column("veterinarian_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("name", String(255), nullable=False),
    Column("cpf", String(11), nullable=False),
    Column("council_number", String(50), nullable=False),
    Column("council_state", String(2), nullable=False),
    Column("verification_status", String(30), nullable=False),
    Column("evidence_reference", String(255), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "record_owner_organization_id",
        "cpf",
        name="uq_veterinarians_org_cpf",
    ),
    UniqueConstraint(
        "record_owner_organization_id",
        "council_state",
        "council_number",
        name="uq_veterinarians_org_council",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_veterinarians_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalVeterinarianRepository(VeterinarianRepositoryPort):
    connection: Connection

    def save(self, vet: Veterinarian) -> None:
        stmt = insert(veterinarians_table).values(
            veterinarian_id=vet.veterinarian_id.value,
            record_owner_organization_id=vet.organization_id.value,
            name=vet.name,
            cpf=vet.cpf,
            council_number=vet.council_number,
            council_state=vet.council_state,
            verification_status=vet.verification_status.value,
            evidence_reference=vet.evidence_reference,
            created_at=vet.created_at,
        )
        self.connection.execute(stmt)

    def update(self, vet: Veterinarian) -> None:
        stmt = (
            update(veterinarians_table)
            .where(veterinarians_table.c.veterinarian_id == vet.veterinarian_id.value)
            .values(
                name=vet.name,
                verification_status=vet.verification_status.value,
                evidence_reference=vet.evidence_reference,
            )
        )
        self.connection.execute(stmt)

    def get_by_id(self, vet_id: TypedId) -> Veterinarian | None:
        if vet_id.entity_type != "veterinarian":
            return None
        stmt = select(veterinarians_table).where(
            veterinarians_table.c.veterinarian_id == vet_id.value
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_vet(row)

    def get_by_cpf(self, organization_id: OrganizationId, cpf: str) -> Veterinarian | None:
        stmt = select(veterinarians_table).where(
            veterinarians_table.c.record_owner_organization_id == organization_id.value,
            veterinarians_table.c.cpf == cpf,
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_vet(row)

    def get_by_council(
        self, organization_id: OrganizationId, state: str, number: str
    ) -> Veterinarian | None:
        stmt = select(veterinarians_table).where(
            veterinarians_table.c.record_owner_organization_id == organization_id.value,
            veterinarians_table.c.council_state == state.upper(),
            veterinarians_table.c.council_number == number,
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_vet(row)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Veterinarian]:
        stmt = (
            select(veterinarians_table)
            .where(veterinarians_table.c.record_owner_organization_id == organization_id.value)
            .order_by(veterinarians_table.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map_vet(row) for row in rows]

    def _map_vet(self, row: Row[Any]) -> Veterinarian:
        c_at = row.created_at
        if c_at.tzinfo is None:
            c_at = c_at.replace(tzinfo=UTC)

        return Veterinarian(
            veterinarian_id=TypedId(entity_type="veterinarian", value=row.veterinarian_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            name=row.name,
            cpf=row.cpf,
            council_number=row.council_number,
            council_state=row.council_state,
            verification_status=VerificationStatus(row.verification_status),
            evidence_reference=row.evidence_reference,
            created_at=c_at,
        )
