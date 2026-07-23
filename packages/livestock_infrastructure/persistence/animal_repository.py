"""Repositório PostgreSQL com RLS para Animal e AnimalIdentifier (Passo 8.2 - Titan Livestock)."""

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_domain.animal import (
    Animal,
    AnimalIdentifier,
    AnimalSex,
    IdentifierState,
    IdentifierType,
    VerificationStatus,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

animals_table = Table(
    "animals",
    livestock_metadata,
    Column("animal_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("birth_property_id", PG_UUID(as_uuid=True), nullable=False),
    Column("sex", String(20), nullable=False),
    Column("breed", String(100), nullable=True),
    Column("birth_date", Date, nullable=True),
    Column("version", Integer, nullable=False, default=1),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_animals_organization",
    ),
    ForeignKeyConstraint(
        ["birth_property_id"],
        ["core_audit.rural_properties.property_id"],
        name="fk_animals_birth_property",
    ),
    Index("ix_animals_org_birth_prop", "record_owner_organization_id", "birth_property_id"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)

animal_identifiers_table = Table(
    "animal_identifiers",
    livestock_metadata,
    Column("identifier_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("animal_id", PG_UUID(as_uuid=True), nullable=False),
    Column("identifier_type", String(50), nullable=False),
    Column("identifier_value", String(100), nullable=False),
    Column("state", String(20), nullable=False),
    Column("issuer_source", String(100), nullable=True),
    Column("evidence_reference", String(255), nullable=True),
    Column("verification_status", String(50), nullable=False, default="DECLARADO"),
    Column("valid_from", DateTime(timezone=True), nullable=True),
    Column("valid_until", DateTime(timezone=True), nullable=True),
    Column("attached_at", DateTime(timezone=True), nullable=False),
    Column("deactivated_at", DateTime(timezone=True), nullable=True),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_animal_identifiers_organization",
    ),
    ForeignKeyConstraint(
        ["animal_id"],
        ["core_audit.animals.animal_id"],
        name="fk_animal_identifiers_animal",
    ),
    Index(
        "ix_animal_identifiers_search",
        "record_owner_organization_id",
        "identifier_type",
        "identifier_value",
        "state",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalAnimalRepository(AnimalRepositoryPort):
    connection: Connection

    def save(self, animal: Animal) -> None:
        stmt_animal = insert(animals_table).values(
            animal_id=animal.animal_id.value,
            record_owner_organization_id=animal.organization_id.value,
            birth_property_id=animal.birth_property_id.value,
            sex=animal.sex.value,
            breed=animal.breed,
            birth_date=animal.birth_date,
            version=animal.version,
            created_at=animal.created_at,
        )
        self.connection.execute(stmt_animal)

        for tag in animal.identifiers:
            stmt_tag = insert(animal_identifiers_table).values(
                identifier_id=tag.identifier_id.value,
                record_owner_organization_id=animal.organization_id.value,
                animal_id=animal.animal_id.value,
                identifier_type=tag.identifier_type.value,
                identifier_value=tag.identifier_value,
                state=tag.state.value,
                issuer_source=tag.issuer_source,
                evidence_reference=tag.evidence_reference,
                verification_status=tag.verification_status.value
                if isinstance(tag.verification_status, VerificationStatus)
                else tag.verification_status,
                valid_from=tag.valid_from,
                valid_until=tag.valid_until,
                attached_at=tag.attached_at,
                deactivated_at=tag.deactivated_at,
            )
            self.connection.execute(stmt_tag)

    def update(self, animal: Animal) -> None:
        stmt_animal = (
            update(animals_table)
            .where(animals_table.c.animal_id == animal.animal_id.value)
            .values(
                sex=animal.sex.value,
                breed=animal.breed,
                birth_date=animal.birth_date,
                version=animal.version,
            )
        )
        self.connection.execute(stmt_animal)

        # Sincroniza identificadores do animal
        self.connection.execute(
            delete(animal_identifiers_table).where(
                animal_identifiers_table.c.animal_id == animal.animal_id.value
            )
        )
        for tag in animal.identifiers:
            stmt_tag = insert(animal_identifiers_table).values(
                identifier_id=tag.identifier_id.value,
                record_owner_organization_id=animal.organization_id.value,
                animal_id=animal.animal_id.value,
                identifier_type=tag.identifier_type.value,
                identifier_value=tag.identifier_value,
                state=tag.state.value,
                issuer_source=tag.issuer_source,
                evidence_reference=tag.evidence_reference,
                verification_status=tag.verification_status.value
                if isinstance(tag.verification_status, VerificationStatus)
                else tag.verification_status,
                valid_from=tag.valid_from,
                valid_until=tag.valid_until,
                attached_at=tag.attached_at,
                deactivated_at=tag.deactivated_at,
            )
            self.connection.execute(stmt_tag)

    def get_by_id(self, animal_id: TypedId) -> Animal | None:
        if animal_id.entity_type != "animal":
            return None
        stmt = select(animals_table).where(animals_table.c.animal_id == animal_id.value)
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        return self._map_animal(row)

    def find_by_identifier(
        self,
        organization_id: OrganizationId,
        identifier_type: IdentifierType,
        identifier_value: str,
    ) -> Animal | None:
        stmt = select(animal_identifiers_table.c.animal_id).where(
            animal_identifiers_table.c.record_owner_organization_id == organization_id.value,
            animal_identifiers_table.c.identifier_type == identifier_type.value,
            animal_identifiers_table.c.identifier_value == identifier_value,
            animal_identifiers_table.c.state == IdentifierState.ACTIVE.value,
        )
        row = self.connection.execute(stmt).fetchone()
        if row is None:
            return None
        animal_id = TypedId(entity_type="animal", value=row.animal_id)
        return self.get_by_id(animal_id)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Animal]:
        stmt = (
            select(animals_table)
            .where(animals_table.c.record_owner_organization_id == organization_id.value)
            .order_by(animals_table.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self.connection.execute(stmt).fetchall()
        return [self._map_animal(row) for row in rows]

    def _map_animal(self, row: Row[Any]) -> Animal:
        stmt_tags = (
            select(animal_identifiers_table)
            .where(animal_identifiers_table.c.animal_id == row.animal_id)
            .order_by(animal_identifiers_table.c.attached_at.asc())
        )
        tag_rows = self.connection.execute(stmt_tags).fetchall()

        tags = []
        for tag_row in tag_rows:
            attached_at = tag_row.attached_at
            if attached_at.tzinfo is None:
                attached_at = attached_at.replace(tzinfo=UTC)

            deactivated_at = tag_row.deactivated_at
            if deactivated_at is not None and deactivated_at.tzinfo is None:
                deactivated_at = deactivated_at.replace(tzinfo=UTC)

            valid_from = getattr(tag_row, "valid_from", None) or attached_at
            if valid_from.tzinfo is None:
                valid_from = valid_from.replace(tzinfo=UTC)

            valid_until = getattr(tag_row, "valid_until", None) or deactivated_at
            if valid_until is not None and valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=UTC)

            v_status_str = getattr(tag_row, "verification_status", "DECLARADO") or "DECLARADO"

            tags.append(
                AnimalIdentifier(
                    identifier_id=TypedId(
                        entity_type="animal_identifier", value=tag_row.identifier_id
                    ),
                    identifier_type=IdentifierType(tag_row.identifier_type),
                    identifier_value=tag_row.identifier_value,
                    state=IdentifierState(tag_row.state),
                    issuer_source=getattr(tag_row, "issuer_source", None),
                    evidence_reference=getattr(tag_row, "evidence_reference", None),
                    verification_status=VerificationStatus(v_status_str),
                    valid_from=valid_from,
                    valid_until=valid_until,
                    attached_at=attached_at,
                    deactivated_at=deactivated_at,
                )
            )

        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        version = getattr(row, "version", 1) or 1

        return Animal(
            animal_id=TypedId(entity_type="animal", value=row.animal_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            birth_property_id=TypedId(entity_type="rural_property", value=row.birth_property_id),
            sex=AnimalSex(row.sex),
            breed=row.breed,
            birth_date=row.birth_date,
            identifiers=tuple(tags),
            version=version,
            created_at=created_at,
        )
