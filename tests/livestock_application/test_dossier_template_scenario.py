"""Cenário do dossiê farmacológico, montado só com operações reais dos serviços.

Vive fora do arquivo de testes porque é longo e porque o que ele monta — animal
com brinco, medicamento, lote, evidência e tratamento em carência — é o mesmo
cenário que o dossiê precisa explicar.

O nome começa com `test_` apenas para que a coleta do pytest o alcance junto dos
demais módulos de teste; ele não contém teste algum.
"""

from datetime import UTC, datetime, timedelta

from packages.core_domain.decision import Decision
from packages.core_domain.evaluation import Evaluation
from packages.livestock_application.animal_service import AnimalService
from packages.livestock_application.eligibility import (
    PharmacologicalEligibilityService,
    build_eligibility_policy,
    build_eligibility_rule,
)
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.fact_provider import LivestockFactProvider
from packages.livestock_application.medication_service import (
    MedicationBatchService,
    MedicationService,
)
from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_application.timeline_service import LivestockTimelineService
from packages.livestock_application.treatment_service import TreatmentApplicationService
from packages.livestock_application.withdrawal_service import WithdrawalCalculator
from packages.livestock_domain.animal import AnimalSex, IdentifierType
from packages.shared_kernel import TypedId
from tests.livestock_application.test_animal_service import InMemoryAnimalRepository
from tests.livestock_application.test_lot_service import InMemoryMembershipRepository
from tests.livestock_application.test_medication_service import (
    InMemoryBatchRepo,
    InMemoryMedicationRepo,
    InMemoryPrescriptionRepo,
    InMemoryPropRepo,
    InMemoryVetRepo,
)
from tests.livestock_application.test_movement_service import InMemoryMovementRepository
from tests.livestock_application.test_treatment_service import InMemoryApplicationRepo
from tests.livestock_support import (
    FakeDecisionRepository,
    FakeEvaluationRepository,
    FakeEvidenceLookup,
    FakeRelationRepository,
    ReadableEventLog,
)


class _AdvancingClock:
    """Instantes de registro distintos, para o corte por `known_until` ter o que cortar."""

    def __init__(self) -> None:
        self._current = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        self._current += timedelta(seconds=1)
        return self._current


class Cenario:
    """Animal em carência, com evidência anexada ao tratamento que a causou."""

    def __init__(self, context: LivestockOperationContext) -> None:
        self.context = context
        self.organization_id = context.organization_id
        self.event_log = ReadableEventLog()
        self.recorder = LivestockEventRecorder(event_log=self.event_log, clock=_AdvancingClock())

        self.animal_repository = InMemoryAnimalRepository()
        self.property_repository = InMemoryPropRepo()
        self.medication_repository = InMemoryMedicationRepo()
        self.batch_repository = InMemoryBatchRepo()
        self.application_repository = InMemoryApplicationRepo()
        self.membership_repository = InMemoryMembershipRepository()
        self.movement_repository = InMemoryMovementRepository()
        self.evidence_lookup = FakeEvidenceLookup()
        self.evaluations = FakeEvaluationRepository()
        self.decisions = FakeDecisionRepository()
        self.relations = FakeRelationRepository()

        property_service = RuralPropertyService(
            repository=self.property_repository, recorder=self.recorder
        )
        fazenda = property_service.register_property(
            context=context,
            code="FAZ-1",
            name="Fazenda Primavera",
            municipality="Uberaba",
            state_code="MG",
        )

        animal = AnimalService(
            repository=self.animal_repository, recorder=self.recorder
        ).register_animal(
            context=context,
            birth_property_id=fazenda.property_id,
            sex=AnimalSex.FEMALE,
            breed="Nelore",
            initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
            initial_identifier_value="BR12345678",
        )
        self.animal_id = animal.animal_id

        medication = MedicationService(
            medication_repository=self.medication_repository,
            prescription_repository=InMemoryPrescriptionRepo(),
            veterinarian_repository=InMemoryVetRepo(),
            property_repository=self.property_repository,
            recorder=self.recorder,
        ).register_medication(
            context=context,
            trade_name="Ivomec Gold",
            active_ingredient="Ivermectina",
            manufacturer="Boehringer",
            withdrawal_period_days=30,
        )
        self.batch_service = MedicationBatchService(
            batch_repository=self.batch_repository,
            medication_repository=self.medication_repository,
            recorder=self.recorder,
        )
        self.batch = self.batch_service.register_batch(
            context=context,
            medication_id=medication.medication_id,
            batch_number="LOTE-2026-001",
            expiry_date=datetime.now(UTC) + timedelta(days=365),
        )

        self.treatment_service = TreatmentApplicationService(
            application_repository=self.application_repository,
            animal_repository=self.animal_repository,
            batch_repository=self.batch_repository,
            prescription_repository=InMemoryPrescriptionRepo(),
            recorder=self.recorder,
            evidence_lookup=self.evidence_lookup,
        )
        # Tratamento há 10 dias, carência de 30: o animal está bloqueado.
        self.tratar(dias_atras=10)

        self.withdrawal = WithdrawalCalculator(
            application_repository=self.application_repository,
            batch_repository=self.batch_repository,
            medication_repository=self.medication_repository,
        )
        self.fact_provider = LivestockFactProvider(
            property_repository=self.property_repository,
            animal_repository=self.animal_repository,
            withdrawal_calculator=self.withdrawal,
        )
        self.policy = build_eligibility_policy(self.organization_id)
        self.rule = build_eligibility_rule(self.policy.policy_id, self.organization_id)
        self.eligibility = PharmacologicalEligibilityService(
            fact_provider=self.fact_provider,
            policy=self.policy,
            rule=self.rule,
            evaluation_repository=self.evaluations,
            decision_repository=self.decisions,
        )

    def tratar(self, dias_atras: int) -> TypedId:
        """Aplica um tratamento com evidência documental anexada."""
        referencia = self.evidence_lookup.add(self.organization_id)
        application = self.treatment_service.register_application(
            context=self.context,
            animal_id=self.animal_id,
            medication_batch_id=self.batch.batch_id,
            applied_at=datetime.now(UTC) - timedelta(days=dias_atras),
            dose="1 mL / 50 kg",
            evidence_references=(referencia,),
            evidence_notes=("foto no celular do João",),
        )
        return application.application_id

    def timeline_service(self) -> LivestockTimelineService:
        return LivestockTimelineService(
            event_reader=self.event_log,
            movement_repository=self.movement_repository,
            application_repository=self.application_repository,
            membership_repository=self.membership_repository,
            batch_repository=self.batch_repository,
            evaluation_repository=self.evaluations,
            decision_repository=self.decisions,
            relation_repository=self.relations,
        )

    def avaliar(self) -> tuple[Evaluation, Decision]:
        return self.eligibility.evaluate_animal(
            self.organization_id, self.animal_id, datetime.now(UTC)
        )
