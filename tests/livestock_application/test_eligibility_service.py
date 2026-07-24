"""Testes da elegibilidade farmacológica (Passo 9.5 - Titan Livestock)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from packages.core_domain.decision import DecisionResult
from packages.livestock_application.eligibility import (
    PharmacologicalEligibilityService,
    build_eligibility_policy,
    build_eligibility_rule,
)
from packages.livestock_application.fact_provider import (
    WITHDRAWAL_FACT_TYPE,
    LivestockFactProvider,
)
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.treatment_service import TreatmentApplicationService
from packages.livestock_application.withdrawal_service import WithdrawalCalculator
from packages.livestock_domain.animal import Animal, AnimalSex
from packages.livestock_domain.medication import Medication, MedicationBatch
from packages.livestock_domain.property import RuralProperty
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.test_treatment_service import (
    InMemoryAnimalRepo,
    InMemoryApplicationRepo,
    InMemoryBatchRepo,
    InMemoryPrescriptionRepo,
)
from tests.livestock_application.test_withdrawal_service import InMemoryMedicationRepo


class _NullPropertyRepo(RuralPropertyRepositoryPort):
    """A avaliação de um animal não consulta propriedades; este repo é só o contrato."""

    def save(self, property: RuralProperty) -> None: ...

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None:
        return None

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        return []


def _service(
    org_id: OrganizationId, animal_id: TypedId, applied_days_ago: int | None, withdrawal_days: int
) -> PharmacologicalEligibilityService:
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
        expiry_date=datetime.now(UTC) + timedelta(days=400),
    )
    animal = Animal(
        animal_id=animal_id,
        organization_id=org_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.FEMALE,
    )
    app_repo = InMemoryApplicationRepo()
    batch_repo = InMemoryBatchRepo({batch.batch_id.value.hex: batch})
    med_repo = InMemoryMedicationRepo({medication.medication_id.value.hex: medication})
    animal_repo = InMemoryAnimalRepo({animal.animal_id.value.hex: animal})

    if applied_days_ago is not None:
        TreatmentApplicationService(
            application_repository=app_repo,
            animal_repository=animal_repo,
            batch_repository=batch_repo,
            prescription_repository=InMemoryPrescriptionRepo(),
        ).register_application(
            organization_id=org_id,
            animal_id=animal_id,
            medication_batch_id=batch.batch_id,
            actor_id=TypedId.new("actor"),
            applied_at=datetime.now(UTC) - timedelta(days=applied_days_ago),
        )

    fact_provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=animal_repo,
        withdrawal_calculator=WithdrawalCalculator(
            application_repository=app_repo,
            batch_repository=batch_repo,
            medication_repository=med_repo,
        ),
    )
    policy = build_eligibility_policy(org_id)
    return PharmacologicalEligibilityService(
        fact_provider=fact_provider,
        policy=policy,
        rule=build_eligibility_rule(policy.policy_id, org_id),
    )


def test_animal_in_withdrawal_is_rejected() -> None:
    org_id = OrganizationId(uuid4())
    animal_id = TypedId.new("animal")
    service = _service(org_id, animal_id, applied_days_ago=10, withdrawal_days=30)

    evaluation, decision = service.evaluate_animal(org_id, animal_id, datetime.now(UTC))

    assert decision.result is DecisionResult.REJEITADA
    assert decision.subject_id == animal_id  # sujeito afetado
    assert decision.reasons  # motivo explícito

    # Versão preservada: o fato de carência carrega a versão da regra de cálculo.
    fato = evaluation.fact_snapshot.get_latest_fact_by_type(WITHDRAWAL_FACT_TYPE)
    assert fato is not None
    assert fato.payload["in_withdrawal"] is True
    assert fato.payload["rule_version"] == "titan-livestock-withdrawal-v1"
    assert fato.payload["blocking_batches"]  # evidência: o lote que bloqueia


def test_animal_out_of_withdrawal_is_approved() -> None:
    org_id = OrganizationId(uuid4())
    animal_id = TypedId.new("animal")
    service = _service(org_id, animal_id, applied_days_ago=100, withdrawal_days=30)

    _, decision = service.evaluate_animal(org_id, animal_id, datetime.now(UTC))

    assert decision.result is DecisionResult.APROVADA


def test_animal_without_treatment_is_approved() -> None:
    org_id = OrganizationId(uuid4())
    animal_id = TypedId.new("animal")
    service = _service(org_id, animal_id, applied_days_ago=None, withdrawal_days=30)

    evaluation, decision = service.evaluate_animal(org_id, animal_id, datetime.now(UTC))

    assert decision.result is DecisionResult.APROVADA
    fato = evaluation.fact_snapshot.get_latest_fact_by_type(WITHDRAWAL_FACT_TYPE)
    assert fato is not None
    assert fato.payload["in_withdrawal"] is False
