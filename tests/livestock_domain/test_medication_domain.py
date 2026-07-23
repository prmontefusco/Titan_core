"""Testes unitários de domínio para Medication e Prescription (Passo 9.1 - Titan Livestock)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from packages.livestock_domain.medication import Medication, MedicationBatch
from packages.livestock_domain.prescription import Prescription, PrescriptionTargetType
from packages.shared_kernel import OrganizationId, TypedId


def _batch(**overrides: object) -> MedicationBatch:
    defaults: dict[str, object] = {
        "batch_id": TypedId.new("medication_batch"),
        "organization_id": OrganizationId(uuid4()),
        "medication_id": TypedId.new("medication"),
        "batch_number": "LOTE-001",
        "expiry_date": datetime.now(UTC) + timedelta(days=365),
    }
    defaults.update(overrides)
    return MedicationBatch(**defaults)  # type: ignore[arg-type]


def test_medication_batch_creation_success() -> None:
    batch = _batch(manufacturing_date=datetime.now(UTC) - timedelta(days=10))
    assert batch.batch_number == "LOTE-001"


def test_medication_batch_rejects_empty_number() -> None:
    with pytest.raises(ValueError, match="batch_number"):
        _batch(batch_number="   ")


def test_medication_batch_rejects_naive_expiry() -> None:
    """Validade sem timezone é rejeitada, nunca tratada silenciosamente como UTC."""
    with pytest.raises(ValueError, match="timezone"):
        _batch(expiry_date=datetime(2027, 1, 1, 0, 0))  # noqa: DTZ001 — naive de propósito


def test_medication_batch_rejects_expiry_before_manufacturing() -> None:
    with pytest.raises(ValueError, match="expiry_date deve ser estritamente posterior"):
        _batch(
            expiry_date=datetime.now(UTC),
            manufacturing_date=datetime.now(UTC) + timedelta(days=1),
        )


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
