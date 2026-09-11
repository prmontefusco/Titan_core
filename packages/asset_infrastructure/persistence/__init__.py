"""Fachada de persistência da vertical Titan Asset & Sustainment (A3).

Reexporta as `Table` e os repositórios de cada agregado. Cresce incrementalmente
— um módulo `<agregado>_repository.py` por agregado (ou pequeno cluster), mesmo
padrão de `packages/livestock_infrastructure/persistence/__init__.py`.
"""

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

__all__ = [
    "TransactionalCustomerSiteRepository",
    "TransactionalInterchangeabilityGroupRepository",
    "TransactionalPartRepository",
    "TransactionalStockLocationRepository",
    "customer_site_contacts_table",
    "customer_sites_table",
    "interchangeability_group_members_table",
    "interchangeability_groups_table",
    "part_revisions_table",
    "part_supersessions_table",
    "parts_table",
    "stock_locations_table",
]
