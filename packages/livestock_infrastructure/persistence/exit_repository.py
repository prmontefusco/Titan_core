"""Persistência da saída do animal (Passo 13.1 - Titan Livestock)."""

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
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.exit_service import AnimalExitRepositoryPort
from packages.livestock_domain.exit import AnimalExit, ExitType
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

animal_exits_table = Table(
    "animal_exits",
    livestock_metadata,
    Column("exit_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("animal_id", PG_UUID(as_uuid=True), nullable=False),
    Column("exit_type", String(40), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("reason", String(500), nullable=True),
    Column("destination", String(255), nullable=True),
    Column("evidence_references", JSONB, nullable=False, server_default="[]"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_animal_exits_organization",
    ),
    ForeignKeyConstraint(
        ["animal_id"],
        ["core_audit.animals.animal_id"],
        name="fk_animal_exits_animal",
    ),
    # Sair é terminal: o banco recusa a segunda saída mesmo que o serviço falhe
    # em conferir. Invariante que só a aplicação garante é invariante que se perde
    # na primeira execução concorrente.
    UniqueConstraint("animal_id", name="uq_animal_exits_animal"),
    schema=CORE_AUDIT_SCHEMA,
)


@dataclass(frozen=True, slots=True)
class TransactionalAnimalExitRepository(AnimalExitRepositoryPort):
    connection: Connection

    def save(self, exit_record: AnimalExit) -> None:
        self.connection.execute(
            insert(animal_exits_table).values(
                exit_id=exit_record.exit_id.value,
                record_owner_organization_id=exit_record.organization_id.value,
                animal_id=exit_record.animal_id.value,
                exit_type=exit_record.exit_type.value,
                occurred_at=exit_record.occurred_at,
                reason=exit_record.reason,
                destination=exit_record.destination,
                evidence_references=json.dumps(
                    [reference_to_dict(r) for r in exit_record.evidence_references]
                ),
                created_at=exit_record.created_at,
            )
        )

    def get_by_animal(self, animal_id: TypedId) -> AnimalExit | None:
        row = self.connection.execute(
            select(animal_exits_table).where(animal_exits_table.c.animal_id == animal_id.value)
        ).one_or_none()
        return None if row is None else self._map(row)

    def _map(self, row: Row[Any]) -> AnimalExit:
        def _aware(value: datetime) -> datetime:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        bruto = row.evidence_references
        referencias = json.loads(bruto) if isinstance(bruto, str) else (bruto or [])

        return AnimalExit(
            exit_id=TypedId(entity_type="animal_exit", value=row.exit_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            animal_id=TypedId(entity_type="animal", value=row.animal_id),
            exit_type=ExitType(row.exit_type),
            occurred_at=_aware(row.occurred_at),
            reason=row.reason,
            destination=row.destination,
            evidence_references=tuple(
                referencia
                for referencia in (reference_from_dict(item) for item in referencias)
                if referencia is not None
            ),
            created_at=_aware(row.created_at),
        )
