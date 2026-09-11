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

__all__ = [
    "TransactionalCustomerSiteRepository",
    "customer_site_contacts_table",
    "customer_sites_table",
]
