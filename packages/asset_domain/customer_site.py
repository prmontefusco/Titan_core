"""Entidade `CustomerSite` — Titan Asset & Sustainment (A2). OM/Site (decisão G).

Modelo: `docs/asset/05_DOMAIN_MODEL.md` §1.11. Fecha o módulo `asset` do
domínio (`docs/asset/04_BOUNDED_CONTEXT_MAP.md` §2).

`CustomerSite` **vive na vertical** — nenhum conceito equivalente entra em
`packages/core_*` (constituição §18; `docs/asset/11_AUTHORIZATION_MODEL.md` §2,
G1). É o valor referenciado pelo `site_scope` de `AssetOperationContext`: uma
entidade de referência sem invariante transacional forte própria
(`06_AGGREGATE_ANALYSIS.md` §2, mesma classe de `StockLocation`) — a garantia
de isolamento pesada (I‑SEC‑2, escopo aplicado antes da resolução do dado) é
responsabilidade da camada de aplicação/autorização, não deste módulo.
"""

from dataclasses import dataclass
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId


class CustomerSiteKind(StrEnum):
    OM = "OM"
    CIVIL_FLEET_SITE = "CIVIL_FLEET_SITE"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class SiteContact:
    """VO — `05_DOMAIN_MODEL.md` §1.11 `contacts`."""

    name: str
    role: str | None = None
    email: str | None = None
    phone: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name do contato não pode ser vazio.")


@dataclass(frozen=True, slots=True)
class CustomerSite:
    """`05_DOMAIN_MODEL.md` §1.11. Entidade de referência."""

    site_id: TypedId
    organization_id: OrganizationId
    customer_ref: TypedId
    code: str
    display_name: str
    kind: CustomerSiteKind = CustomerSiteKind.OM
    contacts: tuple[SiteContact, ...] = ()
    version: int = 1

    def __post_init__(self) -> None:
        if self.site_id.entity_type != "customer_site":
            raise ValueError(
                "site_id deve ter entity_type 'customer_site', recebido "
                f"'{self.site_id.entity_type}'."
            )
        if self.customer_ref.entity_type != "customer":
            raise ValueError(
                "customer_ref deve ter entity_type 'customer', recebido "
                f"'{self.customer_ref.entity_type}'."
            )
        if not self.code or not self.code.strip():
            raise ValueError("code não pode ser vazio.")
        if not self.display_name or not self.display_name.strip():
            raise ValueError("display_name não pode ser vazio.")
