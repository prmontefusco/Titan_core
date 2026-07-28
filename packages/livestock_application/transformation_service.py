"""Transformação industrial — abate com fan-out real (ADR-0046, Passo 11.2).

Primeiro incremento do Marco 11: um animal, já com saída ABATE registrada,
produz duas ou mais saídas rastreáveis (`TraceableItem`) através de um único
`TransformationEvent(SLAUGHTER)`. `DEBONING` e fan-in ficam para incrementos
seguintes (11.6, 11.7) — este serviço só constrói o caso já provado.

A guarda que impede reaproveitar o mesmo animal como entrada de uma segunda
transformação lê a projeção `UniversalRelation` já gravada por uma chamada
anterior (`transformation.input_of`), em vez de um repositório dedicado — é a
mesma trilha que o Passo 7.1 já sustenta, sem tabela nova.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from packages.core_application.relation_service import RelationService
from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier
from packages.core_domain.relations import UniversalRelation
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    AGGREGATE_CONTRACT_VERSION,
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.exit_service import AnimalExitRepositoryPort
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.events import (
    TRANSFORMATION_EVENT_RECORDED,
    transformation_event_recorded_payload,
)
from packages.livestock_domain.exit import ExitType
from packages.livestock_domain.transformation import (
    ConsumptionMode,
    ParticipantRole,
    ProcessType,
    TraceableItem,
    TraceableItemType,
    TransformationEvent,
    TransformationParticipant,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc

TRANSFORMATION_INPUT_OF = "transformation.input_of"
TRANSFORMATION_OUTPUT_OF = "transformation.output_of"

# Abate sem fan-out real não prova a decisão do Passo 11.2 (item 1 da ADR: o
# contrato aceita N=1, mas o cenário validado exige fan-out de verdade).
FAN_OUT_MINIMO = 2


class TraceableItemRepositoryPort(Protocol):
    def save(self, item: TraceableItem) -> None: ...

    def get_by_id(self, item_id: TypedId) -> TraceableItem | None: ...


class TransformationEventRepositoryPort(Protocol):
    def save(self, event: TransformationEvent) -> None: ...

    def get_by_id(self, event_id: TypedId) -> TransformationEvent | None: ...


class AnimalNaoAbatido(ValueError):
    """`TransformationEvent(SLAUGHTER)` exige `AnimalExit(ABATE)` já registrada."""


class AnimalJaTransformado(ValueError):
    """O animal já foi consumido como entrada de uma transformação anterior."""


@dataclass(frozen=True, slots=True)
class SlaughterOutputSpec:
    """Uma saída declarada pelo operador, antes de virar `TraceableItem`."""

    item_type: TraceableItemType
    quantity: Decimal | None = None
    unit: str = ""
    measurement_basis: str | None = None
    label: str | None = None


@dataclass(frozen=True, slots=True)
class SlaughterResult:
    event: TransformationEvent
    created_items: tuple[TraceableItem, ...]


@dataclass(frozen=True, slots=True)
class SlaughterService:
    event_repository: TransformationEventRepositoryPort
    item_repository: TraceableItemRepositoryPort
    animal_repository: AnimalRepositoryPort
    exit_repository: AnimalExitRepositoryPort
    property_repository: RuralPropertyRepositoryPort
    relation_service: RelationService
    recorder: LivestockEventRecorder

    def register_slaughter(
        self,
        context: LivestockOperationContext,
        animal_id: TypedId,
        facility_property_id: TypedId,
        occurred_at: datetime,
        outputs: Sequence[SlaughterOutputSpec],
        evidence_references: tuple[UniversalReference, ...] = (),
    ) -> SlaughterResult:
        organization_id = context.organization_id
        self._guard_occurred_at(occurred_at)
        if len(outputs) < FAN_OUT_MINIMO:
            raise ValueError(
                f"SLAUGHTER exige ao menos {FAN_OUT_MINIMO} saídas rastreáveis "
                "(fan-out real, ADR-0046 item 1)."
            )

        animal = self.animal_repository.get_by_id(animal_id)
        if animal is None or animal.organization_id != organization_id:
            raise KeyError(f"Animal '{animal_id.value}' não encontrado.")

        facility = self.property_repository.get_by_id(facility_property_id)
        if facility is None or facility.organization_id != organization_id:
            raise KeyError(f"Propriedade '{facility_property_id.value}' não encontrada.")

        exit_record = self.exit_repository.get_by_animal(animal_id)
        if (
            exit_record is None
            or exit_record.organization_id != organization_id
            or exit_record.exit_type is not ExitType.ABATE
        ):
            raise AnimalNaoAbatido(
                "TransformationEvent(SLAUGHTER) exige que o animal já tenha saída "
                "registrada como ABATE (ADR-0046, item 8): AnimalExit sozinho não é "
                "evidência de abate, mas é pré-condição dele."
            )
        if occurred_at < exit_record.occurred_at:
            raise ValueError(
                "occurred_at da transformação não pode ser anterior à saída por abate."
            )

        animal_reference = UniversalReference(
            target_id=animal_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        self._guard_nao_reutilizado(organization_id, animal_reference)

        event_id = TypedId.new("transformation_event")
        momento_criacao = datetime.now(UTC)
        created_items = tuple(
            TraceableItem(
                item_id=TypedId.new("traceable_item"),
                organization_id=organization_id,
                item_type=spec.item_type,
                created_by_transformation_id=event_id,
                created_at=momento_criacao,
                label=spec.label,
            )
            for spec in outputs
        )
        output_participants = tuple(
            TransformationParticipant(
                subject_reference=UniversalReference(
                    target_id=item.item_id,
                    organization_id=organization_id,
                    contract_version=AGGREGATE_CONTRACT_VERSION,
                ),
                role=ParticipantRole.OUTPUT,
                quantity=spec.quantity,
                unit=spec.unit,
                measurement_basis=spec.measurement_basis,
            )
            for item, spec in zip(created_items, outputs, strict=True)
        )
        input_participant = TransformationParticipant(
            subject_reference=animal_reference,
            role=ParticipantRole.INPUT,
            consumption_mode=ConsumptionMode.FULL,
        )
        facility_reference = UniversalReference(
            target_id=facility_property_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )

        event = TransformationEvent(
            event_id=event_id,
            organization_id=organization_id,
            process_type=ProcessType.SLAUGHTER,
            occurred_at=occurred_at,
            facility_reference=facility_reference,
            inputs=(input_participant,),
            outputs=output_participants,
            created_at=momento_criacao,
            evidence_references=evidence_references,
        )

        self.event_repository.save(event)
        for item in created_items:
            self.item_repository.save(item)

        domain_event = self.recorder.record(
            context=context,
            aggregate_id=event_id,
            event_type=TRANSFORMATION_EVENT_RECORDED,
            payload=transformation_event_recorded_payload(
                event_id=event_id,
                process_type=ProcessType.SLAUGHTER.value,
                occurred_at=occurred_at,
                facility_id=facility_property_id,
                input_subject_ids=(animal_id,),
                output_items=tuple((item.item_id, item.item_type.value) for item in created_items),
                evidence_references=evidence_references,
            ),
            occurred_at=occurred_at,
        )

        self._project_relations(
            organization_id=organization_id,
            event_id=event_id,
            animal_reference=animal_reference,
            created_items=created_items,
            occurred_at=occurred_at,
            created_by_event=domain_event.event_id,
        )

        return SlaughterResult(event=event, created_items=created_items)

    def _project_relations(
        self,
        *,
        organization_id: OrganizationId,
        event_id: TypedId,
        animal_reference: UniversalReference,
        created_items: tuple[TraceableItem, ...],
        occurred_at: datetime,
        created_by_event: TypedId,
    ) -> None:
        """Projeta `UniversalRelation` a partir do evento já gravado (ADR-0046, item 5).

        A relação nunca é fonte concorrente: reconstituir a transformação sempre
        lê o `TransformationEvent`, nunca estas linhas. Elas existem só para que
        `RelationService`/`RecallService` — já existentes, sem alteração — saibam
        percorrer o grafo até aqui.
        """
        transformation_reference = UniversalReference(
            target_id=event_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        confidence = ConfidenceLevel(
            tier=ConfidenceTier.DOCUMENTED,
            reason="Declarado pelo evento de transformação industrial (SLAUGHTER).",
        )
        self.relation_service.register_relation(
            UniversalRelation.create(
                organization_id=organization_id,
                source_reference=animal_reference,
                target_reference=transformation_reference,
                relation_type=TRANSFORMATION_INPUT_OF,
                created_at=datetime.now(UTC),
                confidence=confidence,
                valid_from=occurred_at,
                created_by_event=created_by_event,
            )
        )
        for item in created_items:
            item_reference = UniversalReference(
                target_id=item.item_id,
                organization_id=organization_id,
                contract_version=AGGREGATE_CONTRACT_VERSION,
            )
            self.relation_service.register_relation(
                UniversalRelation.create(
                    organization_id=organization_id,
                    source_reference=item_reference,
                    target_reference=transformation_reference,
                    relation_type=TRANSFORMATION_OUTPUT_OF,
                    created_at=datetime.now(UTC),
                    confidence=confidence,
                    valid_from=occurred_at,
                    created_by_event=created_by_event,
                )
            )

    def _guard_nao_reutilizado(
        self, organization_id: OrganizationId, animal_reference: UniversalReference
    ) -> None:
        existentes = self.relation_service.list_outgoing_at(
            organization_id=organization_id, source_reference=animal_reference
        )
        if any(relacao.relation_type == TRANSFORMATION_INPUT_OF for relacao in existentes):
            raise AnimalJaTransformado(
                "Este animal já foi utilizado como entrada em uma transformação anterior."
            )

    @staticmethod
    def _guard_occurred_at(occurred_at: datetime) -> None:
        require_utc(occurred_at, field_name="occurred_at")
        if occurred_at > datetime.now(UTC):
            raise ValueError("occurred_at não pode ser no futuro.")
