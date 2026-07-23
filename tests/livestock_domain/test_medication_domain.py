"""Testes unitários de domínio para Medication e Prescription (Passo 9.1 - Titan Livestock)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.livestock_domain.medication import Medication
from packages.livestock_domain.prescription import Prescription, PrescriptionTargetType
from packages.shared_kernel import OrganizationId, TypedId


def test_medication_creation_success() -> None:
    org_id = OrganizationId(uuid4())
    med_id = TypedId.new("medication")

    med = Medication(
        medication_id=med_id,
        organization_id=org_id,
        trade_name="Ivomec Gold",
        active_ingredient="Ivermectina 3.15%",
        manufacturer="Boehringer",
        withdrawal_period_days=122,
    )

    assert med.trade_name == "Ivomec Gold"
    assert med.withdrawal_period_days == 122


def test_medication_withdrawal_validation() -> None:
    org_id = OrganizationId(uuid4())
    med_id = TypedId.new("medication")

    with pytest.raises(ValueError, match="withdrawal_period_days"):
        Medication(
            medication_id=med_id,
            organization_id=org_id,
            trade_name="Remédio Erro",
            active_ingredient="Ativo",
            manufacturer="Lab",
            withdrawal_period_days=-5,
        )


def test_prescription_creation_success() -> None:
    org_id = OrganizationId(uuid4())
    p_id = TypedId.new("prescription")
    v_id = TypedId.new("veterinarian")
    m_id = TypedId.new("medication")
    prop_id = TypedId.new("rural_property")
    animal_id = TypedId.new("animal")

    presc = Prescription(
        prescription_id=p_id,
        organization_id=org_id,
        veterinarian_id=v_id,
        medication_id=m_id,
        property_id=prop_id,
        prescribed_date=datetime.now(UTC),
        dosage="1 mL / 50 kg",
        administration_route="SUBCUTANEOUS",
        target_type=PrescriptionTargetType.ANIMAL,
        target_ids=(animal_id,),
        reason="Tratamento preventivo",
    )

    assert presc.dosage == "1 mL / 50 kg"
    assert len(presc.target_ids) == 1
