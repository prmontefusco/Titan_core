"""Testes de dominio para campanha sanitaria (Passo 14.2)."""

from datetime import UTC, datetime

import pytest

from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.shared_kernel import OrganizationId, TypedId


def test_sanitary_campaign_creation_success() -> None:
    campaign = SanitaryCampaign(
        campaign_id=TypedId.new("sanitary_campaign"),
        organization_id=OrganizationId.new(),
        code="PNCEBT-BRUCELOSE-2026",
        name="Campanha Brucelose 2026",
        starts_at=datetime(2026, 1, 1, tzinfo=UTC),
        ends_at=datetime(2026, 12, 31, tzinfo=UTC),
        disease="Brucelose",
        authority="MAPA",
    )

    assert campaign.covers(datetime(2026, 7, 1, tzinfo=UTC))


def test_sanitary_campaign_rejects_invalid_window() -> None:
    with pytest.raises(ValueError, match="ends_at"):
        SanitaryCampaign(
            campaign_id=TypedId.new("sanitary_campaign"),
            organization_id=OrganizationId.new(),
            code="PNCEBT",
            name="Campanha",
            starts_at=datetime(2026, 12, 31, tzinfo=UTC),
            ends_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
