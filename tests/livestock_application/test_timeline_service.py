"""Linha do tempo da vertical (Passo 10.1b).

O que estes testes protegem: a ordem é total e reproduzível, a correção não
apaga o corrigido, o corte bitemporal separa "o que aconteceu" de "o que se
sabia", e nada é lido do estado atual.
"""

from datetime import UTC, datetime, timedelta

import pytest

from packages.livestock_application.animal_service import AnimalService
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.lot_service import LotService
from packages.livestock_application.medication_service import (
    MedicationBatchService,
    MedicationService,
)
from packages.livestock_application.movement_service import MovementService
from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_application.timeline_service import (
    DECISION_ENTRY_TYPE,
    EVALUATION_ENTRY_TYPE,
    LivestockTimelineService,
    TimelineCutoff,
    TimelineSourceKind,
)
from packages.livestock_application.treatment_service import TreatmentApplicationService
from packages.livestock_domain.animal import AnimalSex, IdentifierType
from packages.livestock_domain.events import (
    ANIMAL_ADDED_TO_LOT,
    ANIMAL_MOVED,
    ANIMAL_REGISTERED,
    ANIMAL_REMOVED_FROM_LOT,
    IDENTIFIER_ATTACHED,
    LOT_CREATED,
    TREATMENT_APPLIED,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.test_animal_service import InMemoryAnimalRepository
from tests.livestock_application.test_lot_service import (
    InMemoryLotRepository,
    InMemoryMembershipRepository,
)
from tests.livestock_application.test_medication_service import (
    InMemoryBatchRepo,
    InMemoryMedicationRepo,
    InMemoryPrescriptionRepo,
    InMemoryPropRepo,
    InMemoryVetRepo,
)
from tests.livestock_application.test_movement_service import (
    InMemoryMovementRepository,
    InMemoryPropertyStayRepository,
)
from tests.livestock_application.test_treatment_service import InMemoryApplicationRepo
from tests.livestock_support import (
    FakeDecisionRepository,
    FakeEvaluationRepository,
    ReadableEventLog,
)


class Scenario:
    """Um rebanho pequeno, montado só com as operações reais dos serviços."""

    def __init__(self, context: LivestockOperationContext) -> None:
        self.context = context
        self.organization_id = context.organization_id
        self.event_log = ReadableEventLog()
        self.recorder = LivestockEventRecorder(event_log=self.event_log, clock=_AdvancingClock())

        self.animal_repository = InMemoryAnimalRepository()
        self.property_repository = InMemoryPropRepo()
        self.movement_repository = InMemoryMovementRepository()
        self.membership_repository = InMemoryMembershipRepository()
        self.lot_repository = InMemoryLotRepository()
        self.application_repository = InMemoryApplicationRepo()
        self.medication_repository = InMemoryMedicationRepo()
        self.batch_repository = InMemoryBatchRepo()
        self.evaluations = FakeEvaluationRepository()
        self.decisions = FakeDecisionRepository()

        self.property_service = RuralPropertyService(
            repository=self.property_repository, recorder=self.recorder
        )
        self.animal_service = AnimalService(
            repository=self.animal_repository, recorder=self.recorder
        )
        self.movement_service = MovementService(
            movement_repository=self.movement_repository,
            stay_repository=InMemoryPropertyStayRepository(),
            animal_repository=self.animal_repository,
            property_repository=self.property_repository,
            recorder=self.recorder,
        )
        self.lot_service = LotService(
            lot_repository=self.lot_repository,
            membership_repository=self.membership_repository,
            animal_repository=self.animal_repository,
            property_repository=self.property_repository,
            recorder=self.recorder,
        )
        self.medication_service = MedicationService(
            medication_repository=self.medication_repository,
            prescription_repository=InMemoryPrescriptionRepo(),
            veterinarian_repository=InMemoryVetRepo(),
            property_repository=self.property_repository,
            recorder=self.recorder,
        )
        self.batch_service = MedicationBatchService(
            batch_repository=self.batch_repository,
            medication_repository=self.medication_repository,
            recorder=self.recorder,
        )
        self.treatment_service = TreatmentApplicationService(
            application_repository=self.application_repository,
            animal_repository=self.animal_repository,
            batch_repository=self.batch_repository,
            prescription_repository=InMemoryPrescriptionRepo(),
            recorder=self.recorder,
        )

    def timeline_service(self) -> LivestockTimelineService:
        return LivestockTimelineService(
            event_reader=self.event_log,
            movement_repository=self.movement_repository,
            application_repository=self.application_repository,
            membership_repository=self.membership_repository,
            batch_repository=self.batch_repository,
            evaluation_repository=self.evaluations,
            decision_repository=self.decisions,
        )


class _AdvancingClock:
    """Relógio de registro que avança a cada leitura.

    Instantes de registro distintos são o que permite exercitar o corte por
    `known_until` sem depender da resolução do relógio da máquina.
    """

    def __init__(self) -> None:
        self._current = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        self._current += timedelta(seconds=1)
        return self._current


def build_herd(context: LivestockOperationContext) -> tuple[Scenario, TypedId, TypedId]:
    """Fazenda, animal com brinco, lote com entrada e saída, e uma movimentação."""
    scenario = Scenario(context)
    origem = scenario.property_service.register_property(
        context=context, code="ORIG", name="Origem", municipality="Franca", state_code="SP"
    )
    destino = scenario.property_service.register_property(
        context=context, code="DEST", name="Destino", municipality="Batatais", state_code="SP"
    )
    animal = scenario.animal_service.register_animal(
        context=context,
        birth_property_id=origem.property_id,
        sex=AnimalSex.FEMALE,
        initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
        initial_identifier_value="BR12345678",
    )
    lot = scenario.lot_service.create_lot(
        context=context, property_id=origem.property_id, code="L-1", name="Lote 1"
    )
    scenario.lot_service.add_animal_to_lot(context, lot.lot_id, animal.animal_id)
    scenario.lot_service.remove_animal_from_lot(context, lot.lot_id, animal.animal_id)
    scenario.movement_service.register_movement(
        context=context,
        origin_property_id=origem.property_id,
        destination_property_id=destino.property_id,
        movement_time=datetime.now(UTC) - timedelta(hours=1),
        animal_ids=(animal.animal_id,),
    )
    return scenario, animal.animal_id, lot.lot_id


def test_animal_timeline_gathers_the_streams_of_everything_that_touched_it(
    context: LivestockOperationContext,
) -> None:
    scenario, animal_id, lot_id = build_herd(context)

    entries = scenario.timeline_service().animal_timeline(scenario.organization_id, animal_id)

    types = [entry.entry_type for entry in entries]
    assert ANIMAL_REGISTERED in types
    assert IDENTIFIER_ATTACHED in types
    assert LOT_CREATED in types
    assert ANIMAL_ADDED_TO_LOT in types
    assert ANIMAL_REMOVED_FROM_LOT in types
    assert ANIMAL_MOVED in types
    # A propriedade não entra: ela não é do histórico do animal.
    assert "livestock.property_registered" not in types


def test_the_order_is_total_and_reproducible(context: LivestockOperationContext) -> None:
    """Duas leituras precisam ser idênticas, não apenas parecidas."""
    scenario, animal_id, _ = build_herd(context)
    service = scenario.timeline_service()

    first = service.animal_timeline(scenario.organization_id, animal_id)
    second = service.animal_timeline(scenario.organization_id, animal_id)

    assert first == second
    assert [entry.sort_key() for entry in first] == sorted(entry.sort_key() for entry in first)


def test_registration_never_appears_after_what_followed_it(
    context: LivestockOperationContext,
) -> None:
    scenario, animal_id, _ = build_herd(context)

    entries = scenario.timeline_service().animal_timeline(scenario.organization_id, animal_id)

    positions = {entry.entry_type: index for index, entry in enumerate(entries)}
    assert positions[ANIMAL_REGISTERED] < positions[ANIMAL_ADDED_TO_LOT]
    assert positions[ANIMAL_ADDED_TO_LOT] < positions[ANIMAL_REMOVED_FROM_LOT]


def test_lot_timeline_keeps_the_entry_that_a_removal_closed(
    context: LivestockOperationContext,
) -> None:
    """Remover fecha a vigência; a entrada continua na história do lote."""
    scenario, _, lot_id = build_herd(context)

    entries = scenario.timeline_service().lot_timeline(scenario.organization_id, lot_id)

    assert [entry.entry_type for entry in entries] == [
        LOT_CREATED,
        ANIMAL_ADDED_TO_LOT,
        ANIMAL_REMOVED_FROM_LOT,
    ]


def treat(scenario: Scenario, animal_id: TypedId, hours_ago: int, dose: str) -> TypedId:
    medication = scenario.medication_service.register_medication(
        context=scenario.context,
        trade_name=f"Med-{hours_ago}",
        active_ingredient="Ivermectina",
        manufacturer="Fab",
        withdrawal_period_days=30,
    )
    batch = scenario.batch_service.register_batch(
        context=scenario.context,
        medication_id=medication.medication_id,
        batch_number=f"LOTE-{hours_ago}",
        expiry_date=datetime.now(UTC) + timedelta(days=365),
    )
    application = scenario.treatment_service.register_application(
        context=scenario.context,
        animal_id=animal_id,
        medication_batch_id=batch.batch_id,
        applied_at=datetime.now(UTC) - timedelta(hours=hours_ago),
        dose=dose,
    )
    return application.application_id


def test_a_correction_marks_the_original_without_removing_it(
    context: LivestockOperationContext,
) -> None:
    """O corrigido continua na linha do tempo, apontando para quem o corrigiu."""
    scenario, animal_id, _ = build_herd(context)
    original_id = treat(scenario, animal_id, hours_ago=3, dose="1 mL")
    correction = scenario.treatment_service.correct_application(
        context=context,
        original_application_id=original_id,
        applied_at=datetime.now(UTC) - timedelta(hours=2),
        dose="2 mL",
    )

    entries = scenario.timeline_service().animal_timeline(scenario.organization_id, animal_id)
    treatments = [entry for entry in entries if entry.entry_type == TREATMENT_APPLIED]

    assert len(treatments) == 2, "O registro corrigido não pode desaparecer."
    original_entry = next(entry for entry in treatments if entry.aggregate_id == original_id)
    correction_entry = next(
        entry for entry in treatments if entry.aggregate_id == correction.application_id
    )
    assert original_entry.superseded_by == correction.application_id
    assert correction_entry.superseded_by is None


def test_treatment_timeline_shows_the_batch_and_the_correction_chain(
    context: LivestockOperationContext,
) -> None:
    scenario, animal_id, _ = build_herd(context)
    original_id = treat(scenario, animal_id, hours_ago=3, dose="1 mL")
    correction = scenario.treatment_service.correct_application(
        context=context,
        original_application_id=original_id,
        applied_at=datetime.now(UTC) - timedelta(hours=2),
        dose="2 mL",
    )

    entries = scenario.timeline_service().treatment_timeline(scenario.organization_id, original_id)

    aggregates = {entry.aggregate_id for entry in entries}
    assert original_id in aggregates
    assert correction.application_id in aggregates
    assert any(entry.entry_type == "livestock.medication_batch_registered" for entry in entries)
    assert any(entry.entry_type == "livestock.medication_registered" for entry in entries)


def test_treatment_timeline_refuses_an_application_of_another_organization(
    context: LivestockOperationContext,
) -> None:
    scenario, animal_id, _ = build_herd(context)
    application_id = treat(scenario, animal_id, hours_ago=3, dose="1 mL")
    service = scenario.timeline_service()

    with pytest.raises(KeyError, match="não encontrada"):
        service.treatment_timeline(OrganizationId.new(), application_id)


def test_occurred_until_cuts_by_when_the_fact_happened(
    context: LivestockOperationContext,
) -> None:
    scenario, animal_id, _ = build_herd(context)
    treat(scenario, animal_id, hours_ago=2, dose="1 mL")
    service = scenario.timeline_service()

    complete = service.animal_timeline(scenario.organization_id, animal_id)
    cut = service.animal_timeline(
        scenario.organization_id,
        animal_id,
        TimelineCutoff(occurred_until=datetime.now(UTC) - timedelta(hours=3)),
    )

    assert len(cut) < len(complete)
    assert all(entry.occurred_at <= datetime.now(UTC) - timedelta(hours=3) for entry in cut)
    assert TREATMENT_APPLIED not in [entry.entry_type for entry in cut]


def test_known_until_cuts_by_what_titan_knew_then(
    context: LivestockOperationContext,
) -> None:
    """O eixo de auditoria: um lançamento atrasado não pode aparecer no passado.

    O tratamento ocorreu horas atrás, mas só foi registrado agora. Uma
    reconstrução do que se sabia antes do registro não pode contê-lo, ainda que o
    fato em si seja antigo.
    """
    scenario, animal_id, _ = build_herd(context)
    before_the_treatment_was_entered = scenario.recorder.clock.now()
    treat(scenario, animal_id, hours_ago=5, dose="1 mL")
    service = scenario.timeline_service()

    known_then = service.animal_timeline(
        scenario.organization_id,
        animal_id,
        TimelineCutoff(known_until=before_the_treatment_was_entered),
    )
    known_now = service.animal_timeline(scenario.organization_id, animal_id)

    assert TREATMENT_APPLIED not in [entry.entry_type for entry in known_then]
    assert TREATMENT_APPLIED in [entry.entry_type for entry in known_now]


def test_evaluations_and_decisions_appear_as_their_own_entries(
    context: LivestockOperationContext,
) -> None:
    """Sem elas, o bloqueio por carência não apareceria na linha do tempo."""
    from tests.livestock_application.test_eligibility_service import _service

    animal_id = TypedId.new("animal")
    scenario = Scenario(context)
    eligibility, evaluations, decisions = _service(
        animal_id,
        applied_days_ago=10,
        withdrawal_days=30,
        recorder=scenario.recorder,
        context=context,
    )
    eligibility.evaluate_animal(scenario.organization_id, animal_id, datetime.now(UTC))

    service = LivestockTimelineService(
        event_reader=scenario.event_log,
        movement_repository=scenario.movement_repository,
        application_repository=scenario.application_repository,
        membership_repository=scenario.membership_repository,
        batch_repository=scenario.batch_repository,
        evaluation_repository=evaluations,
        decision_repository=decisions,
    )
    entries = service.animal_timeline(scenario.organization_id, animal_id)

    kinds = {entry.source_kind for entry in entries}
    assert TimelineSourceKind.EVALUATION in kinds
    assert TimelineSourceKind.DECISION in kinds
    assert EVALUATION_ENTRY_TYPE in [entry.entry_type for entry in entries]
    assert DECISION_ENTRY_TYPE in [entry.entry_type for entry in entries]


def test_cutoff_refuses_naive_instants(context: LivestockOperationContext) -> None:
    """Instante sem timezone nunca é tratado como UTC em silêncio."""
    with pytest.raises(ValueError, match="timezone"):
        TimelineCutoff(occurred_until=datetime(2026, 7, 1, 12, 0))  # noqa: DTZ001

    with pytest.raises(ValueError, match="timezone"):
        TimelineCutoff(known_until=datetime(2026, 7, 1, 12, 0))  # noqa: DTZ001


def test_an_animal_of_another_organization_yields_nothing(
    context: LivestockOperationContext,
) -> None:
    scenario, animal_id, _ = build_herd(context)

    entries = scenario.timeline_service().animal_timeline(OrganizationId.new(), animal_id)

    assert entries == ()
