"""Testes do serviço de cálculo de carência (Passo 9.4 - Titan Livestock)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from packages.livestock_application.withdrawal_service import WithdrawalCalculator
from packages.livestock_domain.medication import Medication, MedicationBatch
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.test_treatment_service import (
    InMemoryApplicationRepo,
    InMemoryBatchRepo,
)

T0 = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


class InMemoryMedicationRepo:
    def __init__(self, medications: dict[str, Medication]) -> None:
        self.meds = medications

    def save(self, medication: Medication) -> None:
        self.meds[medication.medication_id.value.hex] = medication

    def get_by_id(self, medication_id: TypedId) -> Medication | None:
        return self.meds.get(medication_id.value.hex)

    def get_by_trade_name(
        self, organization_id: OrganizationId, trade_name: str
    ) -> Medication | None:
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Medication]:
        return list(self.meds.values())


def _setup(
    org_id: OrganizationId, withdrawal_days: int
) -> tuple[WithdrawalCalculator, TypedId, TypedId, InMemoryApplicationRepo]:
    medication = Medication(
        medication_id=TypedId.new("medication"),
        organization_id=org_id,
        trade_name="Ivomec",
        active_ingredient="Ivermectina",
        manufacturer="Boehringer",
        withdrawal_period_days=withdrawal_days,
    )
    batch = MedicationBatch(
        batch_id=TypedId.new("medication_batch"),
        organization_id=org_id,
        medication_id=medication.medication_id,
        batch_number="LOTE-1",
        expiry_date=T0 + timedelta(days=400),
    )
    app_repo = InMemoryApplicationRepo()
    calculator = WithdrawalCalculator(
        application_repository=app_repo,
        batch_repository=InMemoryBatchRepo({batch.batch_id.value.hex: batch}),
        medication_repository=InMemoryMedicationRepo(
            {medication.medication_id.value.hex: medication}
        ),
    )
    return calculator, batch.batch_id, TypedId.new("animal"), app_repo


def _application(
    org_id: OrganizationId,
    animal_id: TypedId,
    batch_id: TypedId,
    applied_at: datetime,
    *,
    corrects: TypedId | None = None,
) -> TreatmentApplication:
    return TreatmentApplication(
        application_id=TypedId.new("treatment_application"),
        organization_id=org_id,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        actor_id=TypedId.new("actor"),
        applied_at=applied_at,
        corrects_application_id=corrects,
    )


def test_assess_animal_uses_medication_period_snapshot() -> None:
    org_id = OrganizationId(uuid4())
    calc, batch_id, animal_id, app_repo = _setup(org_id, withdrawal_days=122)
    app_repo.save(_application(org_id, animal_id, batch_id, T0))

    status = calc.assess_animal(org_id, animal_id)

    assert len(status.contributions) == 1
    assert status.contributions[0].withdrawal_period_days == 122
    assert status.eligible_from == T0 + timedelta(days=122)
    # Snapshot: mesmo que o medicamento mude depois, este cálculo já está fixado.


def test_correction_supersedes_the_original_in_the_calculation() -> None:
    """Aplicação corrigida não conta; conta a correção (com seu applied_at)."""
    org_id = OrganizationId(uuid4())
    calc, batch_id, animal_id, app_repo = _setup(org_id, withdrawal_days=30)

    original = _application(org_id, animal_id, batch_id, T0)
    app_repo.save(original)
    # A correção move o applied_at para 10 dias antes.
    correction = _application(
        org_id, animal_id, batch_id, T0 - timedelta(days=10), corrects=original.application_id
    )
    app_repo.save(correction)

    status = calc.assess_animal(org_id, animal_id)

    # Só a correção contribui, e o fim da carência conta a partir do applied_at dela.
    assert len(status.contributions) == 1
    assert status.eligible_from == (T0 - timedelta(days=10)) + timedelta(days=30)


def test_animal_without_treatment_is_eligible() -> None:
    org_id = OrganizationId(uuid4())
    calc, _, animal_id, _ = _setup(org_id, withdrawal_days=122)

    status = calc.assess_animal(org_id, animal_id)

    assert status.eligible_from is None
    assert status.is_eligible_at(T0) is True
