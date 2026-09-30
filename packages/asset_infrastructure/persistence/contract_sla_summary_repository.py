"""Repositório de leitura do `ContractSLASummary` — Titan Asset A6.

Reconstrói o snapshot de contrato a partir de `SLIContract`, `Vehicle` e
`WorkOrder` persistidos. Não materializa SLA agregado em tabela própria; a
interpretação de sinais permanece na aplicação.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Connection, Select, select

from packages.asset_application.contract_sla_summary import ContractSLASummarySnapshot
from packages.asset_domain.sustainment_contract import ContractScope, ContractVersion, CoverageLine
from packages.asset_domain.work_order import TERMINAL_STATES, WorkOrder
from packages.asset_infrastructure.persistence.sustainment_contract_repository import (
    TransactionalSLIContractRepository,
)
from packages.asset_infrastructure.persistence.vehicle_repository import vehicles_table
from packages.asset_infrastructure.persistence.work_order_repository import (
    TransactionalWorkOrderRepository,
    work_orders_table,
)
from packages.shared_kernel import TypedId
from packages.shared_kernel.temporal import require_utc


@dataclass(frozen=True, slots=True)
class _VehicleCoverageCandidate:
    vehicle_id: UUID
    model_id: UUID
    site_id: UUID | None


def _covered_vehicle_refs(
    candidates: tuple[_VehicleCoverageCandidate, ...], version: ContractVersion | None
) -> tuple[TypedId, ...]:
    if version is None:
        return ()
    covered: list[TypedId] = []
    seen: set[UUID] = set()
    for candidate in candidates:
        if candidate.vehicle_id in seen:
            continue
        if any(_coverage_line_matches(line, candidate) for line in version.coverage_lines):
            covered.append(TypedId(entity_type="vehicle", value=candidate.vehicle_id))
            seen.add(candidate.vehicle_id)
    return tuple(covered)


def _coverage_line_matches(line: CoverageLine, candidate: _VehicleCoverageCandidate) -> bool:
    if line.scope is ContractScope.VEHICLE:
        return line.scope_value == str(candidate.vehicle_id)
    if line.scope is ContractScope.SITE and candidate.site_id is not None:
        return line.scope_value == str(candidate.site_id)
    if line.scope is ContractScope.MODEL:
        return line.scope_value == str(candidate.model_id)
    return False


@dataclass(frozen=True, slots=True)
class TransactionalContractSLASummaryRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalContractSLASummaryRepository exige Connection com transação ativa."
            )

    def get_summary_snapshot(
        self, *, contract_ref: TypedId, as_of: datetime | None = None
    ) -> ContractSLASummarySnapshot | None:
        if as_of is not None:
            require_utc(as_of, field_name="as_of")
        contract_repository = TransactionalSLIContractRepository(connection=self.connection)
        contract = contract_repository.get_by_id(contract_ref)
        if contract is None:
            return None
        version = (
            contract.resolve_version_at(as_of)
            if as_of is not None
            else (contract.versions[-1] if contract.versions else None)
        )
        return ContractSLASummarySnapshot(
            contract=contract,
            covered_vehicle_refs=_covered_vehicle_refs(self._vehicle_candidates(), version),
            open_work_orders=self._open_work_orders(contract_ref),
            as_of=as_of,
        )

    def _vehicle_candidates(self) -> tuple[_VehicleCoverageCandidate, ...]:
        rows = self.connection.execute(_vehicle_candidates_statement()).fetchall()
        return tuple(
            _VehicleCoverageCandidate(
                vehicle_id=row.vehicle_id,
                model_id=row.model_id,
                site_id=row.site_id,
            )
            for row in rows
        )

    def _open_work_orders(self, contract_ref: TypedId) -> tuple[WorkOrder, ...]:
        rows = self.connection.execute(
            _open_work_orders_for_contract_statement(contract_ref)
        ).fetchall()
        work_order_repository = TransactionalWorkOrderRepository(connection=self.connection)
        work_orders: list[WorkOrder] = []
        for row in rows:
            work_order = work_order_repository.get_by_id(
                TypedId(entity_type="work_order", value=row.work_order_id)
            )
            if work_order is not None:
                work_orders.append(work_order)
        return tuple(work_orders)


def _vehicle_candidates_statement() -> Select[tuple[object, object, object]]:
    return select(
        vehicles_table.c.vehicle_id,
        vehicles_table.c.model_id,
        vehicles_table.c.site_id,
    ).order_by(vehicles_table.c.vehicle_id)


def _open_work_orders_for_contract_statement(contract_ref: TypedId) -> Select[tuple[object]]:
    return (
        select(work_orders_table.c.work_order_id)
        .where(
            work_orders_table.c.contract_ref_id == contract_ref.value,
            work_orders_table.c.state.not_in([state.value for state in TERMINAL_STATES]),
        )
        .order_by(work_orders_table.c.priority_score.desc().nullslast())
    )
