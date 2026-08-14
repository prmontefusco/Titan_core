"""T-05C2: carência histórica só usa material farmacológico comprovado."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from packages.core_domain.events import CanonicalPayload
from packages.livestock_application.event_recorder import AGGREGATE_CONTRACT_VERSION
from packages.livestock_application.fact_provider import (
    WITHDRAWAL_FACT_TYPE,
    LivestockFactProvider,
)
from packages.livestock_application.temporal_treatment import TemporalTreatmentApplicationReader
from packages.livestock_application.temporal_withdrawal import (
    TemporalWithdrawalLimitation,
    TemporalWithdrawalReader,
)
from packages.livestock_domain.events import (
    MEDICATION_BATCH_REGISTERED,
    MEDICATION_REGISTERED,
    TREATMENT_APPLIED,
    medication_batch_registered_payload,
    medication_registered_payload,
    treatment_applied_payload,
)
from packages.livestock_domain.medication import Medication, MedicationBatch
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@dataclass(frozen=True, slots=True)
class _Event:
    event_id: TypedId
    aggregate_reference: UniversalReference
    aggregate_version: int
    event_type: str
    event_version: int
    occurred_at: datetime
    recorded_at: datetime
    actor_reference: UniversalReference
    correlation_id: TypedId
    causation_id: TypedId | None
    payload_schema: str
    payload_version: int
    payload_canonical_bytes: bytes
    payload_digest: str
    integrity_hash: bytes | None = None


class _EventReader:
    def __init__(self, events: list[_Event]) -> None:
        self.events = events

    def list_canonical_for_aggregate(
        self, aggregate_reference: UniversalReference
    ) -> tuple[_Event, ...]:
        return tuple(
            item for item in self.events if item.aggregate_reference == aggregate_reference
        )


class _ApplicationRepo:
    def __init__(self, application: TreatmentApplication) -> None:
        self.application = application

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[TreatmentApplication]:
        if (
            self.application.organization_id == organization_id
            and self.application.animal_id == animal_id
        ):
            return [self.application]
        return []

    def save(self, application: TreatmentApplication) -> None: ...

    def get_by_id(self, application_id: TypedId) -> TreatmentApplication | None:
        return self.application if self.application.application_id == application_id else None

    def list_by_batch(
        self, organization_id: OrganizationId, medication_batch_id: TypedId
    ) -> list[TreatmentApplication]:
        return []


class _BatchRepo:
    def __init__(self, batch: MedicationBatch) -> None:
        self.batch = batch

    def get_by_id(self, batch_id: TypedId) -> MedicationBatch | None:
        return self.batch if self.batch.batch_id == batch_id else None

    def save(self, batch: MedicationBatch) -> None: ...

    def get_by_number(
        self, organization_id: OrganizationId, medication_id: TypedId, batch_number: str
    ) -> MedicationBatch | None:
        return None

    def list_by_medication(
        self, organization_id: OrganizationId, medication_id: TypedId
    ) -> list[MedicationBatch]:
        return []


class _MedicationRepo:
    def __init__(self, medication: Medication) -> None:
        self.medication = medication

    def get_by_id(self, medication_id: TypedId) -> Medication | None:
        return self.medication if self.medication.medication_id == medication_id else None

    def save(self, medication: Medication) -> None: ...

    def get_by_trade_name(
        self, organization_id: OrganizationId, trade_name: str
    ) -> Medication | None:
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Medication]:
        return []


def _event(
    organization_id: OrganizationId,
    aggregate_id: TypedId,
    event_type: str,
    occurred_at: datetime,
    payload: CanonicalPayload,
) -> _Event:
    return _Event(
        event_id=TypedId.new("domain_event"),
        aggregate_reference=UniversalReference(
            target_id=aggregate_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        ),
        aggregate_version=1,
        event_type=event_type,
        event_version=1,
        occurred_at=occurred_at,
        recorded_at=occurred_at,
        actor_reference=UniversalReference(
            target_id=TypedId.new("actor"), organization_id=organization_id, contract_version=1
        ),
        correlation_id=TypedId.new("correlation"),
        causation_id=None,
        payload_schema=payload.schema,
        payload_version=payload.version,
        payload_canonical_bytes=payload.canonical_bytes,
        payload_digest=hashlib.sha256(payload.canonical_bytes).hexdigest(),
    )


def _fixture(
    *, material_recorded_at: datetime
) -> tuple[
    OrganizationId,
    TypedId,
    TreatmentApplication,
    MedicationBatch,
    Medication,
    list[_Event],
]:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    medication = Medication(
        medication_id=TypedId.new("medication"),
        organization_id=organization_id,
        trade_name="Medicamento teste",
        active_ingredient="ingrediente",
        manufacturer="fabricante",
        withdrawal_period_days=10,
        created_at=material_recorded_at,
    )
    batch = MedicationBatch(
        batch_id=TypedId.new("medication_batch"),
        organization_id=organization_id,
        medication_id=medication.medication_id,
        batch_number="L-001",
        expiry_date=material_recorded_at + timedelta(days=365),
        created_at=material_recorded_at,
    )
    application = TreatmentApplication(
        application_id=TypedId.new("treatment_application"),
        organization_id=organization_id,
        animal_id=animal_id,
        medication_batch_id=batch.batch_id,
        actor_id=TypedId.new("actor"),
        applied_at=datetime(2026, 1, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    events = [
        _event(
            organization_id,
            medication.medication_id,
            MEDICATION_REGISTERED,
            medication.created_at,
            medication_registered_payload(
                medication_id=medication.medication_id,
                trade_name=medication.trade_name,
                active_ingredient=medication.active_ingredient,
                manufacturer=medication.manufacturer,
                withdrawal_period_days=medication.withdrawal_period_days,
                product_class=medication.product_class.value,
            ),
        ),
        _event(
            organization_id,
            batch.batch_id,
            MEDICATION_BATCH_REGISTERED,
            batch.created_at,
            medication_batch_registered_payload(
                batch_id=batch.batch_id,
                medication_id=batch.medication_id,
                batch_number=batch.batch_number,
                expiry_date=batch.expiry_date,
                manufacturing_date=batch.manufacturing_date,
            ),
        ),
        _event(
            organization_id,
            application.application_id,
            TREATMENT_APPLIED,
            application.applied_at,
            treatment_applied_payload(
                application_id=application.application_id,
                animal_id=application.animal_id,
                medication_batch_id=application.medication_batch_id,
                applied_at=application.applied_at,
                dose=application.dose,
                prescription_id=application.prescription_id,
                sanitary_campaign_id=application.sanitary_campaign_id,
                evidence_references=application.evidence_references,
                evidence_notes=application.evidence_notes,
                corrects_application_id=application.corrects_application_id,
            ),
        ),
    ]
    return organization_id, animal_id, application, batch, medication, events


def _reader(
    application: TreatmentApplication,
    batch: MedicationBatch,
    medication: Medication,
    events: list[_Event],
) -> TemporalWithdrawalReader:
    event_reader = _EventReader(events)
    treatment_reader = TemporalTreatmentApplicationReader(
        _ApplicationRepo(application), event_reader
    )
    return TemporalWithdrawalReader(
        treatment_reader=treatment_reader,
        batch_repository=_BatchRepo(batch),
        medication_repository=_MedicationRepo(medication),
        event_reader=event_reader,
    )


def test_material_known_after_cutoff_cannot_support_historical_withdrawal() -> None:
    org, animal, application, batch, medication, events = _fixture(
        material_recorded_at=datetime(2026, 1, 3, tzinfo=UTC)
    )
    reader = _reader(application, batch, medication, events)

    selection = reader.select(
        org,
        animal,
        reference_time=datetime(2026, 1, 2, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert selection.limitation is TemporalWithdrawalLimitation.MATERIAL_INSUFFICIENT


def test_withdrawal_uses_period_preserved_by_matching_medication_event() -> None:
    org, animal, application, batch, medication, events = _fixture(
        material_recorded_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    reader = _reader(application, batch, medication, events)

    selection = reader.select(
        org,
        animal,
        reference_time=datetime(2026, 1, 5, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 5, tzinfo=UTC),
    )

    assert selection.limitation is None
    assert selection.contributions[0].contribution.withdrawal_period_days == 10
    assert selection.contributions[0].contribution.withdrawal_ends_at == datetime(
        2026, 1, 11, tzinfo=UTC
    )


def test_current_material_that_diverges_from_canonical_event_fails_closed() -> None:
    org, animal, application, batch, medication, events = _fixture(
        material_recorded_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    changed_medication = Medication(
        medication_id=medication.medication_id,
        organization_id=medication.organization_id,
        trade_name=medication.trade_name,
        active_ingredient=medication.active_ingredient,
        manufacturer=medication.manufacturer,
        withdrawal_period_days=20,
        created_at=medication.created_at,
    )

    selection = _reader(application, batch, changed_medication, events).select(
        org,
        animal,
        reference_time=datetime(2026, 1, 5, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 5, tzinfo=UTC),
    )

    assert selection.limitation is TemporalWithdrawalLimitation.MATERIAL_INSUFFICIENT


def test_temporal_snapshot_emits_withdrawal_fact_without_current_calculator() -> None:
    org, animal, application, batch, medication, events = _fixture(
        material_recorded_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    reader = _reader(application, batch, medication, events)
    provider = LivestockFactProvider(
        property_repository=None,  # type: ignore[arg-type]
        animal_repository=None,  # type: ignore[arg-type]
        temporal_treatment_reader=reader.treatment_reader,
        temporal_withdrawal_reader=reader,
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        org,
        animal,
        reference_time=datetime(2026, 1, 5, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 5, tzinfo=UTC),
    )

    fact = next(item for item in snapshot.facts if item.fact_type == WITHDRAWAL_FACT_TYPE)
    assert fact.payload["in_withdrawal"] is True
    assert fact.payload["derivation"] == "TEMPORAL_TREATMENT_MATERIAL_V1"
