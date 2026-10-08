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
    APPLICABILITY_ASSERT,
    APPLICABILITY_READ,
    APPLICABILITY_WITHDRAW,
    CONTRACT_READ,
    DASHBOARD_READ,
    INVENTORY_ADJUST,
    INVENTORY_OPEN_POSITION,
    INVENTORY_READ,
    PART_ADD_REVISION,
    PART_EDIT_INTERCHANGE,
    PART_REGISTER,
    PART_SUPERSEDE,
    SITE_REGISTER,
    VEHICLE_CORRECT_METER,
    VEHICLE_READ,
    VEHICLE_RECORD_METER,
    VEHICLE_TRANSITION,
    WO_ADD_TASK,
    WO_CANCEL,
    WO_CLOSE,
    WO_DEMAND_MATERIAL,
    WO_EXECUTE,
    WO_OPEN,
    WO_READ,
    WO_RECORD_REMOVAL,
    WO_RESERVE_MATERIAL,
    WO_TECH_COMPLETE,
    WO_TRANSITION,
    WO_VALIDATE,
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


def require_vehicle_transition(
    contexto: Annotated[OrganizationContext, Depends(require_permission(VEHICLE_TRANSITION))],
) -> OrganizationContext:
    return contexto


def require_vehicle_record_meter(
    contexto: Annotated[OrganizationContext, Depends(require_permission(VEHICLE_RECORD_METER))],
) -> OrganizationContext:
    return contexto


def require_vehicle_correct_meter(
    contexto: Annotated[OrganizationContext, Depends(require_permission(VEHICLE_CORRECT_METER))],
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


def require_inventory_open_position(
    contexto: Annotated[OrganizationContext, Depends(require_permission(INVENTORY_OPEN_POSITION))],
) -> OrganizationContext:
    return contexto


def require_inventory_adjust(
    contexto: Annotated[OrganizationContext, Depends(require_permission(INVENTORY_ADJUST))],
) -> OrganizationContext:
    return contexto


def require_site_register(
    contexto: Annotated[OrganizationContext, Depends(require_permission(SITE_REGISTER))],
) -> OrganizationContext:
    return contexto


def require_part_register(
    contexto: Annotated[OrganizationContext, Depends(require_permission(PART_REGISTER))],
) -> OrganizationContext:
    return contexto


def require_part_add_revision(
    contexto: Annotated[OrganizationContext, Depends(require_permission(PART_ADD_REVISION))],
) -> OrganizationContext:
    return contexto


def require_part_edit_interchange(
    contexto: Annotated[OrganizationContext, Depends(require_permission(PART_EDIT_INTERCHANGE))],
) -> OrganizationContext:
    return contexto


def require_applicability_assert(
    contexto: Annotated[OrganizationContext, Depends(require_permission(APPLICABILITY_ASSERT))],
) -> OrganizationContext:
    return contexto


def require_applicability_withdraw(
    contexto: Annotated[OrganizationContext, Depends(require_permission(APPLICABILITY_WITHDRAW))],
) -> OrganizationContext:
    return contexto


def require_part_supersede(
    contexto: Annotated[OrganizationContext, Depends(require_permission(PART_SUPERSEDE))],
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


def require_work_order_reserve_material(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_RESERVE_MATERIAL))],
) -> OrganizationContext:
    return contexto


def require_work_order_record_removal(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_RECORD_REMOVAL))],
) -> OrganizationContext:
    return contexto


def require_work_order_execute(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_EXECUTE))],
) -> OrganizationContext:
    return contexto


def require_work_order_tech_complete(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_TECH_COMPLETE))],
) -> OrganizationContext:
    return contexto


def require_work_order_validate(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_VALIDATE))],
) -> OrganizationContext:
    return contexto


def require_work_order_close(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_CLOSE))],
) -> OrganizationContext:
    return contexto


def require_work_order_cancel(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_CANCEL))],
) -> OrganizationContext:
    return contexto


def require_work_order_transition(
    contexto: Annotated[OrganizationContext, Depends(require_permission(WO_TRANSITION))],
) -> OrganizationContext:
    return contexto


__all__ = [
    "ConnectionDependency",
    "require_applicability_read",
    "require_contract_read",
    "require_dashboard_read",
    "require_inventory_read",
    "require_inventory_adjust",
    "require_inventory_open_position",
    "require_part_register",
    "require_part_add_revision",
    "require_part_edit_interchange",
    "require_applicability_assert",
    "require_applicability_withdraw",
    "require_part_supersede",
    "require_site_register",
    "require_vehicle_read",
    "require_vehicle_correct_meter",
    "require_vehicle_record_meter",
    "require_vehicle_transition",
    "require_work_order_add_task",
    "require_work_order_cancel",
    "require_work_order_close",
    "require_work_order_demand_material",
    "require_work_order_execute",
    "require_work_order_open",
    "require_work_order_read",
    "require_work_order_record_removal",
    "require_work_order_reserve_material",
    "require_work_order_tech_complete",
    "require_work_order_transition",
    "require_work_order_validate",
    "typed_id_or_problem",
]
