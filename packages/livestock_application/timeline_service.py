"""Linha do tempo da vertical Titan Livestock (Passo 10.1b).

Consulta cronológica reconstruída a partir dos registros imutáveis — o log de
eventos do Core e os registros append-only de avaliação e decisão. **Nada aqui lê
estado atual como substituto do histórico:** os repositórios da vertical são
usados apenas para descobrir QUAIS fluxos pertencem ao sujeito, nunca para dizer
o que aconteceu. Quem diz o que aconteceu é o evento.

A fronteira merece nome, porque é a que o PLANO cobra. Duas fontes entram aqui:

1. `core_audit.domain_events`, via `DomainEventReader`;
2. `Evaluation` e `Decision` do Core, que não são eventos de domínio mas são
   registros imutáveis — sem eles o bloqueio por carência e a reavaliação, que
   são o coração do Marco 9, não apareceriam na linha do tempo.

O que **não** é fonte: agregado atual, projeção, ou qualquer campo que reflita
"como está agora". Se um dado só existe no estado corrente, ele não entra.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from packages.core_application.event_log import DomainEventReader, RecordedEvent
from packages.core_application.relation_service import RelationRepositoryPort
from packages.core_domain.decision import Decision
from packages.core_domain.evaluation import Evaluation
from packages.livestock_application.event_recorder import AGGREGATE_CONTRACT_VERSION
from packages.livestock_application.lot_service import LotMembershipRepositoryPort
from packages.livestock_application.medication_service import MedicationBatchRepositoryPort
from packages.livestock_application.movement_service import MovementRepositoryPort
from packages.livestock_application.treatment_service import (
    TreatmentApplicationRepositoryPort,
)
from packages.livestock_domain.parentage import ROLE_BY_RELATION_TYPE
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc

EVALUATION_ENTRY_TYPE = "core.evaluation"
DECISION_ENTRY_TYPE = "core.decision"


class TimelineSourceKind(StrEnum):
    """De qual registro imutável a entrada veio."""

    DOMAIN_EVENT = "DOMAIN_EVENT"
    EVALUATION = "EVALUATION"
    DECISION = "DECISION"


# Desempate por precedência causal, e não pelo nome. A decisão é derivada da
# avaliação e emitida no mesmo instante que ela; ordenar alfabeticamente colocava
# a decisão ANTES da avaliação que a produziu — causalidade invertida num
# documento que se apresenta como prova.
_PRECEDENCIA_CAUSAL = {
    TimelineSourceKind.DOMAIN_EVENT: 0,
    TimelineSourceKind.EVALUATION: 1,
    TimelineSourceKind.DECISION: 2,
}


@dataclass(frozen=True, slots=True)
class TimelineCutoff:
    """Corte bitemporal da consulta.

    Os dois eixos existem porque o Titan separa quando o fato ocorreu de quando
    foi registrado, e as duas perguntas são diferentes:

    - `occurred_until` responde "o que aconteceu até tal data";
    - `known_until` responde "o que o Titan sabia em tal data", que é a pergunta
      de auditoria — um tratamento lançado com atraso não pode aparecer numa
      reconstrução do que se sabia antes de ele ser lançado.

    Sem nenhum dos dois, a leitura vai até o presente.
    """

    occurred_until: datetime | None = None
    known_until: datetime | None = None

    def __post_init__(self) -> None:
        if self.occurred_until is not None:
            require_utc(self.occurred_until, field_name="occurred_until")
        if self.known_until is not None:
            require_utc(self.known_until, field_name="known_until")

    def admits(self, occurred_at: datetime, recorded_at: datetime) -> bool:
        if self.occurred_until is not None and occurred_at > self.occurred_until:
            return False
        return not (self.known_until is not None and recorded_at > self.known_until)


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """Uma linha da história, já desligada do registro que a originou."""

    occurred_at: datetime
    recorded_at: datetime
    entry_type: str
    source_kind: TimelineSourceKind
    source_id: TypedId
    aggregate_id: TypedId
    sequence: int
    actor_reference: UniversalReference | None
    correlation_id: TypedId | None
    payload_schema: str | None
    superseded_by: TypedId | None

    def sort_key(self) -> tuple[datetime, str, str, int, int, str]:
        """Ordem total e estável, que não depende da ordem de leitura do banco.

        `occurred_at` é a cronologia que interessa a quem lê. O resto existe para
        desempatar sempre — inclusive `source_id` ao final, que é único e garante
        que duas leituras da mesma história produzam exatamente a mesma sequência,
        e não apenas uma parecida. É o mesmo princípio de chave total do Passo 7.2.

        Entre origens, o desempate segue a **precedência causal**: fato, depois
        avaliação, depois decisão. Ver `_PRECEDENCIA_CAUSAL`.
        """
        return (
            self.occurred_at,
            self.aggregate_id.entity_type,
            str(self.aggregate_id.value),
            _PRECEDENCIA_CAUSAL[self.source_kind],
            self.sequence,
            str(self.source_id.value),
        )


class EvaluationReaderPort(Protocol):
    """Contrato mínimo de leitura de avaliações do Core."""

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[Evaluation]: ...


class DecisionReaderPort(Protocol):
    """Contrato mínimo de leitura de decisões do Core."""

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[Decision]: ...


@dataclass(frozen=True, slots=True)
class LivestockTimelineService:
    """Monta a linha do tempo de um animal, de um lote ou de um tratamento."""

    event_reader: DomainEventReader
    movement_repository: MovementRepositoryPort
    application_repository: TreatmentApplicationRepositoryPort
    membership_repository: LotMembershipRepositoryPort
    batch_repository: MedicationBatchRepositoryPort
    evaluation_repository: EvaluationReaderPort
    decision_repository: DecisionReaderPort
    relation_repository: RelationRepositoryPort

    def animal_timeline(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        cutoff: TimelineCutoff | None = None,
    ) -> tuple[TimelineEntry, ...]:
        """História do animal: cadastro, marcações, movimentações, lotes, tratamentos.

        Os repositórios respondem apenas "quais movimentações, lotes e aplicações
        citam este animal". O conteúdo de cada uma vem do fluxo de eventos dela.
        """
        applications = self.application_repository.list_by_animal(organization_id, animal_id)
        superseded = _superseded_map(applications)

        aggregates: list[TypedId] = [animal_id]
        aggregates.extend(
            movement.movement_id for movement in self.movement_repository.list_by_animal(animal_id)
        )
        aggregates.extend(
            membership.lot_id
            for membership in self.membership_repository.list_memberships_for_animal(animal_id)
        )
        aggregates.extend(application.application_id for application in applications)
        aggregates.extend(self._parentage_relations(organization_id, animal_id))

        return self._assemble(organization_id, animal_id, aggregates, superseded, cutoff)

    def lot_timeline(
        self,
        organization_id: OrganizationId,
        lot_id: TypedId,
        cutoff: TimelineCutoff | None = None,
    ) -> tuple[TimelineEntry, ...]:
        """História do lote: criação e cada entrada e saída de animal."""
        return self._assemble(organization_id, lot_id, [lot_id], {}, cutoff)

    def treatment_timeline(
        self,
        organization_id: OrganizationId,
        application_id: TypedId,
        cutoff: TimelineCutoff | None = None,
    ) -> tuple[TimelineEntry, ...]:
        """História de uma aplicação: o registro, sua origem e suas correções.

        Inclui a prescrição que a autorizou e o lote de medicamento usado, porque
        é o que permite ler a aplicação sem consultar o estado atual de nenhum dos
        dois — e é do lote que sai o prazo de carência.
        """
        application = self.application_repository.get_by_id(application_id)
        if application is None or application.organization_id != organization_id:
            raise KeyError(f"Aplicação '{application_id.value}' não encontrada.")

        siblings = self.application_repository.list_by_animal(
            organization_id, application.animal_id
        )
        chain = _correction_chain(application_id, siblings)

        aggregates: list[TypedId] = [application.medication_batch_id]
        batch = self.batch_repository.get_by_id(application.medication_batch_id)
        if batch is not None and batch.organization_id == organization_id:
            aggregates.append(batch.medication_id)
        if application.prescription_id is not None:
            aggregates.append(application.prescription_id)
        aggregates.extend(chain)

        return self._assemble(
            organization_id, application_id, aggregates, _superseded_map(siblings), cutoff
        )

    def _assemble(
        self,
        organization_id: OrganizationId,
        subject_id: TypedId,
        aggregates: Iterable[TypedId],
        superseded: dict[TypedId, TypedId],
        cutoff: TimelineCutoff | None,
    ) -> tuple[TimelineEntry, ...]:
        entries: list[TimelineEntry] = []
        for aggregate_id in _unique(aggregates):
            for event in self._events_of(organization_id, aggregate_id):
                entries.append(_entry_from_event(event, superseded.get(aggregate_id)))

        for evaluation in self.evaluation_repository.list_by_subject(organization_id, subject_id):
            entries.append(_entry_from_evaluation(evaluation))
        for decision in self.decision_repository.list_by_subject(organization_id, subject_id):
            entries.append(_entry_from_decision(decision))

        admitted = (
            entries
            if cutoff is None
            else [entry for entry in entries if cutoff.admits(entry.occurred_at, entry.recorded_at)]
        )
        return tuple(sorted(admitted, key=lambda entry: entry.sort_key()))

    def _parentage_relations(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[TypedId]:
        """Os vínculos de parentesco em que este animal é uma das pontas.

        É por aqui que o parto entra na vida da matriz: a relação é o agregado do
        evento, e tanto a cria quanto a mãe a citam. Sem isto, o nascimento
        apareceria só na história do bezerro, e a vaca que o pariu não teria
        registro do parto — que é um dos fatos mais importantes da vida dela.

        As relações de saída trazem as crias; as de entrada, os progenitores. A
        tabela é do Core e guarda vínculos de toda natureza, então só o que for
        parentesco entra.
        """
        encontradas = [
            *self.relation_repository.list_outgoing(
                organization_id=organization_id, source_id=animal_id
            ),
            *self.relation_repository.list_incoming(
                organization_id=organization_id, target_id=animal_id
            ),
        ]
        return [
            relacao.relation_id
            for relacao in encontradas
            if relacao.relation_type in ROLE_BY_RELATION_TYPE
        ]

    def _events_of(
        self, organization_id: OrganizationId, aggregate_id: TypedId
    ) -> Sequence[RecordedEvent]:
        reference = UniversalReference(
            target_id=aggregate_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        return self.event_reader.list_for_aggregate(reference)


def _unique(values: Iterable[TypedId]) -> list[TypedId]:
    """Preserva a ordem de descoberta e não repete fluxo já colhido."""
    seen: set[tuple[str, str]] = set()
    result: list[TypedId] = []
    for value in values:
        key = (value.entity_type, str(value.value))
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _superseded_map(applications: Sequence[object]) -> dict[TypedId, TypedId]:
    """Aplicação corrigida → aplicação que a corrigiu.

    O vínculo vem do campo do registro, e não do payload do evento: o payload
    diria a mesma coisa, mas exigiria desserializar bytes canônicos para saber
    algo que a aplicação já declara em campo tipado.
    """
    mapping: dict[TypedId, TypedId] = {}
    for application in applications:
        corrects = getattr(application, "corrects_application_id", None)
        if corrects is not None:
            mapping[corrects] = application.application_id  # type: ignore[attr-defined]
    return mapping


def _correction_chain(application_id: TypedId, siblings: Sequence[object]) -> list[TypedId]:
    """A aplicação, o que ela corrigiu e o que a corrigiu, em cadeia."""
    by_id = {app.application_id: app for app in siblings}  # type: ignore[attr-defined]
    chain = [application_id]

    current = by_id.get(application_id)
    while current is not None:
        previous = getattr(current, "corrects_application_id", None)
        if previous is None or previous in chain:
            break
        chain.append(previous)
        current = by_id.get(previous)

    forward = _superseded_map(siblings)
    cursor = application_id
    while cursor in forward:
        cursor = forward[cursor]
        if cursor in chain:
            break
        chain.append(cursor)
    return chain


def _entry_from_event(event: RecordedEvent, superseded_by: TypedId | None) -> TimelineEntry:
    return TimelineEntry(
        occurred_at=event.occurred_at,
        recorded_at=event.recorded_at,
        entry_type=event.event_type,
        source_kind=TimelineSourceKind.DOMAIN_EVENT,
        source_id=event.event_id,
        aggregate_id=event.aggregate_reference.target_id,
        sequence=event.aggregate_version,
        actor_reference=event.actor_reference,
        correlation_id=event.correlation_id,
        payload_schema=event.payload_schema,
        superseded_by=superseded_by,
    )


def _entry_from_evaluation(evaluation: Evaluation) -> TimelineEntry:
    return TimelineEntry(
        occurred_at=evaluation.evaluated_at,
        recorded_at=evaluation.evaluated_at,
        entry_type=EVALUATION_ENTRY_TYPE,
        source_kind=TimelineSourceKind.EVALUATION,
        source_id=evaluation.evaluation_id,
        aggregate_id=evaluation.subject_id,
        sequence=0,
        actor_reference=evaluation.executor_reference,
        correlation_id=None,
        payload_schema=None,
        superseded_by=None,
    )


def _entry_from_decision(decision: Decision) -> TimelineEntry:
    return TimelineEntry(
        occurred_at=decision.issued_at,
        recorded_at=decision.issued_at,
        entry_type=DECISION_ENTRY_TYPE,
        source_kind=TimelineSourceKind.DECISION,
        source_id=decision.decision_id,
        aggregate_id=decision.subject_id,
        sequence=0,
        actor_reference=None,
        correlation_id=None,
        payload_schema=None,
        superseded_by=None,
    )
