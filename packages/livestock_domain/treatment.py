"""Entidade de domínio TreatmentApplication (Passo 9.3 - Titan Livestock).

A aplicação de tratamento é um registro imutável e append-only: nunca é editada.
Uma correção não altera o registro original — cria um novo que o referencia por
`corrects_application_id`. Isso preserva a auditoria (o que foi aplicado e quando)
e sustenta o recall por lote (quais animais receberam determinado lote).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


@dataclass(frozen=True, slots=True)
class TreatmentApplication:
    application_id: TypedId
    organization_id: OrganizationId
    animal_id: TypedId
    medication_batch_id: TypedId
    actor_id: TypedId
    applied_at: datetime
    dose: str | None = None
    evidence_references: tuple[str, ...] = ()
    prescription_id: TypedId | None = None
    corrects_application_id: TypedId | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.applied_at, field_name="applied_at")
        require_utc(self.created_at, field_name="created_at")
        if self.application_id.entity_type != "treatment_application":
            raise ValueError(
                "application_id deve ter entity_type 'treatment_application', recebido "
                f"'{self.application_id.entity_type}'."
            )
        if self.animal_id.entity_type != "animal":
            raise ValueError(
                f"animal_id deve ter entity_type 'animal', recebido '{self.animal_id.entity_type}'."
            )
        if self.medication_batch_id.entity_type != "medication_batch":
            raise ValueError(
                "medication_batch_id deve ter entity_type 'medication_batch', recebido "
                f"'{self.medication_batch_id.entity_type}'."
            )
        if self.actor_id.entity_type != "actor":
            raise ValueError(
                f"actor_id deve ter entity_type 'actor', recebido '{self.actor_id.entity_type}'."
            )
        if self.dose is not None and not self.dose.strip():
            raise ValueError("dose, quando informada, não pode ser vazia.")
        if self.prescription_id is not None and self.prescription_id.entity_type != "prescription":
            raise ValueError(
                "prescription_id deve ter entity_type 'prescription', recebido "
                f"'{self.prescription_id.entity_type}'."
            )
        if self.corrects_application_id is not None:
            if self.corrects_application_id.entity_type != "treatment_application":
                raise ValueError(
                    "corrects_application_id deve ter entity_type 'treatment_application', "
                    f"recebido '{self.corrects_application_id.entity_type}'."
                )
            if self.corrects_application_id == self.application_id:
                raise ValueError("Uma aplicação não pode corrigir a si mesma.")
