"""Fachada de persistência da vertical Titan Asset & Sustainment (A3).

Reexporta as `Table` e os repositórios de cada agregado. Cresce incrementalmente
— um módulo `<agregado>_repository.py` por agregado (ou pequeno cluster), mesmo
padrão de `packages/livestock_infrastructure/persistence/__init__.py`.
"""
