"""Cálculo histórico estrito de carência a partir de material imutável."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from packages.core_application.event_log import CanonicalDomainEventReader, RecordedCanonicalEvent
from packages.livestock_application.event_recorder import AGGREGATE_CONTRACT_VERSION
from packages.livestock_application.medication_service import (
    MedicationBatchRepositoryPort,
    MedicationRepositoryPort,
)
from packages.livestock_application.temporal_treatment import (
    TemporalTreatmentApplication,
    TemporalTreatmentApplicationReader,
)
from packages.livestock_domain.events import (
    MEDICATION_BATCH_REGISTERED,
    MEDICATION_REGISTERED,
    medication_batch_registered_payload,
    medication_registered_payload,
)
from packages.livestock_domain.medication import Medication, MedicationBatch
from packages.livestock_domain.withdrawal import (
    AnimalWithdrawalStatus,
    WithdrawalContribution,
    build_animal_withdrawal_status,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class TemporalWithdrawalLimitation(StrEnum):
    TREATMENT_HISTORY_INSUFFICIENT = "LIVESTOCK_TEMPORAL_WITHDRAWAL_TREATMENT_HISTORY_INSUFFICIENT"
    MATERIAL_INSUFFICIENT = "LIVESTOCK_TEMPORAL_WITHDRAWAL_MATERIAL_INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class TemporalWithdrawalContribution:
    contribution: WithdrawalContribution
    application_event_id: TypedId
    application_payload_digest: str
    batch_id: TypedId
    batch_event_id: TypedId
    batch_payload_digest: str
    medication_id: TypedId
    medication_event_id: TypedId
    medication_payload_digest: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class TemporalWithdrawalSelection:
    contributions: tuple[TemporalWithdrawalContribution, ...]
    limitation: TemporalWithdrawalLimitation | None


@dataclass(frozen=True, slots=True)
class TemporalWithdrawalReader:
    treatment_reader: TemporalTreatmentApplicationReader
    batch_repository: MedicationBatchRepositoryPort
    medication_repository: MedicationRepositoryPort
    event_reader: CanonicalDomainEventReader

    def select(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        *,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> TemporalWithdrawalSelection:
        treatments = self.treatment_reader.select(
            organization_id,
            animal_id,
            reference_time=reference_time,
            knowledge_cutoff=knowledge_cutoff,
        )
        if treatments.limitation is not None:
            return TemporalWithdrawalSelection(
                (), TemporalWithdrawalLimitation.TREATMENT_HISTORY_INSUFFICIENT
            )

        contributions: list[TemporalWithdrawalContribution] = []
        for treatment in treatments.effective_applications:
            contribution = self._contribution_for(
                organization_id,
                treatment,
                knowledge_cutoff=knowledge_cutoff,
            )
            if contribution is None:
                return TemporalWithdrawalSelection(
                    (), TemporalWithdrawalLimitation.MATERIAL_INSUFFICIENT
                )
            contributions.append(contribution)
        return TemporalWithdrawalSelection(tuple(contributions), None)

    def _contribution_for(
        self,
        organization_id: OrganizationId,
        treatment: TemporalTreatmentApplication,
        *,
        knowledge_cutoff: datetime,
    ) -> TemporalWithdrawalContribution | None:
        application = treatment.application
        batch = self.batch_repository.get_by_id(application.medication_batch_id)
        if (
            batch is None
            or batch.organization_id != organization_id
            or batch.created_at > knowledge_cutoff
        ):
            return None
        batch_event = self._matching_batch_event(
            organization_id, batch, knowledge_cutoff=knowledge_cutoff
        )
        if batch_event is None:
            return None

        medication = self.medication_repository.get_by_id(batch.medication_id)
        if (
            medication is None
            or medication.organization_id != organization_id
            or medication.created_at > knowledge_cutoff
        ):
            return None
        medication_event = self._matching_medication_event(
            organization_id, medication, knowledge_cutoff=knowledge_cutoff
        )
        if medication_event is None:
            return None

        contribution = WithdrawalContribution.create(
            application_id=application.application_id,
            medication_batch_id=batch.batch_id,
            applied_at=application.applied_at,
            withdrawal_period_days=medication.withdrawal_period_days,
        )
        return TemporalWithdrawalContribution(
            contribution=contribution,
            application_event_id=treatment.event_id,
            application_payload_digest=treatment.payload_digest,
            batch_id=batch.batch_id,
            batch_event_id=batch_event.event_id,
            batch_payload_digest=batch_event.payload_digest,
            medication_id=medication.medication_id,
            medication_event_id=medication_event.event_id,
            medication_payload_digest=medication_event.payload_digest,
            recorded_at=max(
                treatment.recorded_at,
                batch.created_at,
                batch_event.recorded_at,
                medication.created_at,
                medication_event.recorded_at,
            ),
        )

    def _matching_batch_event(
        self,
        organization_id: OrganizationId,
        batch: MedicationBatch,
        *,
        knowledge_cutoff: datetime,
    ) -> RecordedCanonicalEvent | None:
        expected = medication_batch_registered_payload(
            batch_id=batch.batch_id,
            medication_id=batch.medication_id,
            batch_number=batch.batch_number,
            expiry_date=batch.expiry_date,
            manufacturing_date=batch.manufacturing_date,
        )
        return _matching_event(
            self.event_reader,
            organization_id,
            aggregate_id=batch.batch_id,
            event_type=MEDICATION_BATCH_REGISTERED,
            occurred_at=batch.created_at,
            knowledge_cutoff=knowledge_cutoff,
            payload_schema=expected.schema,
            payload_version=expected.version,
            payload_bytes=expected.canonical_bytes,
        )

    def _matching_medication_event(
        self,
        organization_id: OrganizationId,
        medication: Medication,
        *,
        knowledge_cutoff: datetime,
    ) -> RecordedCanonicalEvent | None:
        expected = medication_registered_payload(
            medication_id=medication.medication_id,
            trade_name=medication.trade_name,
            active_ingredient=medication.active_ingredient,
            manufacturer=medication.manufacturer,
            withdrawal_period_days=medication.withdrawal_period_days,
            product_class=medication.product_class.value,
        )
        return _matching_event(
            self.event_reader,
            organization_id,
            aggregate_id=medication.medication_id,
            event_type=MEDICATION_REGISTERED,
            occurred_at=medication.created_at,
            knowledge_cutoff=knowledge_cutoff,
            payload_schema=expected.schema,
            payload_version=expected.version,
            payload_bytes=expected.canonical_bytes,
        )


def build_temporal_withdrawal_status(
    animal_id: TypedId, selection: TemporalWithdrawalSelection
) -> AnimalWithdrawalStatus:
    """Monta o status sem consultar o estado atual de nenhum repositório."""
    if selection.limitation is not None:
        raise ValueError("Seleção temporal limitada não pode produzir status de carência.")
    return build_animal_withdrawal_status(
        animal_id, tuple(item.contribution for item in selection.contributions)
    )


def _matching_event(
    event_reader: CanonicalDomainEventReader,
    organization_id: OrganizationId,
    *,
    aggregate_id: TypedId,
    event_type: str,
    occurred_at: datetime,
    knowledge_cutoff: datetime,
    payload_schema: str,
    payload_version: int,
    payload_bytes: bytes,
) -> RecordedCanonicalEvent | None:
    reference = UniversalReference(
        target_id=aggregate_id,
        organization_id=organization_id,
        contract_version=AGGREGATE_CONTRACT_VERSION,
    )
    matches = [
        event
        for event in event_reader.list_canonical_for_aggregate(reference)
        if event.event_type == event_type
        and event.occurred_at == occurred_at
        and event.recorded_at <= knowledge_cutoff
        and event.payload_schema == payload_schema
        and event.payload_version == payload_version
        and event.payload_canonical_bytes == payload_bytes
    ]
    return matches[0] if len(matches) == 1 else None
