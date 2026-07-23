"""Testes unitários de domínio para TreatmentApplication (Passo 9.3 - Titan Livestock)."""

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId


def _application(**overrides: object) -> TreatmentApplication:
    defaults: dict[str, object] = {
        "application_id": TypedId.new("treatment_application"),
        "organization_id": OrganizationId(uuid4()),
        "animal_id": TypedId.new("animal"),
        "medication_batch_id": TypedId.new("medication_batch"),
        "actor_id": TypedId.new("actor"),
        "applied_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return TreatmentApplication(**defaults)  # type: ignore[arg-type]


def test_treatment_application_creation_success() -> None:
    app = _application(
        dose="1 mL / 50 kg",
        evidence_references=("evidence:foto-1", "evidence:receita-1"),
        prescription_id=TypedId.new("prescription"),
    )
    assert app.dose == "1 mL / 50 kg"
    assert len(app.evidence_references) == 2
    assert app.corrects_application_id is None


def test_treatment_application_is_immutable() -> None:
    """O registro é congelado: não há edição, só correção por novo registro."""
    app = _application()
    with pytest.raises(dataclasses.FrozenInstanceError):
        app.dose = "outra dose"  # type: ignore[misc]


def test_treatment_application_rejects_naive_applied_at() -> None:
    with pytest.raises(ValueError, match="timezone"):
        _application(applied_at=datetime(2026, 7, 20, 12, 0))  # noqa: DTZ001 — naive de propósito


def test_treatment_application_rejects_wrong_entity_types() -> None:
    with pytest.raises(ValueError, match="animal_id"):
        _application(animal_id=TypedId.new("rural_property"))
    with pytest.raises(ValueError, match="medication_batch_id"):
        _application(medication_batch_id=TypedId.new("medication"))
    with pytest.raises(ValueError, match="actor_id"):
        _application(actor_id=TypedId.new("user"))


def test_treatment_application_cannot_correct_itself() -> None:
    app_id = TypedId.new("treatment_application")
    with pytest.raises(ValueError, match="corrigir a si mesma"):
        _application(application_id=app_id, corrects_application_id=app_id)
