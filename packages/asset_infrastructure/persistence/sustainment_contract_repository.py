"""Persistência do agregado `SLIContract` — Titan Asset (A3, módulo `sustainment`).

`versions` é append-only por invariante de domínio (I-SLI-3: `ContractVersion`
imutável após emissão — `issue_version` só acrescenta, nunca edita uma versão
existente). `version_no` já é a chave natural da ordem, então `update()` só
insere as versões cujo `version_no` ainda não está persistido — nunca
delete+reinsert (nem precisaria: nada muda depois de emitido).

`coverage_lines` é tabela neta (filha de `contract_versions`, que é filha de
`sli_contracts`); `covered_services`/`covered_parts`/`excluded_parts` são
mapeados como `ARRAY` em vez de uma quarta tabela — mesmo padrão de
`external_classifications` em `part_repository.py`. `covered_parts`/
`excluded_parts` assumem `entity_type="part"` na reconstrução: ao contrário de
`Applicability.asserted_by`, o próprio nome do campo já fixa o tipo lógico
referenciado (usados por `CoverageLine.covers_part(part_ref)`).
"""

from dataclasses import dataclass
from datetime import UTC
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Interval,
    Numeric,
    String,
    Table,
    select,
)
from sqlalchemy import (
    insert as sa_insert,
)
from sqlalchemy import (
    update as sa_update,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.asset_domain.sustainment_contract import (
    SLA,
    ContractScope,
    ContractVersion,
    CoverageLine,
    KnownValidInterval,
    ServiceLimits,
    SLIContract,
)
from packages.asset_infrastructure.persistence.metadata import asset_metadata
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.shared_kernel import OrganizationId, TypedId

sli_contracts_table = Table(
    "sli_contracts",
    asset_metadata,
    Column("contract_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("customer_id", PG_UUID(as_uuid=True), nullable=False),
    Column("version", Integer, nullable=False, default=1),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_sli_contracts_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

contract_versions_table = Table(
    "contract_versions",
    asset_metadata,
    Column("contract_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("version_no", Integer, primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("effective_valid_from", DateTime(timezone=True), nullable=False),
    Column("effective_known_at", DateTime(timezone=True), nullable=False),
    Column("effective_valid_until", DateTime(timezone=True), nullable=True),
    Column("response_sla_duration", Interval, nullable=True),
    Column("response_sla_clock_start_event", String(100), nullable=True),
    Column("response_sla_clock_stop_event", String(100), nullable=True),
    Column("response_sla_pause_conditions", ARRAY(String), nullable=True),
    Column("repair_sla_duration", Interval, nullable=True),
    Column("repair_sla_clock_start_event", String(100), nullable=True),
    Column("repair_sla_clock_stop_event", String(100), nullable=True),
    Column("repair_sla_pause_conditions", ARRAY(String), nullable=True),
    Column("availability_target_percentage", Numeric, nullable=True),
    Column("service_limits_max_services_per_period", Integer, nullable=True),
    Column("service_limits_period_days", Integer, nullable=True),
    Column("amendment_id", PG_UUID(as_uuid=True), nullable=True),
    ForeignKeyConstraint(
        ["contract_id"],
        ["core_audit.sli_contracts.contract_id"],
        name="fk_contract_versions_contract",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

contract_version_coverage_lines_table = Table(
    "contract_version_coverage_lines",
    asset_metadata,
    Column("contract_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("version_no", Integer, primary_key=True),
    Column("ordinal", Integer, primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("scope", String(20), nullable=False),
    Column("scope_value", String(200), nullable=False),
    Column("covered_services", ARRAY(String), nullable=False),
    Column("covered_parts", ARRAY(PG_UUID(as_uuid=True)), nullable=False),
    Column("excluded_parts", ARRAY(PG_UUID(as_uuid=True)), nullable=False),
    Column("labor_rules", String(500), nullable=True),
    Column("travel_rules", String(500), nullable=True),
    ForeignKeyConstraint(
        ["contract_id", "version_no"],
        ["core_audit.contract_versions.contract_id", "core_audit.contract_versions.version_no"],
        name="fk_contract_version_coverage_lines_version",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)


@dataclass(frozen=True, slots=True)
class TransactionalSLIContractRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalSLIContractRepository exige Connection com transação ativa."
            )

    def save(self, contract: SLIContract) -> None:
        self.connection.execute(
            sa_insert(sli_contracts_table).values(
                contract_id=contract.contract_id.value,
                record_owner_organization_id=contract.organization_id.value,
                customer_id=contract.customer_ref.value,
                version=contract.version,
            )
        )
        self._insert_new_versions(contract)

    def update(self, contract: SLIContract) -> None:
        self.connection.execute(
            sa_update(sli_contracts_table)
            .where(sli_contracts_table.c.contract_id == contract.contract_id.value)
            .values(version=contract.version)
        )
        self._insert_new_versions(contract)

    def _insert_new_versions(self, contract: SLIContract) -> None:
        existing = {
            row.version_no
            for row in self.connection.execute(
                select(contract_versions_table.c.version_no).where(
                    contract_versions_table.c.contract_id == contract.contract_id.value
                )
            )
        }
        for contract_version in contract.versions:
            if contract_version.version_no in existing:
                continue
            self._insert_version(contract, contract_version)

    def _insert_version(self, contract: SLIContract, version: ContractVersion) -> None:
        response_sla = version.response_sla
        repair_sla = version.repair_sla
        limits = version.service_limits
        self.connection.execute(
            sa_insert(contract_versions_table).values(
                contract_id=contract.contract_id.value,
                version_no=version.version_no,
                record_owner_organization_id=contract.organization_id.value,
                effective_valid_from=version.effective.valid_from,
                effective_known_at=version.effective.known_at,
                effective_valid_until=version.effective.valid_until,
                response_sla_duration=response_sla.duration if response_sla else None,
                response_sla_clock_start_event=(
                    response_sla.clock_start_event if response_sla else None
                ),
                response_sla_clock_stop_event=(
                    response_sla.clock_stop_event if response_sla else None
                ),
                response_sla_pause_conditions=(
                    list(response_sla.pause_conditions) if response_sla else None
                ),
                repair_sla_duration=repair_sla.duration if repair_sla else None,
                repair_sla_clock_start_event=repair_sla.clock_start_event if repair_sla else None,
                repair_sla_clock_stop_event=repair_sla.clock_stop_event if repair_sla else None,
                repair_sla_pause_conditions=(
                    list(repair_sla.pause_conditions) if repair_sla else None
                ),
                availability_target_percentage=version.availability_target_percentage,
                service_limits_max_services_per_period=(
                    limits.max_services_per_period if limits else None
                ),
                service_limits_period_days=limits.period_days if limits else None,
                amendment_id=version.amendment_ref.value if version.amendment_ref else None,
            )
        )
        for ordinal, line in enumerate(version.coverage_lines):
            self.connection.execute(
                sa_insert(contract_version_coverage_lines_table).values(
                    contract_id=contract.contract_id.value,
                    version_no=version.version_no,
                    ordinal=ordinal,
                    record_owner_organization_id=contract.organization_id.value,
                    scope=line.scope.value,
                    scope_value=line.scope_value,
                    covered_services=list(line.covered_services),
                    covered_parts=[part_ref.value for part_ref in line.covered_parts],
                    excluded_parts=[part_ref.value for part_ref in line.excluded_parts],
                    labor_rules=line.labor_rules,
                    travel_rules=line.travel_rules,
                )
            )

    def get_by_id(self, contract_id: TypedId) -> SLIContract | None:
        row = self.connection.execute(
            select(sli_contracts_table).where(
                sli_contracts_table.c.contract_id == contract_id.value
            )
        ).fetchone()
        if row is None:
            return None
        return self._map(row)

    def _map(self, row: Row[Any]) -> SLIContract:
        version_rows = self.connection.execute(
            select(contract_versions_table)
            .where(contract_versions_table.c.contract_id == row.contract_id)
            .order_by(contract_versions_table.c.version_no)
        ).fetchall()
        versions = tuple(
            self._map_version(row.contract_id, version_row) for version_row in version_rows
        )
        return SLIContract(
            contract_id=TypedId(entity_type="sli_contract", value=row.contract_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            customer_ref=TypedId(entity_type="customer", value=row.customer_id),
            versions=versions,
            version=row.version,
        )

    def _map_version(self, contract_id: Any, version_row: Row[Any]) -> ContractVersion:
        def _tz(value: Any) -> Any:
            if value is not None and value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value

        coverage_rows = self.connection.execute(
            select(contract_version_coverage_lines_table)
            .where(
                contract_version_coverage_lines_table.c.contract_id == contract_id,
                contract_version_coverage_lines_table.c.version_no == version_row.version_no,
            )
            .order_by(contract_version_coverage_lines_table.c.ordinal)
        ).fetchall()
        coverage_lines = tuple(
            CoverageLine(
                scope=ContractScope(coverage_row.scope),
                scope_value=coverage_row.scope_value,
                covered_services=tuple(coverage_row.covered_services or ()),
                covered_parts=tuple(
                    TypedId(entity_type="part", value=part_id)
                    for part_id in (coverage_row.covered_parts or ())
                ),
                excluded_parts=tuple(
                    TypedId(entity_type="part", value=part_id)
                    for part_id in (coverage_row.excluded_parts or ())
                ),
                labor_rules=coverage_row.labor_rules,
                travel_rules=coverage_row.travel_rules,
            )
            for coverage_row in coverage_rows
        )
        response_sla = (
            SLA(
                duration=version_row.response_sla_duration,
                clock_start_event=version_row.response_sla_clock_start_event,
                clock_stop_event=version_row.response_sla_clock_stop_event,
                pause_conditions=tuple(version_row.response_sla_pause_conditions or ()),
            )
            if version_row.response_sla_duration is not None
            else None
        )
        repair_sla = (
            SLA(
                duration=version_row.repair_sla_duration,
                clock_start_event=version_row.repair_sla_clock_start_event,
                clock_stop_event=version_row.repair_sla_clock_stop_event,
                pause_conditions=tuple(version_row.repair_sla_pause_conditions or ()),
            )
            if version_row.repair_sla_duration is not None
            else None
        )
        service_limits = (
            ServiceLimits(
                max_services_per_period=version_row.service_limits_max_services_per_period,
                period_days=version_row.service_limits_period_days,
            )
            if version_row.service_limits_max_services_per_period is not None
            else None
        )
        availability_target = version_row.availability_target_percentage
        return ContractVersion(
            version_no=version_row.version_no,
            effective=KnownValidInterval(
                valid_from=_tz(version_row.effective_valid_from),
                known_at=_tz(version_row.effective_known_at),
                valid_until=_tz(version_row.effective_valid_until),
            ),
            coverage_lines=coverage_lines,
            response_sla=response_sla,
            repair_sla=repair_sla,
            availability_target_percentage=(
                Decimal(availability_target) if availability_target is not None else None
            ),
            service_limits=service_limits,
            amendment_ref=(
                TypedId(entity_type="contract_amendment", value=version_row.amendment_id)
                if version_row.amendment_id is not None
                else None
            ),
        )
