"""Read model de SLA por contrato — Titan Asset A6.

`GetContractSLASummary(contract_ref)` (`docs/asset/09_COMMAND_MODEL.md`) é uma
projection de leitura: agrega frota coberta, WOs abertas e sinais operacionais
de SLA sob um contrato. Não calcula violação contratual real porque o slice
atual ainda não possui timestamps de relógio de SLA suficientes para medir
`clock_start_event`/`clock_stop_event`; por isso este módulo fala em risco/sinal,
não em breach.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from packages.asset_domain.sustainment_contract import ContractVersion, SLIContract
from packages.asset_domain.work_order import TERMINAL_STATES, WorkOrder, WorkOrderState
from packages.shared_kernel import TypedId
from packages.shared_kernel.temporal import require_utc

SLA_RISK_THRESHOLD = 80


class ContractSLAOperationalSignal(StrEnum):
    WAITING_MATERIAL = "WAITING_MATERIAL"
    WAITING_AUTHORIZATION = "WAITING_AUTHORIZATION"
    HIGH_PRIORITY = "HIGH_PRIORITY"
    WITHOUT_PRIORITY = "WITHOUT_PRIORITY"


@dataclass(frozen=True, slots=True)
class ContractSLASummarySnapshot:
    contract: SLIContract
    covered_vehicle_refs: tuple[TypedId, ...]
    open_work_orders: tuple[WorkOrder, ...] = ()
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        if self.as_of is not None:
            require_utc(self.as_of, field_name="as_of")
        invalid = [
            vehicle_ref
            for vehicle_ref in self.covered_vehicle_refs
            if vehicle_ref.entity_type != "vehicle"
        ]
        if invalid:
            raise ValueError("covered_vehicle_refs deve conter apenas refs de vehicle.")


class ContractSLASummaryRepositoryPort(Protocol):
    def get_summary_snapshot(
        self, *, contract_ref: TypedId, as_of: datetime | None = None
    ) -> ContractSLASummarySnapshot | None: ...


@dataclass(frozen=True, slots=True)
class ContractSLAWorkOrderLine:
    work_order_id: TypedId
    vehicle_ref: TypedId
    state: WorkOrderState
    priority_score: int | None
    signals: tuple[ContractSLAOperationalSignal, ...]


@dataclass(frozen=True, slots=True)
class ContractSLASummary:
    contract_ref: TypedId
    contract_version_no: int | None
    covered_vehicle_count: int
    open_work_order_count: int
    waiting_material_count: int
    waiting_authorization_count: int
    sla_risk_count: int
    response_sla_duration_seconds: int | None
    repair_sla_duration_seconds: int | None
    lines: tuple[ContractSLAWorkOrderLine, ...]


class SLIContractSummaryNaoEncontrado(KeyError):
    """`contract_ref` não corresponde a nenhum snapshot de contrato."""


def _active_contract_version(
    contract: SLIContract, as_of: datetime | None
) -> ContractVersion | None:
    if as_of is not None:
        return contract.resolve_version_at(as_of)
    if contract.current_version_no is None:
        return None
    return contract.versions[-1]


def _is_open(work_order: WorkOrder) -> bool:
    return work_order.state not in TERMINAL_STATES


def _signals(work_order: WorkOrder) -> tuple[ContractSLAOperationalSignal, ...]:
    signals: list[ContractSLAOperationalSignal] = []
    if work_order.state is WorkOrderState.WAITING_MATERIAL:
        signals.append(ContractSLAOperationalSignal.WAITING_MATERIAL)
    if work_order.state is WorkOrderState.WAITING_AUTHORIZATION:
        signals.append(ContractSLAOperationalSignal.WAITING_AUTHORIZATION)
    if work_order.priority is None:
        signals.append(ContractSLAOperationalSignal.WITHOUT_PRIORITY)
    elif work_order.priority.score >= SLA_RISK_THRESHOLD:
        signals.append(ContractSLAOperationalSignal.HIGH_PRIORITY)
    return tuple(signals)


def _sla_duration_seconds(version: ContractVersion | None, *, kind: str) -> int | None:
    if version is None:
        return None
    sla = version.response_sla if kind == "response" else version.repair_sla
    if sla is None:
        return None
    return int(sla.duration.total_seconds())


@dataclass(frozen=True, slots=True)
class ContractSLASummaryService:
    repository: ContractSLASummaryRepositoryPort

    def get_contract_sla_summary(
        self, *, contract_ref: TypedId, as_of: datetime | None = None
    ) -> ContractSLASummary:
        if as_of is not None:
            require_utc(as_of, field_name="as_of")
        snapshot = self.repository.get_summary_snapshot(contract_ref=contract_ref, as_of=as_of)
        if snapshot is None:
            raise SLIContractSummaryNaoEncontrado(
                f"SLIContract '{contract_ref.value}' não encontrado."
            )
        version = _active_contract_version(snapshot.contract, as_of or snapshot.as_of)
        open_work_orders = tuple(
            work_order
            for work_order in snapshot.open_work_orders
            if _is_open(work_order)
            and work_order.contract_context.contract_ref == snapshot.contract.contract_id
        )
        lines = tuple(
            ContractSLAWorkOrderLine(
                work_order_id=work_order.work_order_id,
                vehicle_ref=work_order.vehicle_ref,
                state=work_order.state,
                priority_score=work_order.priority.score if work_order.priority else None,
                signals=_signals(work_order),
            )
            for work_order in sorted(
                open_work_orders,
                key=lambda item: item.priority.score if item.priority else -1,
                reverse=True,
            )
        )
        return ContractSLASummary(
            contract_ref=snapshot.contract.contract_id,
            contract_version_no=version.version_no if version else None,
            covered_vehicle_count=len(snapshot.covered_vehicle_refs),
            open_work_order_count=len(lines),
            waiting_material_count=sum(
                1 for line in lines if ContractSLAOperationalSignal.WAITING_MATERIAL in line.signals
            ),
            waiting_authorization_count=sum(
                1
                for line in lines
                if ContractSLAOperationalSignal.WAITING_AUTHORIZATION in line.signals
            ),
            sla_risk_count=sum(
                1 for line in lines if ContractSLAOperationalSignal.HIGH_PRIORITY in line.signals
            ),
            response_sla_duration_seconds=_sla_duration_seconds(version, kind="response"),
            repair_sla_duration_seconds=_sla_duration_seconds(version, kind="repair"),
            lines=lines,
        )
