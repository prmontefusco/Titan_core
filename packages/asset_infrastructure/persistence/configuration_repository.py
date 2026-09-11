"""Persistência do agregado `ConfigurationBaseline` — Titan Asset (A3).

Publicada uma vez e imutável (nenhum método do domínio retorna uma nova
instância do mesmo `baseline_id` — correções/supersessão criam outra baseline,
referenciando esta por `revision.supersedes_ref`). Por isso o repositório só
tem `save`/`get_by_id`, sem `update` — não há operação de domínio que o exija.

`positions` é tabela filha com `ordinal` para preservar a ordem da tupla
(mesma técnica de `customer_site_contacts`). `revision`/`effectivity` são VOs
únicos por instância, embutidos como colunas (mesmo padrão de `Applicability.target`).
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
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.asset_domain.configuration import (
    BaselinePosition,
    ConfigurationBaseline,
    ConfigurationRevision,
    ConfigurationView,
    Effectivity,
)
from packages.asset_infrastructure.persistence.metadata import asset_metadata
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.shared_kernel import OrganizationId, TypedId

configuration_baselines_table = Table(
    "configuration_baselines",
    asset_metadata,
    Column("baseline_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("model_id", PG_UUID(as_uuid=True), nullable=False),
    Column("variant_id", PG_UUID(as_uuid=True), nullable=True),
    Column("revision_number", Integer, nullable=False),
    Column("supersedes_id", PG_UUID(as_uuid=True), nullable=True),
    Column("effectivity_valid_from", DateTime(timezone=True), nullable=False),
    Column("effectivity_valid_to", DateTime(timezone=True), nullable=True),
    Column("effectivity_serial_from", String(100), nullable=True),
    Column("effectivity_serial_to", String(100), nullable=True),
    Column("view", String(20), nullable=False),
    Column("version", Integer, nullable=False, default=1),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_configuration_baselines_organization",
    ),
    ForeignKeyConstraint(
        ["supersedes_id"],
        ["core_audit.configuration_baselines.baseline_id"],
        name="fk_configuration_baselines_supersedes",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

configuration_baseline_positions_table = Table(
    "configuration_baseline_positions",
    asset_metadata,
    Column("baseline_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("ordinal", Integer, primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("position_code", String(100), nullable=False),
    Column("part_id", PG_UUID(as_uuid=True), nullable=False),
    Column("part_revision_id", PG_UUID(as_uuid=True), nullable=False),
    ForeignKeyConstraint(
        ["baseline_id"],
        ["core_audit.configuration_baselines.baseline_id"],
        name="fk_configuration_baseline_positions_baseline",
    ),
    ForeignKeyConstraint(
        ["part_id"], ["core_audit.parts.part_id"], name="fk_configuration_baseline_positions_part"
    ),
    ForeignKeyConstraint(
        ["part_revision_id"],
        ["core_audit.part_revisions.revision_id"],
        name="fk_configuration_baseline_positions_revision",
    ),
    UniqueConstraint(
        "baseline_id", "position_code", name="uq_configuration_baseline_positions_code"
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)


@dataclass(frozen=True, slots=True)
class TransactionalConfigurationBaselineRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalConfigurationBaselineRepository exige Connection com transação ativa."
            )

    def save(self, baseline: ConfigurationBaseline) -> None:
        self.connection.execute(
            insert(configuration_baselines_table).values(
                baseline_id=baseline.baseline_id.value,
                record_owner_organization_id=baseline.organization_id.value,
                model_id=baseline.model_ref.value,
                variant_id=baseline.variant_ref.value if baseline.variant_ref else None,
                revision_number=baseline.revision.number,
                supersedes_id=(
                    baseline.revision.supersedes_ref.value
                    if baseline.revision.supersedes_ref is not None
                    else None
                ),
                effectivity_valid_from=baseline.effectivity.valid_from,
                effectivity_valid_to=baseline.effectivity.valid_to,
                effectivity_serial_from=baseline.effectivity.serial_from,
                effectivity_serial_to=baseline.effectivity.serial_to,
                view=baseline.view.value,
                version=baseline.version,
                created_at=baseline.created_at,
            )
        )
        for ordinal, position in enumerate(baseline.positions):
            self.connection.execute(
                insert(configuration_baseline_positions_table).values(
                    baseline_id=baseline.baseline_id.value,
                    ordinal=ordinal,
                    record_owner_organization_id=baseline.organization_id.value,
                    position_code=position.position_code,
                    part_id=position.part_ref.value,
                    part_revision_id=position.part_revision_ref.value,
                )
            )

    def get_by_id(self, baseline_id: TypedId) -> ConfigurationBaseline | None:
        row = self.connection.execute(
            select(configuration_baselines_table).where(
                configuration_baselines_table.c.baseline_id == baseline_id.value
            )
        ).fetchone()
        if row is None:
            return None
        return self._map(row)

    def _map(self, row: Row[Any]) -> ConfigurationBaseline:
        def _tz(value: Any) -> Any:
            if value is not None and value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value

        position_rows = self.connection.execute(
            select(configuration_baseline_positions_table)
            .where(configuration_baseline_positions_table.c.baseline_id == row.baseline_id)
            .order_by(configuration_baseline_positions_table.c.ordinal)
        ).fetchall()
        positions = tuple(
            BaselinePosition(
                position_code=position_row.position_code,
                part_ref=TypedId(entity_type="part", value=position_row.part_id),
                part_revision_ref=TypedId(
                    entity_type="part_revision", value=position_row.part_revision_id
                ),
            )
            for position_row in position_rows
        )
        return ConfigurationBaseline(
            baseline_id=TypedId(entity_type="configuration_baseline", value=row.baseline_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            model_ref=TypedId(entity_type="vehicle_model", value=row.model_id),
            revision=ConfigurationRevision(
                number=row.revision_number,
                supersedes_ref=(
                    TypedId(entity_type="configuration_baseline", value=row.supersedes_id)
                    if row.supersedes_id is not None
                    else None
                ),
            ),
            effectivity=Effectivity(
                valid_from=_tz(row.effectivity_valid_from),
                valid_to=_tz(row.effectivity_valid_to),
                serial_from=row.effectivity_serial_from,
                serial_to=row.effectivity_serial_to,
            ),
            positions=positions,
            variant_ref=(
                TypedId(entity_type="vehicle_variant", value=row.variant_id)
                if row.variant_id is not None
                else None
            ),
            view=ConfigurationView(row.view),
            version=row.version,
            created_at=_tz(row.created_at),
        )
