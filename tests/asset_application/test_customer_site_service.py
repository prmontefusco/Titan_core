"""Testes do `CustomerSiteService` — Titan Asset (A4)."""

from datetime import UTC, datetime

from packages.asset_application.customer_site_service import (
    CustomerSiteRepositoryPort,
    CustomerSiteService,
)
from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.customer_site import CustomerSite, CustomerSiteKind, SiteContact
from packages.asset_domain.events import SITE_REGISTERED
from packages.shared_kernel import TypedId
from tests.asset_support import FakeEventLog

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class InMemoryCustomerSiteRepository(CustomerSiteRepositoryPort):
    def __init__(self) -> None:
        self.sites: dict[str, CustomerSite] = {}

    def save(self, site: CustomerSite) -> None:
        self.sites[site.site_id.value.hex] = site

    def get_by_id(self, site_id: TypedId) -> CustomerSite | None:
        return self.sites.get(site_id.value.hex)


def test_register_site(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = CustomerSiteService(repository=InMemoryCustomerSiteRepository(), recorder=recorder)

    site = service.register_site(
        context,
        customer_ref=TypedId.new("customer"),
        code="OM-001",
        display_name="Oficina Matriz",
        kind=CustomerSiteKind.OM,
        contacts=(SiteContact(name="Maria Souza", role="Gerente"),),
        occurred_at=OCCURRED_AT,
    )

    assert site.organization_id == context.organization_id
    assert site.contacts[0].name == "Maria Souza"
    assert service.get_site(site.site_id) == site
    event_log.only(SITE_REGISTERED)
