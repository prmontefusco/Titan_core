"""Avaliação de lote e reavaliação farmacológica (Passo 9.6 - Titan Livestock).

Cenário ponta a ponta do plano: lote bloqueado por animal em carência, remoção
temporal do animal e nova avaliação (`REJECTED → remoção → APPROVED`),
preservando ambas as decisões e com snapshots/hashes distintos.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from packages.core_domain.decision import DecisionResult
from packages.livestock_application.eligibility import (
    PharmacologicalEligibilityService,
    build_eligibility_policy,
    build_eligibility_rule,
    build_lot_eligibility_rule,
)
from packages.livestock_application.fact_provider import (
    LOT_ELIGIBILITY_FACT_TYPE,
    LivestockFactProvider,
)
from packages.livestock_application.lot_service import LotService
from packages.livestock_application.treatment_service import TreatmentApplicationService
from packages.livestock_application.withdrawal_service import WithdrawalCalculator
from packages.livestock_domain.animal import Animal, AnimalSex
from packages.livestock_domain.medication import Medication, MedicationBatch
from packages.livestock_domain.property import RuralProperty
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.test_lot_service import (
    InMemoryAnimalRepo,
    InMemoryLotRepository,
    InMemoryMembershipRepository,
    InMemoryPropertyRepo,
)
from tests.livestock_application.test_treatment_service import (
    InMemoryApplicationRepo,
    InMemoryBatchRepo,
    InMemoryPrescriptionRepo,
)
from tests.livestock_application.test_withdrawal_service import InMemoryMedicationRepo


def test_lot_blocked_then_approved_after_removing_animal_in_withdrawal() -> None:
    org_id = OrganizationId(uuid4())
    prop = RuralProperty(
        property_id=TypedId.new("rural_property"),
        organization_id=org_id,
        code="P-01",
        name="Fazenda 1",
        municipality="RP",
        state_code="SP",
    )
    animal_em_carencia = Animal(
        animal_id=TypedId.new("animal"),
        organization_id=org_id,
        birth_property_id=prop.property_id,
        sex=AnimalSex.FEMALE,
    )
    animal_livre = Animal(
        animal_id=TypedId.new("animal"),
        organization_id=org_id,
        birth_property_id=prop.property_id,
        sex=AnimalSex.MALE,
    )
    medication = Medication(
        medication_id=TypedId.new("medication"),
        organization_id=org_id,
        trade_name="Ivomec",
        active_ingredient="Ivermectina",
        manufacturer="Boehringer",
        withdrawal_period_days=30,
    )
    batch = MedicationBatch(
        batch_id=TypedId.new("medication_batch"),
        organization_id=org_id,
        medication_id=medication.medication_id,
        batch_number="LOTE-1",
        expiry_date=datetime.now(UTC) + timedelta(days=400),
    )

    prop_repo = InMemoryPropertyRepo()
    prop_repo.save(prop)
    animal_repo = InMemoryAnimalRepo()
    animal_repo.save(animal_em_carencia)
    animal_repo.save(animal_livre)
    lot_repo = InMemoryLotRepository()
    membership_repo = InMemoryMembershipRepository()
    app_repo = InMemoryApplicationRepo()
    batch_repo = InMemoryBatchRepo({batch.batch_id.value.hex: batch})
    med_repo = InMemoryMedicationRepo({medication.medication_id.value.hex: medication})

    # Um animal recebe tratamento há 10 dias (carência 30) → em carência.
    TreatmentApplicationService(
        application_repository=app_repo,
        animal_repository=animal_repo,
        batch_repository=batch_repo,
        prescription_repository=InMemoryPrescriptionRepo(),
    ).register_application(
        organization_id=org_id,
        animal_id=animal_em_carencia.animal_id,
        medication_batch_id=batch.batch_id,
        actor_id=TypedId.new("actor"),
        applied_at=datetime.now(UTC) - timedelta(days=10),
    )

    lot_service = LotService(
        lot_repository=lot_repo,
        membership_repository=membership_repo,
        animal_repository=animal_repo,
        property_repository=prop_repo,
    )
    lot = lot_service.create_lot(
        organization_id=org_id, property_id=prop.property_id, code="L-01", name="Lote 1"
    )
    lot_service.add_animal_to_lot(lot.lot_id, animal_em_carencia.animal_id)
    lot_service.add_animal_to_lot(lot.lot_id, animal_livre.animal_id)

    fact_provider = LivestockFactProvider(
        property_repository=prop_repo,
        animal_repository=animal_repo,
        withdrawal_calculator=WithdrawalCalculator(
            application_repository=app_repo,
            batch_repository=batch_repo,
            medication_repository=med_repo,
        ),
        membership_repository=membership_repo,
    )
    policy = build_eligibility_policy(org_id)
    service = PharmacologicalEligibilityService(
        fact_provider=fact_provider,
        policy=policy,
        rule=build_eligibility_rule(policy.policy_id, org_id),
        lot_rule=build_lot_eligibility_rule(policy.policy_id, org_id),
    )

    # 1. Lote REPROVADO: contém animal em carência.
    eval_1, decision_1 = service.evaluate_lot(org_id, lot.lot_id, datetime.now(UTC))
    assert decision_1.result is DecisionResult.REJEITADA
    fato_1 = eval_1.fact_snapshot.get_latest_fact_by_type(LOT_ELIGIBILITY_FACT_TYPE)
    assert fato_1 is not None
    assert fato_1.payload["blocking_animals"] == [animal_em_carencia.animal_id.value.hex]

    # 2. Remoção temporal do animal em carência.
    lot_service.remove_animal_from_lot(lot.lot_id, animal_em_carencia.animal_id)

    # 3. Reavaliação: lote APROVADO, agora só com o animal livre.
    eval_2, decision_2 = service.evaluate_lot(
        org_id, lot.lot_id, datetime.now(UTC) + timedelta(hours=1)
    )
    assert decision_2.result is DecisionResult.APROVADA
    fato_2 = eval_2.fact_snapshot.get_latest_fact_by_type(LOT_ELIGIBILITY_FACT_TYPE)
    assert fato_2 is not None
    assert fato_2.payload["blocking_animals"] == []
    assert fato_2.payload["member_count"] == 1

    # Ambas as decisões preservadas e distintas; o snapshot mudou (hash diferente).
    assert decision_1.decision_id != decision_2.decision_id
    assert eval_1.fact_snapshot.snapshot_hash != eval_2.fact_snapshot.snapshot_hash
