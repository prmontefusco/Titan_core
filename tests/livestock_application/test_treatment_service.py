"""Testes unitários para TreatmentApplicationService (Passo 9.3 - Titan Livestock)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from packages.core_application import OutboxMessage
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.erp_contract import ERP_OPERATIONAL_INTENT_CONTRACT_TYPE
from packages.livestock_application.erp_outbox import LivestockErpOutboxService
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.exit_service import AnimalForaDoRebanho
from packages.livestock_application.medication_service import (
    MedicationBatchRepositoryPort,
    PrescriptionRepositoryPort,
)
from packages.livestock_application.treatment_service import (
    TreatmentApplicationRepositoryPort,
    TreatmentApplicationService,
)
from packages.livestock_domain.animal import Animal, AnimalSex, IdentifierType
from packages.livestock_domain.events import TREATMENT_APPLIED
from packages.livestock_domain.exit import AnimalExit, ExitType
from packages.livestock_domain.lot import LotMembership
from packages.livestock_domain.medication import MedicationBatch
from packages.livestock_domain.prescription import Prescription, PrescriptionTargetType
from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from tests.livestock_application.conftest import FakeEventLog
from tests.livestock_support import FakeEvidenceLookup


class InMemoryApplicationRepo(TreatmentApplicationRepositoryPort):
    def __init__(self) -> None:
        self.apps: dict[str, TreatmentApplication] = {}

    def save(self, application: TreatmentApplication) -> None:
        self.apps[application.application_id.value.hex] = application

    def get_by_id(self, application_id: TypedId) -> TreatmentApplication | None:
        return self.apps.get(application_id.value.hex)

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[TreatmentApplication]:
        return [
            a
            for a in self.apps.values()
            if a.organization_id == organization_id and a.animal_id == animal_id
        ]

    def list_by_batch(
        self, organization_id: OrganizationId, medication_batch_id: TypedId
    ) -> list[TreatmentApplication]:
        return [
            a
            for a in self.apps.values()
            if a.organization_id == organization_id and a.medication_batch_id == medication_batch_id
        ]


class InMemoryAnimalRepo(AnimalRepositoryPort):
    def __init__(self, animals: dict[str, Animal]) -> None:
        self.saidas: dict[str, AnimalExit] = {}
        self.animals = animals

    def save(self, animal: Animal) -> None:
        self.animals[animal.animal_id.value.hex] = animal

    def update(self, animal: Animal) -> None:
        self.animals[animal.animal_id.value.hex] = animal

    def get_by_id(self, animal_id: TypedId) -> Animal | None:
        return self.animals.get(animal_id.value.hex)

    def find_by_identifier(
        self,
        organization_id: OrganizationId,
        identifier_type: IdentifierType,
        identifier_value: str,
    ) -> Animal | None:
        return None

    def get_exit(self, animal_id: TypedId) -> AnimalExit | None:
        return self.saidas.get(animal_id.value.hex)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Animal]:
        return list(self.animals.values())


class InMemoryBatchRepo(MedicationBatchRepositoryPort):
    def __init__(self, batches: dict[str, MedicationBatch]) -> None:
        self.batches = batches

    def save(self, batch: MedicationBatch) -> None:
        self.batches[batch.batch_id.value.hex] = batch

    def get_by_id(self, batch_id: TypedId) -> MedicationBatch | None:
        return self.batches.get(batch_id.value.hex)

    def get_by_number(
        self, organization_id: OrganizationId, medication_id: TypedId, batch_number: str
    ) -> MedicationBatch | None:
        return None

    def list_by_medication(
        self, organization_id: OrganizationId, medication_id: TypedId
    ) -> list[MedicationBatch]:
        return list(self.batches.values())


class InMemoryPrescriptionRepo(PrescriptionRepositoryPort):
    def __init__(self) -> None:
        self.prescriptions: dict[str, Prescription] = {}

    def save(self, prescription: Prescription) -> None:
        self.prescriptions[prescription.prescription_id.value.hex] = prescription

    def get_by_id(self, prescription_id: TypedId) -> Prescription | None:
        return self.prescriptions.get(prescription_id.value.hex)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Prescription]:
        return list(self.prescriptions.values())


class InMemoryCampaignLookup:
    def __init__(self, campaigns: dict[str, SanitaryCampaign]) -> None:
        self.campaigns = campaigns

    def get_by_id(self, campaign_id: TypedId) -> SanitaryCampaign | None:
        return self.campaigns.get(campaign_id.value.hex)


class InMemoryLotMembershipLookup:
    def __init__(self) -> None:
        self.memberships: list[LotMembership] = []

    def get_memberships_for_lot(
        self, lot_id: TypedId, at_time: datetime | None = None
    ) -> list[LotMembership]:
        result = []
        for membership in self.memberships:
            if membership.lot_id != lot_id:
                continue
            if at_time is None:
                if membership.valid_until is None:
                    result.append(membership)
                continue
            if membership.valid_from <= at_time and (
                membership.valid_until is None or membership.valid_until > at_time
            ):
                result.append(membership)
        return result


class SpyOutboxWriter:
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []

    def append(self, message: OutboxMessage) -> None:
        self.messages.append(message)


def _scenario(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> tuple[TreatmentApplicationService, TypedId, TypedId, InMemoryApplicationRepo]:
    org_id = context.organization_id
    animal = Animal(
        animal_id=TypedId.new("animal"),
        organization_id=org_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.FEMALE,
    )
    batch = MedicationBatch(
        batch_id=TypedId.new("medication_batch"),
        organization_id=org_id,
        medication_id=TypedId.new("medication"),
        batch_number="LOTE-1",
        expiry_date=datetime.now(UTC) + timedelta(days=200),
    )
    app_repo = InMemoryApplicationRepo()
    service = TreatmentApplicationService(
        application_repository=app_repo,
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        batch_repository=InMemoryBatchRepo({batch.batch_id.value.hex: batch}),
        prescription_repository=InMemoryPrescriptionRepo(),
        recorder=recorder,
    )
    return service, animal.animal_id, batch.batch_id, app_repo


def _campaign(context: LivestockOperationContext) -> SanitaryCampaign:
    return SanitaryCampaign(
        campaign_id=TypedId.new("sanitary_campaign"),
        organization_id=context.organization_id,
        code="PNCEBT-BRUCELOSE-2026",
        name="Campanha Brucelose 2026",
        starts_at=datetime(2026, 1, 1, tzinfo=UTC),
        ends_at=datetime(2026, 12, 31, tzinfo=UTC),
    )


def _prescription(
    context: LivestockOperationContext,
    medication_id: TypedId,
    target_ids: tuple[TypedId, ...],
    target_type: PrescriptionTargetType = PrescriptionTargetType.ANIMAL,
) -> Prescription:
    return Prescription(
        prescription_id=TypedId.new("prescription"),
        organization_id=context.organization_id,
        veterinarian_id=TypedId.new("veterinarian"),
        medication_id=medication_id,
        property_id=TypedId.new("rural_property"),
        prescribed_date=datetime.now(UTC) - timedelta(days=1),
        dosage="1 mL",
        administration_route="SUBCUTANEA",
        target_type=target_type,
        target_ids=target_ids,
        reason="Tratamento ficticio.",
    )


def test_register_application_success(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, batch_id, _ = _scenario(recorder, context)

    app = service.register_application(
        context=context,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        dose="1 mL",
        evidence_notes=("foto no celular do João",),
    )
    assert app.corrects_application_id is None
    assert app.animal_id == animal_id
    # A autoria do registro vem do contexto, e é a mesma do evento.
    assert app.actor_id == context.actor_reference.target_id
    assert event_log.only(TREATMENT_APPLIED).actor_reference == context.actor_reference


def test_register_application_emits_erp_outbox_command(
    recorder: LivestockEventRecorder,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    writer = SpyOutboxWriter()
    service = replace(service, erp_outbox_service=LivestockErpOutboxService(writer=writer))

    app = service.register_application(
        context=context,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        dose="1 mL",
        evidence_notes=("observacao operacional",),
    )

    assert len(writer.messages) == 1
    message = writer.messages[0]
    assert message.contract_type == ERP_OPERATIONAL_INTENT_CONTRACT_TYPE
    assert message.kind.value == "COMMAND"
    assert message.causation_id.entity_type == "domain_event"
    assert str(app.application_id.value).encode() in message.payload.canonical_bytes
    assert b"external_operation_id" in message.payload.canonical_bytes
    assert b"contract_profile" in message.payload.canonical_bytes
    assert b"authoritative_source" in message.payload.canonical_bytes
    assert b"titan" in message.payload.canonical_bytes


def test_refused_registration_does_not_emit_erp_outbox_command(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, _, _ = _scenario(recorder, context)
    writer = SpyOutboxWriter()
    service = replace(service, erp_outbox_service=LivestockErpOutboxService(writer=writer))

    with pytest.raises(KeyError, match="Lote"):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=TypedId.new("medication_batch"),
            applied_at=datetime.now(UTC),
        )

    assert event_log.events == []
    assert writer.messages == []


def test_register_application_accepts_prescription_for_same_medication_and_animal(
    recorder: LivestockEventRecorder,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    batch_repo = service.batch_repository
    prescription_repo = service.prescription_repository
    assert isinstance(batch_repo, InMemoryBatchRepo)
    assert isinstance(prescription_repo, InMemoryPrescriptionRepo)
    batch = batch_repo.get_by_id(batch_id)
    assert batch is not None
    prescription = _prescription(context, batch.medication_id, (animal_id,))
    prescription_repo.save(prescription)

    app = service.register_application(
        context=context,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        prescription_id=prescription.prescription_id,
    )

    assert app.prescription_id == prescription.prescription_id


def test_register_application_rejects_prescription_for_other_medication(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    prescription_repo = service.prescription_repository
    assert isinstance(prescription_repo, InMemoryPrescriptionRepo)
    prescription = _prescription(context, TypedId.new("medication"), (animal_id,))
    prescription_repo.save(prescription)

    with pytest.raises(ValueError, match="medicamento aplicado"):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=batch_id,
            applied_at=datetime.now(UTC) - timedelta(hours=1),
            prescription_id=prescription.prescription_id,
        )

    assert event_log.events == []


def test_register_application_rejects_prescription_for_other_animal(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    batch_repo = service.batch_repository
    prescription_repo = service.prescription_repository
    assert isinstance(batch_repo, InMemoryBatchRepo)
    assert isinstance(prescription_repo, InMemoryPrescriptionRepo)
    batch = batch_repo.get_by_id(batch_id)
    assert batch is not None
    prescription = _prescription(context, batch.medication_id, (TypedId.new("animal"),))
    prescription_repo.save(prescription)

    with pytest.raises(ValueError, match="este animal"):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=batch_id,
            applied_at=datetime.now(UTC) - timedelta(hours=1),
            prescription_id=prescription.prescription_id,
        )

    assert event_log.events == []


def test_register_application_accepts_lot_prescription_when_animal_was_member(
    recorder: LivestockEventRecorder,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    lot_id = TypedId.new("livestock_lot")
    membership_lookup = InMemoryLotMembershipLookup()
    applied_at = datetime.now(UTC) - timedelta(hours=1)
    membership_lookup.memberships.append(
        LotMembership(
            membership_id=TypedId.new("lot_membership"),
            lot_id=lot_id,
            animal_id=animal_id,
            valid_from=applied_at - timedelta(hours=1),
        )
    )
    service = replace(service, lot_membership_lookup=membership_lookup)
    batch_repo = service.batch_repository
    prescription_repo = service.prescription_repository
    assert isinstance(batch_repo, InMemoryBatchRepo)
    assert isinstance(prescription_repo, InMemoryPrescriptionRepo)
    batch = batch_repo.get_by_id(batch_id)
    assert batch is not None
    prescription = _prescription(
        context,
        batch.medication_id,
        (lot_id,),
        target_type=PrescriptionTargetType.LOT,
    )
    prescription_repo.save(prescription)

    app = service.register_application(
        context=context,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        applied_at=applied_at,
        prescription_id=prescription.prescription_id,
    )

    assert app.prescription_id == prescription.prescription_id


def test_register_application_rejects_lot_prescription_without_temporal_membership(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    service = replace(service, lot_membership_lookup=InMemoryLotMembershipLookup())
    batch_repo = service.batch_repository
    prescription_repo = service.prescription_repository
    assert isinstance(batch_repo, InMemoryBatchRepo)
    assert isinstance(prescription_repo, InMemoryPrescriptionRepo)
    batch = batch_repo.get_by_id(batch_id)
    assert batch is not None
    prescription = _prescription(
        context,
        batch.medication_id,
        (TypedId.new("livestock_lot"),),
        target_type=PrescriptionTargetType.LOT,
    )
    prescription_repo.save(prescription)

    with pytest.raises(ValueError, match="lote informado"):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=batch_id,
            applied_at=datetime.now(UTC) - timedelta(hours=1),
            prescription_id=prescription.prescription_id,
        )

    assert event_log.events == []


def test_register_application_can_link_sanitary_campaign(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    campaign = _campaign(context)
    service = replace(
        service,
        campaign_lookup=InMemoryCampaignLookup({campaign.campaign_id.value.hex: campaign}),
    )

    app = service.register_application(
        context=context,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        applied_at=datetime(2026, 7, 1, tzinfo=UTC),
        sanitary_campaign_id=campaign.campaign_id,
    )

    assert app.sanitary_campaign_id == campaign.campaign_id
    assert (
        str(campaign.campaign_id.value).encode()
        in event_log.only(TREATMENT_APPLIED).payload.canonical_bytes
    )


def test_register_application_rejects_campaign_outside_window(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    campaign = _campaign(context)
    service = replace(
        service,
        campaign_lookup=InMemoryCampaignLookup({campaign.campaign_id.value.hex: campaign}),
    )

    with pytest.raises(ValueError, match="janela de vigencia"):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=batch_id,
            applied_at=datetime(2027, 1, 1, tzinfo=UTC),
            sanitary_campaign_id=campaign.campaign_id,
        )

    assert event_log.events == []


def test_correction_creates_new_record_preserving_original(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """O cenário do plano: não se edita; corrige-se por um novo evento."""
    service, animal_id, batch_id, app_repo = _scenario(recorder, context)

    original = service.register_application(
        context=context,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        applied_at=datetime.now(UTC) - timedelta(hours=2),
        dose="1 mL",
    )

    correction = service.correct_application(
        context=context,
        original_application_id=original.application_id,
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        dose="2 mL",  # a dose correta
    )

    # A correção é um NOVO registro que aponta para o original.
    assert correction.application_id != original.application_id
    assert correction.corrects_application_id == original.application_id
    assert correction.animal_id == original.animal_id
    assert correction.medication_batch_id == original.medication_batch_id

    # Ambos permanecem: o histórico só cresce, o original é imutável.
    assert app_repo.get_by_id(original.application_id) is not None
    assert app_repo.get_by_id(original.application_id).dose == "1 mL"  # type: ignore[union-attr]
    assert len(app_repo.apps) == 2

    # Dois registros, dois fluxos: a correção não reescreve o evento original, e
    # o vínculo entre eles viaja no payload.
    events = event_log.of_type(TREATMENT_APPLIED)
    assert len(events) == 2
    assert [event.aggregate_version for event in events] == [1, 1]
    assert events[0].aggregate_reference.target_id == original.application_id
    assert events[1].aggregate_reference.target_id == correction.application_id
    assert str(original.application_id.value).encode() in events[1].payload.canonical_bytes


def test_register_application_rejects_future_time(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, batch_id, _ = _scenario(recorder, context)

    with pytest.raises(ValueError, match="não pode ser no futuro"):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=batch_id,
            applied_at=datetime.now(UTC) + timedelta(days=1),
        )

    assert event_log.events == []


def test_register_application_rejects_unknown_batch(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, _, _ = _scenario(recorder, context)

    with pytest.raises(KeyError, match="Lote"):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=TypedId.new("medication_batch"),
            applied_at=datetime.now(UTC),
        )

    assert event_log.events == []


# -- Evidência tipada (Passo 10.2a) -------------------------------------------


def _com_evidencia(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> tuple[TreatmentApplicationService, TypedId, TypedId, FakeEvidenceLookup]:
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    lookup = FakeEvidenceLookup()
    return replace(service, evidence_lookup=lookup), animal_id, batch_id, lookup


def test_typed_evidence_is_recorded_and_reaches_the_event(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """Referência tipada aponta para `Evidence` do Core, com hash e proveniência."""
    service, animal_id, batch_id, lookup = _com_evidencia(recorder, context)
    referencia = lookup.add(context.organization_id)

    application = service.register_application(
        context=context,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        evidence_references=(referencia,),
    )

    assert application.evidence_references == (referencia,)
    payload = event_log.only(TREATMENT_APPLIED).payload.canonical_bytes
    assert str(referencia.target_id.value).encode() in payload


def test_citing_evidence_that_does_not_exist_is_refused(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """Um dossiê que apontasse para o nada seria prova vazia."""
    service, animal_id, batch_id, _ = _com_evidencia(recorder, context)
    inexistente = UniversalReference(
        target_id=TypedId.new("evidence"),
        organization_id=context.organization_id,
        contract_version=1,
    )

    with pytest.raises(KeyError, match="não encontrada"):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=batch_id,
            applied_at=datetime.now(UTC) - timedelta(hours=1),
            evidence_references=(inexistente,),
        )

    assert event_log.events == []


def test_evidence_of_another_organization_is_indistinguishable_from_absent(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """A recusa não revela que a evidência existe noutra organização.

    Mensagem distinta viraria oráculo: bastaria tentar identificadores para
    descobrir o que outra organização possui.
    """
    service, animal_id, batch_id, lookup = _com_evidencia(recorder, context)
    alheia = lookup.add(OrganizationId.new())

    with pytest.raises(KeyError, match="não encontrada"):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=batch_id,
            applied_at=datetime.now(UTC) - timedelta(hours=1),
            evidence_references=(alheia,),
        )


def test_domain_refuses_evidence_of_another_organization(
    context: LivestockOperationContext,
) -> None:
    """Segunda linha de defesa: vale mesmo para quem construir a entidade direto."""
    alheia = UniversalReference(
        target_id=TypedId.new("evidence"),
        organization_id=OrganizationId.new(),
        contract_version=1,
    )

    with pytest.raises(ValueError, match="outra Organization"):
        TreatmentApplication(
            application_id=TypedId.new("treatment_application"),
            organization_id=context.organization_id,
            animal_id=TypedId.new("animal"),
            medication_batch_id=TypedId.new("medication_batch"),
            actor_id=TypedId.new("actor"),
            applied_at=datetime.now(UTC),
            evidence_references=(alheia,),
        )


def test_free_text_cannot_pose_as_evidence(context: LivestockOperationContext) -> None:
    """Anotação de operador é informação útil e não é prova; o tipo separa as duas."""
    with pytest.raises(TypeError, match="evidence_notes"):
        TreatmentApplication(
            application_id=TypedId.new("treatment_application"),
            organization_id=context.organization_id,
            animal_id=TypedId.new("animal"),
            medication_batch_id=TypedId.new("medication_batch"),
            actor_id=TypedId.new("actor"),
            applied_at=datetime.now(UTC),
            evidence_references=("evidence:foto-1",),  # type: ignore[arg-type]
        )


def test_notes_travel_beside_the_evidence_without_being_it(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, batch_id, lookup = _com_evidencia(recorder, context)
    referencia = lookup.add(context.organization_id)

    application = service.register_application(
        context=context,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        evidence_references=(referencia,),
        evidence_notes=("foto no celular do João",),
    )

    assert application.evidence_notes == ("foto no celular do João",)
    payload = event_log.only(TREATMENT_APPLIED).payload.canonical_bytes
    assert "foto no celular do João".encode() in payload


def test_correction_may_bring_the_evidence_the_original_lacked(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """Corrigir para anexar a prova que faltava é o caso comum em campo."""
    service, animal_id, batch_id, lookup = _com_evidencia(recorder, context)
    original = service.register_application(
        context=context,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        applied_at=datetime.now(UTC) - timedelta(hours=2),
    )
    referencia = lookup.add(context.organization_id)

    correction = service.correct_application(
        context=context,
        original_application_id=original.application_id,
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        evidence_references=(referencia,),
    )

    assert original.evidence_references == ()
    assert correction.evidence_references == (referencia,)


def test_service_without_lookup_refuses_to_accept_evidence(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """Aceitar referência sem poder conferi-la seria confiar no chamador."""
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    referencia = UniversalReference(
        target_id=TypedId.new("evidence"),
        organization_id=context.organization_id,
        contract_version=1,
    )

    with pytest.raises(RuntimeError, match="evidence_lookup"):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=batch_id,
            applied_at=datetime.now(UTC) - timedelta(hours=1),
            evidence_references=(referencia,),
        )


def _saida_em(animal_id: TypedId, organization_id: OrganizationId, quando: datetime) -> AnimalExit:
    return AnimalExit(
        exit_id=TypedId.new("animal_exit"),
        organization_id=organization_id,
        animal_id=animal_id,
        exit_type=ExitType.ABATE,
        occurred_at=quando,
    )


def test_tratamento_posterior_a_saida_e_recusado(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """A guarda da saída está ligada no serviço de tratamento, e não só no domínio."""
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    animal_repo = service.animal_repository
    assert isinstance(animal_repo, InMemoryAnimalRepo)
    saiu_em = datetime.now(UTC) - timedelta(days=5)
    animal_repo.saidas[animal_id.value.hex] = _saida_em(animal_id, context.organization_id, saiu_em)
    event_log.events.clear()

    with pytest.raises(AnimalForaDoRebanho, match="deixou o rebanho"):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=batch_id,
            applied_at=saiu_em + timedelta(days=1),
        )

    # Recusa não deixa rastro: o log só recebe o que aconteceu.
    assert event_log.events == []


def test_tratamento_anterior_a_saida_continua_aceito(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    service, animal_id, batch_id, _ = _scenario(recorder, context)
    animal_repo = service.animal_repository
    assert isinstance(animal_repo, InMemoryAnimalRepo)
    saiu_em = datetime.now(UTC) - timedelta(days=5)
    animal_repo.saidas[animal_id.value.hex] = _saida_em(animal_id, context.organization_id, saiu_em)

    aplicacao = service.register_application(
        context=context,
        animal_id=animal_id,
        medication_batch_id=batch_id,
        applied_at=saiu_em - timedelta(days=2),
    )

    assert aplicacao.animal_id == animal_id
