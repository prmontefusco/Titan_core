"""Serviço de aplicação TreatmentApplicationService (Passo 9.3 - Titan Livestock).

Registra aplicações de tratamento e as corrige de forma append-only. Não existe
método de edição: corrigir cria um novo registro que referencia o original, que
permanece imutável. É o cenário de validação manual do plano — "tentar edição e
confirmar correção por novo evento".
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.medication_service import (
    MedicationBatchRepositoryPort,
    PrescriptionRepositoryPort,
)
from packages.livestock_domain.events import TREATMENT_APPLIED, treatment_applied_payload
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class TreatmentApplicationRepositoryPort(Protocol):
    def save(self, application: TreatmentApplication) -> None: ...

    def get_by_id(self, application_id: TypedId) -> TreatmentApplication | None: ...

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[TreatmentApplication]: ...

    def list_by_batch(
        self, organization_id: OrganizationId, medication_batch_id: TypedId
    ) -> list[TreatmentApplication]: ...


@dataclass(frozen=True, slots=True)
class TreatmentApplicationService:
    application_repository: TreatmentApplicationRepositoryPort
    animal_repository: AnimalRepositoryPort
    batch_repository: MedicationBatchRepositoryPort
    prescription_repository: PrescriptionRepositoryPort
    recorder: LivestockEventRecorder

    def register_application(
        self,
        context: LivestockOperationContext,
        animal_id: TypedId,
        medication_batch_id: TypedId,
        applied_at: datetime,
        dose: str | None = None,
        evidence_references: tuple[str, ...] = (),
        prescription_id: TypedId | None = None,
    ) -> TreatmentApplication:
        organization_id = context.organization_id
        self._validate_references(organization_id, animal_id, medication_batch_id, prescription_id)
        self._guard_applied_at(applied_at)

        # A autoria vem do contexto, e não de um parâmetro à parte: assim o autor
        # do registro e o do evento não podem divergir.
        application = TreatmentApplication(
            application_id=TypedId.new("treatment_application"),
            organization_id=organization_id,
            animal_id=animal_id,
            medication_batch_id=medication_batch_id,
            actor_id=context.actor_reference.target_id,
            applied_at=applied_at,
            dose=dose,
            evidence_references=evidence_references,
            prescription_id=prescription_id,
            corrects_application_id=None,
            created_at=datetime.now(UTC),
        )
        self.application_repository.save(application)
        self._record(context, application)
        return application

    def correct_application(
        self,
        context: LivestockOperationContext,
        original_application_id: TypedId,
        applied_at: datetime,
        dose: str | None = None,
        evidence_references: tuple[str, ...] = (),
        prescription_id: TypedId | None = None,
    ) -> TreatmentApplication:
        """Corrige uma aplicação criando um NOVO registro que a supersede.

        O registro original não é tocado — a correção é um novo evento auditável
        que aponta para ele. Corrigir o animal ou o lote de uma aplicação seria
        registrar outra aplicação, não uma correção; por isso a correção reusa o
        animal e o lote do original.
        """
        organization_id = context.organization_id
        original = self.application_repository.get_by_id(original_application_id)
        if original is None or original.organization_id != organization_id:
            raise KeyError(
                f"Aplicação '{original_application_id.value}' não encontrada ou pertencente "
                "a outra organização."
            )
        self._validate_references(
            organization_id, original.animal_id, original.medication_batch_id, prescription_id
        )
        self._guard_applied_at(applied_at)

        correction = TreatmentApplication(
            application_id=TypedId.new("treatment_application"),
            organization_id=organization_id,
            animal_id=original.animal_id,
            medication_batch_id=original.medication_batch_id,
            actor_id=context.actor_reference.target_id,
            applied_at=applied_at,
            dose=dose,
            evidence_references=evidence_references,
            prescription_id=prescription_id,
            corrects_application_id=original.application_id,
            created_at=datetime.now(UTC),
        )
        self.application_repository.save(correction)
        self._record(context, correction)
        return correction

    def _record(
        self, context: LivestockOperationContext, application: TreatmentApplication
    ) -> None:
        """A correção é registro novo, com fluxo próprio.

        O vínculo com o corrigido viaja em `corrects_application_id`, no payload, e
        não em `causation_id`: a porta do log expõe apenas escrita e versões, então
        o serviço não tem como descobrir o `event_id` do evento original para
        apontar para ele. Quem lê a linha do tempo segue o vínculo pelo payload.
        """
        self.recorder.record(
            context=context,
            aggregate_id=application.application_id,
            event_type=TREATMENT_APPLIED,
            payload=treatment_applied_payload(
                application_id=application.application_id,
                animal_id=application.animal_id,
                medication_batch_id=application.medication_batch_id,
                applied_at=application.applied_at,
                dose=application.dose,
                prescription_id=application.prescription_id,
                evidence_references=application.evidence_references,
                corrects_application_id=application.corrects_application_id,
            ),
            occurred_at=application.applied_at,
        )

    def _validate_references(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        medication_batch_id: TypedId,
        prescription_id: TypedId | None,
    ) -> None:
        animal = self.animal_repository.get_by_id(animal_id)
        if animal is None or animal.organization_id != organization_id:
            raise KeyError(
                f"Animal '{animal_id.value}' não encontrado ou pertencente a outra organização."
            )
        batch = self.batch_repository.get_by_id(medication_batch_id)
        if batch is None or batch.organization_id != organization_id:
            raise KeyError(
                f"Lote '{medication_batch_id.value}' não encontrado ou pertencente a "
                "outra organização."
            )
        if prescription_id is not None:
            prescription = self.prescription_repository.get_by_id(prescription_id)
            if prescription is None or prescription.organization_id != organization_id:
                raise KeyError(
                    f"Prescrição '{prescription_id.value}' não encontrada ou pertencente a "
                    "outra organização."
                )

    @staticmethod
    def _guard_applied_at(applied_at: datetime) -> None:
        require_utc(applied_at, field_name="applied_at")
        if applied_at > datetime.now(UTC):
            raise ValueError("applied_at não pode ser no futuro.")
