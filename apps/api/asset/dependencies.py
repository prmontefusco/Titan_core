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
from packages.asset_application.authorization import DASHBOARD_READ
from packages.core_domain import OrganizationContext


def require_dashboard_read(
    contexto: Annotated[OrganizationContext, Depends(require_permission(DASHBOARD_READ))],
) -> OrganizationContext:
    return contexto


__all__ = [
    "ConnectionDependency",
    "require_dashboard_read",
    "typed_id_or_problem",
]
