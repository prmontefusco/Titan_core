"""Testes unitários de domínio para `CustomerSite` (A2). `docs/asset/05_DOMAIN_MODEL.md` §1.11."""

from uuid import uuid4

import pytest

from packages.asset_domain.customer_site import CustomerSite, CustomerSiteKind, SiteContact
from packages.shared_kernel import OrganizationId, TypedId


def _site(**overrides: object) -> CustomerSite:
    defaults: dict[str, object] = dict(
        site_id=TypedId.new("customer_site"),
        organization_id=OrganizationId(uuid4()),
        customer_ref=TypedId.new("customer"),
        code="OM-01",
        display_name="Organização Militar 01",
    )
    defaults.update(overrides)
    return CustomerSite(**defaults)  # type: ignore[arg-type]


def test_site_creation_defaults_to_om_kind() -> None:
    site = _site()
    assert site.kind is CustomerSiteKind.OM
    assert site.contacts == ()


def test_site_id_entity_type_is_enforced() -> None:
    with pytest.raises(ValueError, match="entity_type 'customer_site'"):
        _site(site_id=TypedId.new("vehicle"))


def test_customer_ref_entity_type_is_enforced() -> None:
    with pytest.raises(ValueError, match="entity_type 'customer'"):
        _site(customer_ref=TypedId.new("part"))


def test_code_cannot_be_blank() -> None:
    with pytest.raises(ValueError, match="code não pode ser vazio"):
        _site(code="  ")


def test_site_accepts_contacts() -> None:
    contact = SiteContact(name="Sgt. Silva", role="Logística", email="silva@om.mil")
    site = _site(contacts=(contact,))
    assert site.contacts == (contact,)


def test_contact_requires_name() -> None:
    with pytest.raises(ValueError, match="name do contato não pode ser vazio"):
        SiteContact(name="  ")
