"""Entidade de domínio TreatmentApplication (Passo 9.3 - Titan Livestock).

A aplicação de tratamento é um registro imutável e append-only: nunca é editada.
Uma correção não altera o registro original — cria um novo que o referencia por
`corrects_application_id`. Isso preserva a auditoria (o que foi aplicado e quando)
e sustenta o recall por lote (quais animais receberam determinado lote).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc


@dataclass(frozen=True, slots=True)
class TreatmentApplication:
    """Aplicação de tratamento, imutável e append-only.

    `evidence_references` aponta para `Evidence` do Core — registro com hash de
    conteúdo, fonte e proveniência — na mesma convenção que `Decision` e
    `NonConformity` já usam. Texto livre não sustenta prova: um dossiê que citasse
    "evidence:foto-1" não permitiria a ninguém conferir coisa alguma.

    `evidence_notes` guarda a anotação operacional ("foto no celular do João"),
    que é informação útil e **não** é evidência. Separar os dois impede que
    anotação seja apresentada como prova.
    """

    application_id: TypedId
    organization_id: OrganizationId
    animal_id: TypedId
    medication_batch_id: TypedId
    actor_id: TypedId
    applied_at: datetime
    dose: str | None = None
    evidence_references: tuple[UniversalReference, ...] = ()
    evidence_notes: tuple[str, ...] = ()
    prescription_id: TypedId | None = None
    sanitary_campaign_id: TypedId | None = None
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
        if (
            self.sanitary_campaign_id is not None
            and self.sanitary_campaign_id.entity_type != "sanitary_campaign"
        ):
            raise ValueError(
                "sanitary_campaign_id deve ter entity_type 'sanitary_campaign', recebido "
                f"'{self.sanitary_campaign_id.entity_type}'."
            )
        if self.corrects_application_id is not None:
            if self.corrects_application_id.entity_type != "treatment_application":
                raise ValueError(
                    "corrects_application_id deve ter entity_type 'treatment_application', "
                    f"recebido '{self.corrects_application_id.entity_type}'."
                )
            if self.corrects_application_id == self.application_id:
                raise ValueError("Uma aplicação não pode corrigir a si mesma.")
        for reference in self.evidence_references:
            if not isinstance(reference, UniversalReference):
                raise TypeError(
                    "evidence_references deve conter UniversalReference. Texto livre "
                    "pertence a evidence_notes, que não é prova."
                )
            if reference.target_id.entity_type != "evidence":
                raise ValueError(
                    "evidence_references deve apontar para 'evidence', recebido "
                    f"'{reference.target_id.entity_type}'."
                )
            if reference.organization_id != self.organization_id:
                raise ValueError("A evidência citada pertence a outra Organization.")
        for note in self.evidence_notes:
            if not isinstance(note, str) or not note.strip():
                raise ValueError("evidence_notes não aceita anotação vazia.")
