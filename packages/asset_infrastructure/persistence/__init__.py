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
from packages.asset_infrastructure.persistence.vehicle_repository import (
    TransactionalVehicleRepository,
    vehicle_meter_corrections_table,
    vehicle_meter_readings_table,
    vehicles_table,
)

__all__ = [
    "TransactionalApplicabilityRepository",
    "TransactionalConfigurationBaselineRepository",
    "TransactionalCustomerSiteRepository",
    "TransactionalInterchangeabilityGroupRepository",
    "TransactionalPartRepository",
    "TransactionalStockLocationRepository",
    "TransactionalVehicleRepository",
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
    "vehicle_meter_corrections_table",
    "vehicle_meter_readings_table",
    "vehicles_table",
]
