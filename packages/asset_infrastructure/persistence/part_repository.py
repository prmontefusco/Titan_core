"""Persistência dos agregados `Part` e `InterchangeabilityGroup` — Titan Asset (A3).

`Part.revisions`/`Part.supersessions` e `InterchangeabilityGroup.member_part_revisions`
são tuplas ordenadas — cada tabela filha usa `position` para preservar a ordem
(mesma técnica de `customer_site_contacts_table`). `external_classifications`/
`materials` são listas simples de string, mapeadas como `ARRAY` (mesmo padrão de
`livestock_infrastructure/persistence/medication_classification_repository.py`).

Ordem de criação das tabelas importa: `interchangeability_groups` antes de
`parts` (FK), `parts` antes de `part_revisions` (FK), `part_revisions` antes de
`part_supersessions`/`interchangeability_group_members` (FK).
"""

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Row

from packages.asset_domain.part import (
    InterchangeabilityGroup,
    Part,
    PartIdentity,
    PartLifecycleState,
    PartRevision,
    Supersession,
)
from packages.asset_infrastructure.persistence.metadata import asset_metadata
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.shared_kernel import OrganizationId, TypedId

interchangeability_groups_table = Table(
    "interchangeability_groups",
    asset_metadata,
    Column("group_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("version", Integer, nullable=False, default=1),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_interchangeability_groups_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

parts_table = Table(
    "parts",
    asset_metadata,
    Column("part_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("part_number", String(100), nullable=False),
    Column("description", String(500), nullable=False),
    Column("manufacturer", String(200), nullable=False),
    Column("manufacturer_pn", String(100), nullable=True),
    Column("nsn", String(50), nullable=True),
    Column("external_classifications", ARRAY(String), nullable=False, default=list),
    Column("interchangeability_group_id", PG_UUID(as_uuid=True), nullable=True),
    Column("version", Integer, nullable=False, default=1),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_parts_organization",
    ),
    ForeignKeyConstraint(
        ["interchangeability_group_id"],
        ["core_audit.interchangeability_groups.group_id"],
        name="fk_parts_interchangeability_group",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

part_revisions_table = Table(
    "part_revisions",
    asset_metadata,
    Column("revision_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("part_id", PG_UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("revision_code", String(50), nullable=False),
    Column("lifecycle_state", String(20), nullable=False),
    Column("spec_ref", PG_UUID(as_uuid=True), nullable=True),
    Column("drawing_ref", PG_UUID(as_uuid=True), nullable=True),
    Column("materials", ARRAY(String), nullable=False, default=list),
    ForeignKeyConstraint(["part_id"], ["core_audit.parts.part_id"], name="fk_part_revisions_part"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

part_supersessions_table = Table(
    "part_supersessions",
    asset_metadata,
    Column("part_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("predecessor_revision_id", PG_UUID(as_uuid=True), nullable=False),
    Column("successor_revision_id", PG_UUID(as_uuid=True), nullable=False),
    Column("reason", String(500), nullable=False),
    ForeignKeyConstraint(
        ["part_id"], ["core_audit.parts.part_id"], name="fk_part_supersessions_part"
    ),
    ForeignKeyConstraint(
        ["predecessor_revision_id"],
        ["core_audit.part_revisions.revision_id"],
        name="fk_part_supersessions_predecessor",
    ),
    ForeignKeyConstraint(
        ["successor_revision_id"],
        ["core_audit.part_revisions.revision_id"],
        name="fk_part_supersessions_successor",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

interchangeability_group_members_table = Table(
    "interchangeability_group_members",
    asset_metadata,
    Column("group_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("part_revision_id", PG_UUID(as_uuid=True), nullable=False),
    ForeignKeyConstraint(
        ["group_id"],
        ["core_audit.interchangeability_groups.group_id"],
        name="fk_interchangeability_group_members_group",
    ),
    ForeignKeyConstraint(
        ["part_revision_id"],
        ["core_audit.part_revisions.revision_id"],
        name="fk_interchangeability_group_members_revision",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)


@dataclass(frozen=True, slots=True)
class TransactionalPartRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalPartRepository exige Connection com transação ativa.")

    def save(self, part: Part) -> None:
        self.connection.execute(
            insert(parts_table).values(
                part_id=part.part_id.value,
                record_owner_organization_id=part.organization_id.value,
                part_number=part.identity.part_number,
                description=part.identity.description,
                manufacturer=part.identity.manufacturer,
                manufacturer_pn=part.identity.manufacturer_pn,
                nsn=part.identity.nsn,
                external_classifications=list(part.identity.external_classifications),
                interchangeability_group_id=(
                    part.interchangeability_group_ref.value
                    if part.interchangeability_group_ref is not None
                    else None
                ),
                version=part.version,
                created_at=part.created_at,
            )
        )
        self._insert_revisions(part)
        self._insert_supersessions(part)

    def update(self, part: Part) -> None:
        self.connection.execute(
            update(parts_table)
            .where(parts_table.c.part_id == part.part_id.value)
            .values(
                interchangeability_group_id=(
                    part.interchangeability_group_ref.value
                    if part.interchangeability_group_ref is not None
                    else None
                ),
                version=part.version,
            )
        )
        self.connection.execute(
            delete(part_supersessions_table).where(
                part_supersessions_table.c.part_id == part.part_id.value
            )
        )
        self._upsert_revisions(part)
        self._insert_supersessions(part)

    def _insert_revisions(self, part: Part) -> None:
        for revision in part.revisions:
            self.connection.execute(
                insert(part_revisions_table).values(
                    revision_id=revision.revision_id.value,
                    part_id=part.part_id.value,
                    record_owner_organization_id=part.organization_id.value,
                    revision_code=revision.revision_code,
                    lifecycle_state=revision.lifecycle_state.value,
                    spec_ref=revision.spec_ref.value if revision.spec_ref is not None else None,
                    drawing_ref=(
                        revision.drawing_ref.value if revision.drawing_ref is not None else None
                    ),
                    materials=list(revision.materials),
                )
            )

    def _upsert_revisions(self, part: Part) -> None:
        """`revision_id` é estável ao longo da vida de um `Part` — nunca
        regenerado por `add_revision`/`supersede_revision`. Delete+reinsert
        (como `customer_site_contacts`) violaria a FK de
        `interchangeability_group_members` sempre que uma revisão já membro de
        um grupo continuasse existindo após o update; por isso aqui é upsert
        por `revision_id`, e só remove as que de fato saíram da tupla."""
        current_ids = {revision.revision_id.value for revision in part.revisions}
        existing_ids = {
            row.revision_id
            for row in self.connection.execute(
                select(part_revisions_table.c.revision_id).where(
                    part_revisions_table.c.part_id == part.part_id.value
                )
            )
        }
        removed_ids = existing_ids - current_ids
        if removed_ids:
            self.connection.execute(
                delete(part_revisions_table).where(
                    part_revisions_table.c.revision_id.in_(removed_ids)
                )
            )
        for revision in part.revisions:
            stmt = pg_insert(part_revisions_table).values(
                revision_id=revision.revision_id.value,
                part_id=part.part_id.value,
                record_owner_organization_id=part.organization_id.value,
                revision_code=revision.revision_code,
                lifecycle_state=revision.lifecycle_state.value,
                spec_ref=revision.spec_ref.value if revision.spec_ref is not None else None,
                drawing_ref=(
                    revision.drawing_ref.value if revision.drawing_ref is not None else None
                ),
                materials=list(revision.materials),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[part_revisions_table.c.revision_id],
                set_={
                    "lifecycle_state": stmt.excluded.lifecycle_state,
                    "spec_ref": stmt.excluded.spec_ref,
                    "drawing_ref": stmt.excluded.drawing_ref,
                    "materials": stmt.excluded.materials,
                },
            )
            self.connection.execute(stmt)

    def _insert_supersessions(self, part: Part) -> None:
        for position, edge in enumerate(part.supersessions):
            self.connection.execute(
                insert(part_supersessions_table).values(
                    part_id=part.part_id.value,
                    position=position,
                    record_owner_organization_id=part.organization_id.value,
                    predecessor_revision_id=edge.predecessor_revision_id.value,
                    successor_revision_id=edge.successor_revision_id.value,
                    reason=edge.reason,
                )
            )

    def get_by_id(self, part_id: TypedId) -> Part | None:
        row = self.connection.execute(
            select(parts_table).where(parts_table.c.part_id == part_id.value)
        ).fetchone()
        if row is None:
            return None
        return self._map(row)

    def _map(self, row: Row[Any]) -> Part:
        revision_rows = self.connection.execute(
            select(part_revisions_table).where(part_revisions_table.c.part_id == row.part_id)
        ).fetchall()
        revisions = tuple(
            PartRevision(
                revision_id=TypedId(entity_type="part_revision", value=revision_row.revision_id),
                revision_code=revision_row.revision_code,
                lifecycle_state=PartLifecycleState(revision_row.lifecycle_state),
                spec_ref=(
                    TypedId(entity_type="spec", value=revision_row.spec_ref)
                    if revision_row.spec_ref is not None
                    else None
                ),
                drawing_ref=(
                    TypedId(entity_type="drawing", value=revision_row.drawing_ref)
                    if revision_row.drawing_ref is not None
                    else None
                ),
                materials=tuple(revision_row.materials or ()),
            )
            for revision_row in revision_rows
        )
        supersession_rows = self.connection.execute(
            select(part_supersessions_table)
            .where(part_supersessions_table.c.part_id == row.part_id)
            .order_by(part_supersessions_table.c.position)
        ).fetchall()
        supersessions = tuple(
            Supersession(
                predecessor_revision_id=TypedId(
                    entity_type="part_revision", value=supersession_row.predecessor_revision_id
                ),
                successor_revision_id=TypedId(
                    entity_type="part_revision", value=supersession_row.successor_revision_id
                ),
                reason=supersession_row.reason,
            )
            for supersession_row in supersession_rows
        )
        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        return Part(
            part_id=TypedId(entity_type="part", value=row.part_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            identity=PartIdentity(
                part_number=row.part_number,
                description=row.description,
                manufacturer=row.manufacturer,
                manufacturer_pn=row.manufacturer_pn,
                nsn=row.nsn,
                external_classifications=tuple(row.external_classifications or ()),
            ),
            revisions=revisions,
            supersessions=supersessions,
            interchangeability_group_ref=(
                TypedId(
                    entity_type="interchangeability_group",
                    value=row.interchangeability_group_id,
                )
                if row.interchangeability_group_id is not None
                else None
            ),
            version=row.version,
            created_at=created_at,
        )


@dataclass(frozen=True, slots=True)
class TransactionalInterchangeabilityGroupRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalInterchangeabilityGroupRepository exige "
                "Connection com transação ativa."
            )

    def save(self, group: InterchangeabilityGroup) -> None:
        self.connection.execute(
            insert(interchangeability_groups_table).values(
                group_id=group.group_id.value,
                record_owner_organization_id=group.organization_id.value,
                version=group.version,
            )
        )
        self._insert_members(group)

    def update(self, group: InterchangeabilityGroup) -> None:
        self.connection.execute(
            update(interchangeability_groups_table)
            .where(interchangeability_groups_table.c.group_id == group.group_id.value)
            .values(version=group.version)
        )
        self.connection.execute(
            delete(interchangeability_group_members_table).where(
                interchangeability_group_members_table.c.group_id == group.group_id.value
            )
        )
        self._insert_members(group)

    def _insert_members(self, group: InterchangeabilityGroup) -> None:
        for position, member_ref in enumerate(group.member_part_revisions):
            self.connection.execute(
                insert(interchangeability_group_members_table).values(
                    group_id=group.group_id.value,
                    position=position,
                    record_owner_organization_id=group.organization_id.value,
                    part_revision_id=member_ref.value,
                )
            )

    def get_by_id(self, group_id: TypedId) -> InterchangeabilityGroup | None:
        row = self.connection.execute(
            select(interchangeability_groups_table).where(
                interchangeability_groups_table.c.group_id == group_id.value
            )
        ).fetchone()
        if row is None:
            return None
        member_rows = self.connection.execute(
            select(interchangeability_group_members_table)
            .where(interchangeability_group_members_table.c.group_id == row.group_id)
            .order_by(interchangeability_group_members_table.c.position)
        ).fetchall()
        members = tuple(
            TypedId(entity_type="part_revision", value=member_row.part_revision_id)
            for member_row in member_rows
        )
        return InterchangeabilityGroup(
            group_id=TypedId(entity_type="interchangeability_group", value=row.group_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            member_part_revisions=members,
            version=row.version,
        )
