"""Projeção reconstruível de referências reversas em PostgreSQL (Passo 7.2)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_domain.projections import ReferenceRole, ReferencingKind, ReverseReference
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

# A chave primária é o próprio conteúdo derivado, sem identificador sorteado: assim
# reconstruir produz linhas idênticas e a comparação entre reconstruções é exata.
reference_projection_table = Table(
    "reference_projection",
    organization_metadata,
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("referenced_entity_type", String(100), nullable=False),
    Column("referenced_id", PG_UUID(as_uuid=True), nullable=False),
    Column("referenced_contract_version", Integer, nullable=False),
    Column("referencing_kind", String(30), nullable=False),
    Column("referencing_id", PG_UUID(as_uuid=True), nullable=False),
    Column("role", String(30), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint(
        "record_owner_organization_id",
        "referenced_id",
        "referencing_kind",
        "referencing_id",
        "role",
        name="pk_reference_projection",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_reference_projection_organization",
    ),
    Index(
        "ix_reference_projection_referenced",
        "record_owner_organization_id",
        "referenced_id",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

_SELECT_COLUMNS = """
    record_owner_organization_id,
    referenced_entity_type,
    referenced_id,
    referenced_contract_version,
    referencing_kind,
    referencing_id,
    role,
    occurred_at
"""


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


@dataclass(frozen=True, slots=True)
class PostgresProjectionSource:
    """Lê as fontes imutáveis das quais a projeção é derivada."""

    connection: Connection

    def read_event_references(self, organization_id: OrganizationId) -> list[ReverseReference]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    event_id,
                    aggregate_type,
                    aggregate_id,
                    aggregate_contract_version,
                    actor_type,
                    actor_id,
                    actor_contract_version,
                    source_type,
                    source_id,
                    source_contract_version,
                    occurred_at
                FROM core_audit.domain_events
                WHERE record_owner_organization_id = :org_id
                ORDER BY occurred_at ASC, event_id ASC
                """
            ),
            {"org_id": organization_id.value},
        ).fetchall()

        entries: list[ReverseReference] = []
        for row in rows:
            event_id = TypedId(entity_type="domain_event", value=row.event_id)
            occurred_at = _aware(row.occurred_at)
            for entity_type, target_value, contract_version, role in (
                (
                    row.aggregate_type,
                    row.aggregate_id,
                    row.aggregate_contract_version,
                    ReferenceRole.AGGREGATE,
                ),
                (row.actor_type, row.actor_id, row.actor_contract_version, ReferenceRole.ACTOR),
                (row.source_type, row.source_id, row.source_contract_version, ReferenceRole.SOURCE),
            ):
                entries.append(
                    ReverseReference(
                        organization_id=organization_id,
                        referenced=UniversalReference(
                            target_id=TypedId(entity_type=entity_type, value=target_value),
                            organization_id=organization_id,
                            contract_version=contract_version,
                        ),
                        referencing_kind=ReferencingKind.DOMAIN_EVENT,
                        referencing_id=event_id,
                        role=role,
                        occurred_at=occurred_at,
                    )
                )
        return entries

    def read_relation_references(self, organization_id: OrganizationId) -> list[ReverseReference]:
        rows = self.connection.execute(
            text(
                """
                SELECT
                    relation_id,
                    source_entity_type,
                    source_id,
                    source_contract_version,
                    target_entity_type,
                    target_id,
                    target_contract_version,
                    created_at
                FROM core_audit.relations
                WHERE record_owner_organization_id = :org_id
                ORDER BY created_at ASC, relation_id ASC
                """
            ),
            {"org_id": organization_id.value},
        ).fetchall()

        entries: list[ReverseReference] = []
        for row in rows:
            relation_id = TypedId(entity_type="relation", value=row.relation_id)
            created_at = _aware(row.created_at)
            for entity_type, target_value, contract_version, role in (
                (
                    row.source_entity_type,
                    row.source_id,
                    row.source_contract_version,
                    ReferenceRole.RELATION_SOURCE,
                ),
                (
                    row.target_entity_type,
                    row.target_id,
                    row.target_contract_version,
                    ReferenceRole.RELATION_TARGET,
                ),
            ):
                entries.append(
                    ReverseReference(
                        organization_id=organization_id,
                        referenced=UniversalReference(
                            target_id=TypedId(entity_type=entity_type, value=target_value),
                            organization_id=organization_id,
                            contract_version=contract_version,
                        ),
                        referencing_kind=ReferencingKind.RELATION,
                        referencing_id=relation_id,
                        role=role,
                        occurred_at=created_at,
                    )
                )
        return entries


@dataclass(frozen=True, slots=True)
class TransactionalProjectionRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalProjectionRepository exige transacao ativa.")

    def clear(self, organization_id: OrganizationId) -> None:
        self.connection.execute(
            text(
                """
                DELETE FROM core_audit.reference_projection
                WHERE record_owner_organization_id = :org_id
                """
            ),
            {"org_id": organization_id.value},
        )

    def replace_all(self, organization_id: OrganizationId, entries: list[ReverseReference]) -> None:
        # Projeção é descartável por definição: apagar e regravar é a operação
        # normal, e não uma perda de dado.
        self.clear(organization_id)
        if not entries:
            return

        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.reference_projection (
                    record_owner_organization_id,
                    referenced_entity_type,
                    referenced_id,
                    referenced_contract_version,
                    referencing_kind,
                    referencing_id,
                    role,
                    occurred_at
                ) VALUES (
                    :org_id,
                    :referenced_entity_type,
                    :referenced_id,
                    :referenced_contract_version,
                    :referencing_kind,
                    :referencing_id,
                    :role,
                    :occurred_at
                )
                ON CONFLICT ON CONSTRAINT pk_reference_projection DO NOTHING
                """
            ),
            [
                {
                    "org_id": e.organization_id.value,
                    "referenced_entity_type": e.referenced.target_id.entity_type,
                    "referenced_id": e.referenced.target_id.value,
                    "referenced_contract_version": e.referenced.contract_version,
                    "referencing_kind": e.referencing_kind.value,
                    "referencing_id": e.referencing_id.value,
                    "role": e.role.value,
                    "occurred_at": e.occurred_at,
                }
                for e in entries
            ],
        )

    def list_all(self, organization_id: OrganizationId) -> list[ReverseReference]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.reference_projection
                WHERE record_owner_organization_id = :org_id
                ORDER BY referenced_entity_type, referenced_id, referencing_kind,
                         referencing_id, role
                """
            ),
            {"org_id": organization_id.value},
        ).fetchall()
        return [self._map_row(row) for row in rows]

    def list_referencing(
        self, organization_id: OrganizationId, referenced: UniversalReference
    ) -> list[ReverseReference]:
        rows = self.connection.execute(
            text(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM core_audit.reference_projection
                WHERE record_owner_organization_id = :org_id
                  AND referenced_id = :referenced_id
                ORDER BY occurred_at ASC, referencing_kind, referencing_id, role
                """
            ),
            {
                "org_id": organization_id.value,
                "referenced_id": referenced.target_id.value,
            },
        ).fetchall()
        return [self._map_row(row) for row in rows]

    def _map_row(self, row: object) -> ReverseReference:
        organization_id = OrganizationId(row.record_owner_organization_id)  # type: ignore[attr-defined]
        return ReverseReference(
            organization_id=organization_id,
            referenced=UniversalReference(
                target_id=TypedId(
                    entity_type=row.referenced_entity_type,  # type: ignore[attr-defined]
                    value=row.referenced_id,  # type: ignore[attr-defined]
                ),
                organization_id=organization_id,
                contract_version=row.referenced_contract_version,  # type: ignore[attr-defined]
            ),
            referencing_kind=ReferencingKind(row.referencing_kind),  # type: ignore[attr-defined]
            referencing_id=TypedId(
                entity_type=row.referencing_kind,  # type: ignore[attr-defined]
                value=row.referencing_id,  # type: ignore[attr-defined]
            ),
            role=ReferenceRole(row.role),  # type: ignore[attr-defined]
            occurred_at=_aware(row.occurred_at),  # type: ignore[attr-defined]
        )
