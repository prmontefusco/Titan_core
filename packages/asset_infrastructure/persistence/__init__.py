"""Fachada de persistência da vertical Titan Asset & Sustainment (A3).

Reexporta as `Table` e os repositórios de cada agregado. Cresce incrementalmente
— um módulo `<agregado>_repository.py` por agregado (ou pequeno cluster), mesmo
padrão de `packages/livestock_infrastructure/persistence/__init__.py`.
"""

from packages.asset_infrastructure.persistence.applicability_repository import (
    TransactionalApplicabilityRepository,
    applicability_table,
)
from packages.asset_infrastructure.persistence.configuration_repository import (
    TransactionalConfigurationBaselineRepository,
    configuration_baseline_positions_table,
    configuration_baselines_table,
)
from packages.asset_infrastructure.persistence.customer_site_repository import (
    TransactionalCustomerSiteRepository,
    customer_site_contacts_table,
    customer_sites_table,
)
from packages.asset_infrastructure.persistence.inventory_repository import (
    TransactionalStockPositionRepository,
    TransactionalStockReservationRepository,
    TransactionalStockTransferRepository,
    stock_position_reservations_table,
    stock_positions_table,
    stock_reservations_table,
    stock_transfers_table,
)
from packages.asset_infrastructure.persistence.part_repository import (
    TransactionalInterchangeabilityGroupRepository,
    TransactionalPartRepository,
    interchangeability_group_members_table,
    interchangeability_groups_table,
    part_revisions_table,
    part_supersessions_table,
    parts_table,
)
from packages.asset_infrastructure.persistence.stock_location_repository import (
    TransactionalStockLocationRepository,
    stock_locations_table,
)
from packages.asset_infrastructure.persistence.sustainment_contract_repository import (
    TransactionalSLIContractRepository,
    contract_version_coverage_lines_table,
    contract_versions_table,
    sli_contracts_table,
)
from packages.asset_infrastructure.persistence.vehicle_repository import (
    TransactionalVehicleRepository,
    vehicle_meter_corrections_table,
    vehicle_meter_readings_table,
    vehicles_table,
)
from packages.asset_infrastructure.persistence.work_order_repository import (
    TransactionalWorkOrderRepository,
    work_order_material_demands_table,
    work_order_removed_components_table,
    work_order_tasks_table,
    work_orders_table,
)

__all__ = [
    "TransactionalApplicabilityRepository",
    "TransactionalConfigurationBaselineRepository",
    "TransactionalCustomerSiteRepository",
    "TransactionalInterchangeabilityGroupRepository",
    "TransactionalPartRepository",
    "TransactionalStockLocationRepository",
    "TransactionalStockPositionRepository",
    "TransactionalStockReservationRepository",
    "TransactionalSLIContractRepository",
    "TransactionalStockTransferRepository",
    "TransactionalVehicleRepository",
    "TransactionalWorkOrderRepository",
    "applicability_table",
    "configuration_baseline_positions_table",
    "configuration_baselines_table",
    "customer_site_contacts_table",
    "customer_sites_table",
    "interchangeability_group_members_table",
    "interchangeability_groups_table",
    "part_revisions_table",
    "part_supersessions_table",
    "parts_table",
    "stock_locations_table",
    "stock_position_reservations_table",
    "stock_positions_table",
    "stock_reservations_table",
    "stock_transfers_table",
    "contract_version_coverage_lines_table",
    "contract_versions_table",
    "sli_contracts_table",
    "vehicle_meter_corrections_table",
    "vehicle_meter_readings_table",
    "vehicles_table",
    "work_order_material_demands_table",
    "work_order_removed_components_table",
    "work_order_tasks_table",
    "work_orders_table",
]
