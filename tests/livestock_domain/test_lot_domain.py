"""Testes unitários de domínio para LivestockLot e LotMembership (Passo 8.4 - Titan Livestock)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from packages.livestock_domain.lot import (
    LivestockLot,
    LotMembership,
    LotStatus,
    LotType,
)
from packages.shared_kernel import OrganizationId, TypedId


def test_livestock_lot_creation_success() -> None:
    org_id = OrganizationId(uuid4())
    prop_id = TypedId.new("rural_property")
    lot_id = TypedId.new("livestock_lot")

    lot = LivestockLot(
        lot_id=lot_id,
        organization_id=org_id,
        property_id=prop_id,
        code="LOTE-ENGORDA-01",
        name="Lote de Engorda Pasto 3",
        lot_type=LotType.OPERATIONAL,
        status=LotStatus.ACTIVE,
    )

    assert lot.code == "LOTE-ENGORDA-01"
    assert lot.lot_type == LotType.OPERATIONAL
    assert lot.status == LotStatus.ACTIVE


def test_lot_membership_validation() -> None:
    lot_id = TypedId.new("livestock_lot")
    animal_id = TypedId.new("animal")
    m_id = TypedId.new("lot_membership")
    t_start = datetime.now(UTC) - timedelta(days=10)
    t_end = datetime.now(UTC) - timedelta(days=2)

    membership = LotMembership(
        membership_id=m_id,
        lot_id=lot_id,
        animal_id=animal_id,
        valid_from=t_start,
        valid_until=t_end,
    )

    assert membership.valid_until == t_end

    # Testar valid_until <= valid_from
    with pytest.raises(ValueError, match="estritamente posterior"):
        LotMembership(
            membership_id=m_id,
            lot_id=lot_id,
            animal_id=animal_id,
            valid_from=t_end,
            valid_until=t_start,
        )
