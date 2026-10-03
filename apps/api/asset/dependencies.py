"""Dependências HTTP da vertical Asset.

A5 introduz a raiz de composição HTTP de Asset. Este primeiro corte é
read-only, então a dependência exposta aqui reaproveita a resolução genérica já
validada da API: OIDC → OrganizationContext → Permission → Connection/RLS.
"""

from typing import Annotated

from fastapi import Depends

from apps.api.livestock_dependencies import (
    ConnectionDependency,
    require_permission,
    typed_id_or_problem,
)
from packages.asset_application.authorization import (
    APPLICABILITY_READ,
    CONTRACT_READ,
    DASHBOARD_READ,
    INVENTORY_READ,
    VEHICLE_READ,
    WO_ADD_TASK,
    WO_DEMAND_MATERIAL,
    WO_OPEN,
    WO_READ,
)
from packages.core_domain import OrganizationContext


def require_dashboard_read(
    contexto: Annotated[OrganizationContext, Depends(require_permission(DASHBOARD_READ))],
) -> OrganizationContext:
    return contexto


def require_vehicle_read(
    contexto: Annotated[OrganizationContext, Depends(require_permission(VEHICLE_READ))],
) -> OrganizationContext:
    return contexto


def require_applicability_read(
    contexto: Annotated[OrganizationContext, Depends(require_permission(APPLICABILITY_READ))],
) -> OrganizationContext:
    return contexto


def require_contract_read(
    contexto: Annotated[OrganizationContext, Depends(require_permission(CONTRACT_READ))],
) -> OrganizationContext:
    return contexto


def require_inventory_read(
    contexto: Annotated[OrganizationContext, Depends(require_permission(INVENTORY_READ))],
) -> OrganizationContext:
    return contexto


def require_work_order_read(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_READ))],
) -> OrganizationContext:
    return contexto


def require_work_order_open(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_OPEN))],
) -> OrganizationContext:
    return contexto


def require_work_order_add_task(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_ADD_TASK))],
) -> OrganizationContext:
    return contexto


def require_work_order_demand_material(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_DEMAND_MATERIAL))],
) -> OrganizationContext:
    return contexto


__all__ = [
    "ConnectionDependency",
    "require_applicability_read",
    "require_contract_read",
    "require_dashboard_read",
    "require_inventory_read",
    "require_vehicle_read",
    "require_work_order_add_task",
    "require_work_order_demand_material",
    "require_work_order_open",
    "require_work_order_read",
    "typed_id_or_problem",
]
