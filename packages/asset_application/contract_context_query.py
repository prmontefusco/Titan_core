"""Query `GetContractContextForVehicle` — Titan Asset A5."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from packages.asset_domain.sustainment_contract import (
    ContractScope,
    ContractVersion,
    CoverageLine,
    ServiceLimits,
    SLIContract,
)
from packages.asset_domain.vehicle import Vehicle
from packages.shared_kernel import TypedId
from packages.shared_kernel.temporal import require_utc


class ContractContextVehicleRepositoryPort(Protocol):
    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None: ...


class ContractContextRepositoryPort(Protocol):
    def list_all(self) -> tuple[SLIContract, ...]: ...


class ContractContextNaoEncontrado(KeyError):
    """Nenhum contrato vigente cobre o Vehicle no instante solicitado."""


class ContractContextAmbiguo(ValueError):
    """Mais de um contrato vigente cobre o Vehicle no mesmo instante."""


def _duration_seconds(duration: timedelta | None) -> int | None:
    return None if duration is None else int(duration.total_seconds())


def _coverage_matches_vehicle(line: CoverageLine, vehicle: Vehicle) -> bool:
    if line.scope is ContractScope.VEHICLE:
        return line.scope_value == str(vehicle.vehicle_id.value)
    if line.scope is ContractScope.MODEL:
        return line.scope_value == str(vehicle.model_ref.value)
    if line.scope is ContractScope.SITE and vehicle.site_ref is not None:
        return line.scope_value == str(vehicle.site_ref.value)
    return False


@dataclass(frozen=True, slots=True)
class ContractContextForVehicle:
    vehicle: Vehicle
    contract: SLIContract
    contract_version: ContractVersion
    coverage_line: CoverageLine
    resolved_at: datetime

    @property
    def response_sla_duration_seconds(self) -> int | None:
        sla = self.contract_version.response_sla
        return _duration_seconds(sla.duration if sla is not None else None)

    @property
    def repair_sla_duration_seconds(self) -> int | None:
        sla = self.contract_version.repair_sla
        return _duration_seconds(sla.duration if sla is not None else None)

    @property
    def availability_target_percentage(self) -> Decimal | None:
        return self.contract_version.availability_target_percentage

    @property
    def service_limits(self) -> ServiceLimits | None:
        return self.contract_version.service_limits


@dataclass(frozen=True, slots=True)
class ContractContextQueryService:
    vehicle_repository: ContractContextVehicleRepositoryPort
    contract_repository: ContractContextRepositoryPort

    def get_context_for_vehicle(
        self, *, vehicle_id: TypedId, instant: datetime
    ) -> ContractContextForVehicle:
        require_utc(instant, field_name="instant")
        vehicle = self.vehicle_repository.get_by_id(vehicle_id)
        if vehicle is None:
            raise ContractContextNaoEncontrado(f"Vehicle '{vehicle_id.value}' não encontrado.")

        matches: list[ContractContextForVehicle] = []
        for contract in self.contract_repository.list_all():
            version = contract.resolve_version_at(instant)
            if version is None:
                continue
            for line in version.coverage_lines:
                if _coverage_matches_vehicle(line, vehicle):
                    matches.append(
                        ContractContextForVehicle(
                            vehicle=vehicle,
                            contract=contract,
                            contract_version=version,
                            coverage_line=line,
                            resolved_at=instant,
                        )
                    )

        if not matches:
            raise ContractContextNaoEncontrado(
                f"Nenhum SLIContract cobre Vehicle '{vehicle_id.value}' em {instant.isoformat()}."
            )
        if len(matches) > 1:
            raise ContractContextAmbiguo(
                "Mais de um SLIContract cobre Vehicle "
                f"'{vehicle_id.value}' em {instant.isoformat()}."
            )
        return matches[0]
