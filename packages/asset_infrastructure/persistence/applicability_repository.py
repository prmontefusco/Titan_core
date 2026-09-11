"""Persistência do agregado `Applicability` — Titan Asset (A3).

Sem tabela filha: `target` (VO `ApplicabilityTarget`) é embutido como colunas
`target_*` na própria tabela (não é uma coleção, é um único VO por instância).
`evidence_ref`/`asserted_by` não ganham FK — são referências opacas para fora
da vertical (evidência/ator são do Core; `DEPENDENCY_RULES.md` §5 não exige
FK real para isso, só o `entity_type` validado no domínio).
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
    select,
    update,
)
from sqlalchemy import (
    insert as sa_insert,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.asset_domain.applicability import (
    Applicability,
    ApplicabilityState,
    ApplicabilityTarget,
)
from packages.asset_infrastructure.persistence.metadata import asset_metadata
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.shared_kernel import OrganizationId, TypedId

applicability_table = Table(
    "applicability",
    asset_metadata,
    Column("applicability_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("part_id", PG_UUID(as_uuid=True), nullable=False),
    Column("part_revision_id", PG_UUID(as_uuid=True), nullable=False),
    Column("target_model_id", PG_UUID(as_uuid=True), nullable=False),
    Column("target_variant_id", PG_UUID(as_uuid=True), nullable=True),
    Column("target_serial_from", String(100), nullable=True),
    Column("target_serial_to", String(100), nullable=True),
    Column("target_valid_from", DateTime(timezone=True), nullable=False),
    Column("target_valid_until", DateTime(timezone=True), nullable=True),
    Column("evidence_id", PG_UUID(as_uuid=True), nullable=False),
    Column("asserted_at", DateTime(timezone=True), nullable=False),
    Column("asserted_by_id", PG_UUID(as_uuid=True), nullable=False),
    # `Applicability.asserted_by` não tem `entity_type` fixo validado pelo
    # domínio (ao contrário de `evidence_ref`/`part_ref`/...) — persistir o
    # `entity_type` explicitamente evita reconstruir com um valor adivinhado
    # que corromperia silenciosamente o round-trip do `TypedId`.
    Column("asserted_by_entity_type", String(100), nullable=False),
    Column("state", String(20), nullable=False),
    Column("withdrawal_reason", String(500), nullable=True),
    Column("withdrawn_at", DateTime(timezone=True), nullable=True),
    Column("version", Integer, nullable=False, default=1),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_applicability_organization",
    ),
    ForeignKeyConstraint(["part_id"], ["core_audit.parts.part_id"], name="fk_applicability_part"),
    ForeignKeyConstraint(
        ["part_revision_id"],
        ["core_audit.part_revisions.revision_id"],
        name="fk_applicability_part_revision",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)


@dataclass(frozen=True, slots=True)
class TransactionalApplicabilityRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalApplicabilityRepository exige Connection com transação ativa."
            )

    def save(self, applicability: Applicability) -> None:
        self.connection.execute(
            sa_insert(applicability_table).values(**self._values(applicability))
        )

    def update(self, applicability: Applicability) -> None:
        self.connection.execute(
            update(applicability_table)
            .where(applicability_table.c.applicability_id == applicability.applicability_id.value)
            .values(**self._values(applicability, include_id=False))
        )

    def _values(self, applicability: Applicability, *, include_id: bool = True) -> dict[str, Any]:
        target = applicability.target
        values: dict[str, Any] = {
            "record_owner_organization_id": applicability.organization_id.value,
            "part_id": applicability.part_ref.value,
            "part_revision_id": applicability.part_revision_ref.value,
            "target_model_id": target.model_ref.value,
            "target_variant_id": target.variant_ref.value if target.variant_ref else None,
            "target_serial_from": target.serial_from,
            "target_serial_to": target.serial_to,
            "target_valid_from": target.valid_from,
            "target_valid_until": target.valid_until,
            "evidence_id": applicability.evidence_ref.value,
            "asserted_at": applicability.asserted_at,
            "asserted_by_id": applicability.asserted_by.value,
            "asserted_by_entity_type": applicability.asserted_by.entity_type,
            "state": applicability.state.value,
            "withdrawal_reason": applicability.withdrawal_reason,
            "withdrawn_at": applicability.withdrawn_at,
            "version": applicability.version,
        }
        if include_id:
            values["applicability_id"] = applicability.applicability_id.value
        return values

    def get_by_id(self, applicability_id: TypedId) -> Applicability | None:
        row = self.connection.execute(
            select(applicability_table).where(
                applicability_table.c.applicability_id == applicability_id.value
            )
        ).fetchone()
        if row is None:
            return None
        return self._map(row)

    def _map(self, row: Row[Any]) -> Applicability:
        def _tz(value: Any) -> Any:
            if value is not None and value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value

        target = ApplicabilityTarget(
            model_ref=TypedId(entity_type="vehicle_model", value=row.target_model_id),
            variant_ref=(
                TypedId(entity_type="vehicle_variant", value=row.target_variant_id)
                if row.target_variant_id is not None
                else None
            ),
            serial_from=row.target_serial_from,
            serial_to=row.target_serial_to,
            valid_from=_tz(row.target_valid_from),
            valid_until=_tz(row.target_valid_until),
        )
        return Applicability(
            applicability_id=TypedId(entity_type="applicability", value=row.applicability_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            part_ref=TypedId(entity_type="part", value=row.part_id),
            part_revision_ref=TypedId(entity_type="part_revision", value=row.part_revision_id),
            target=target,
            evidence_ref=TypedId(entity_type="evidence", value=row.evidence_id),
            asserted_at=_tz(row.asserted_at),
            asserted_by=TypedId(entity_type=row.asserted_by_entity_type, value=row.asserted_by_id),
            state=ApplicabilityState(row.state),
            withdrawal_reason=row.withdrawal_reason,
            withdrawn_at=_tz(row.withdrawn_at),
            version=row.version,
        )
