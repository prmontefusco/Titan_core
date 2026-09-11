"""Caso de uso da entidade de referência `CustomerSite` — Titan Asset (A4).

Sem invariante transacional forte própria (`06_AGGREGATE_ANALYSIS.md` §2) —
o serviço só cobre `RegisterCustomerSite` (`09_COMMAND_MODEL.md`), o único
comando catalogado para este agregado no slice.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.customer_site import CustomerSite, CustomerSiteKind, SiteContact
from packages.asset_domain.events import SITE_REGISTERED, site_registered_payload
from packages.shared_kernel import TypedId


class CustomerSiteRepositoryPort(Protocol):
    def save(self, site: CustomerSite) -> None: ...

    def get_by_id(self, site_id: TypedId) -> CustomerSite | None: ...


@dataclass(frozen=True, slots=True)
class CustomerSiteService:
    repository: CustomerSiteRepositoryPort
    recorder: AssetEventRecorder

    def register_site(
        self,
        context: AssetOperationContext,
        *,
        customer_ref: TypedId,
        code: str,
        display_name: str,
        kind: CustomerSiteKind = CustomerSiteKind.OM,
        contacts: tuple[SiteContact, ...] = (),
        occurred_at: datetime,
    ) -> CustomerSite:
        site = CustomerSite(
            site_id=TypedId.new("customer_site"),
            organization_id=context.organization_id,
            customer_ref=customer_ref,
            code=code,
            display_name=display_name,
            kind=kind,
            contacts=contacts,
        )
        self.repository.save(site)
        self.recorder.record(
            context=context,
            aggregate_id=site.site_id,
            event_type=SITE_REGISTERED,
            payload=site_registered_payload(
                site_id=site.site_id,
                customer_ref=customer_ref,
                code=code,
                kind=kind.value,
            ),
            occurred_at=occurred_at,
        )
        return site

    def get_site(self, site_id: TypedId) -> CustomerSite | None:
        return self.repository.get_by_id(site_id)
