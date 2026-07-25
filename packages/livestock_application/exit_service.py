"""Registro da saída de um animal do rebanho (Passo 13.1 - Titan Livestock).

A guarda que impede fato posterior à saída vive em `guard_animal_active`, e é
consultada pelos serviços que registram fatos datados sobre um animal. Ela lê a
saída pela **porta de animal**, que todos eles já recebem: uma porta nova exigiria
alterar a fiação de cada serviço, e quem esquecesse de fazê-lo teria a guarda
desligada em silêncio.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_domain.events import ANIMAL_EXITED, animal_exited_payload
from packages.livestock_domain.exit import AnimalExit, ExitType
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc


class AnimalExitRepositoryPort(Protocol):
    def save(self, exit_record: AnimalExit) -> None: ...

    def get_by_animal(self, animal_id: TypedId) -> AnimalExit | None: ...


class SaidaJaRegistrada(ValueError):
    """Sair é terminal: um animal não deixa o rebanho duas vezes."""


class AnimalForaDoRebanho(ValueError):
    """O fato é posterior à saída, e não pôde ter acontecido."""


def guard_animal_active(
    animal_repository: AnimalRepositoryPort,
    animal_id: TypedId,
    occurred_at: datetime,
) -> None:
    """Recusa fato posterior à saída; aceita o anterior, ainda que lançado hoje.

    Chamada pelos serviços de tratamento, movimentação e lote. Silenciosa quando
    o animal continua no rebanho, que é o caso comum.

    **Também recusa qualquer fato sobre quem não nasceu vivo** (ADR-0040). O
    natimorto é rastreável pela genealogia e pelo índice reprodutivo, mas nunca
    entrou no ciclo operacional: ele não é tratado, movimentado nem colocado em
    lote. A conferência vive aqui, e não numa guarda nova, porque uma guarda que
    alguém esqueça de chamar é uma guarda desligada em silêncio.
    """
    animal = animal_repository.get_by_id(animal_id)
    if animal is not None and not animal.born_alive:
        raise AnimalForaDoRebanho(
            "O animal não nasceu vivo (NATIMORTO); ele não participa do ciclo "
            "operacional do rebanho e não recebe fatos."
        )

    saida = animal_repository.get_exit(animal_id)
    if saida is None or saida.admite_fato_em(occurred_at):
        return
    raise AnimalForaDoRebanho(
        f"O animal deixou o rebanho em {saida.occurred_at.isoformat()} "
        f"({saida.exit_type.value}); um fato posterior a essa data não pôde ocorrer."
    )


@dataclass(frozen=True, slots=True)
class AnimalExitService:
    """Registra a saída, uma única vez por animal."""

    exit_repository: AnimalExitRepositoryPort
    animal_repository: AnimalRepositoryPort
    recorder: LivestockEventRecorder

    def register_exit(
        self,
        context: LivestockOperationContext,
        animal_id: TypedId,
        exit_type: ExitType,
        occurred_at: datetime,
        reason: str | None = None,
        destination: str | None = None,
        evidence_references: tuple[UniversalReference, ...] = (),
    ) -> AnimalExit:
        organization_id = context.organization_id
        animal = self.animal_repository.get_by_id(animal_id)
        if animal is None or animal.organization_id != organization_id:
            raise KeyError(f"Animal '{animal_id.value}' não encontrado.")

        self._guard_occurred_at(occurred_at)
        ja_saiu = self.exit_repository.get_by_animal(animal_id)
        if ja_saiu is not None:
            raise SaidaJaRegistrada(
                f"O animal já deixou o rebanho em {ja_saiu.occurred_at.isoformat()} "
                f"({ja_saiu.exit_type.value})."
            )

        registro = AnimalExit(
            exit_id=TypedId.new("animal_exit"),
            organization_id=organization_id,
            animal_id=animal_id,
            exit_type=exit_type,
            occurred_at=occurred_at,
            reason=reason,
            destination=destination,
            evidence_references=evidence_references,
            created_at=datetime.now(UTC),
        )
        self.exit_repository.save(registro)
        self.recorder.record(
            context=context,
            aggregate_id=animal_id,
            event_type=ANIMAL_EXITED,
            payload=animal_exited_payload(
                exit_id=registro.exit_id,
                animal_id=animal_id,
                exit_type=exit_type.value,
                occurred_at=occurred_at,
                reason=reason,
                destination=destination,
                evidence_references=evidence_references,
            ),
            occurred_at=occurred_at,
        )
        return registro

    def get_exit(self, organization_id: OrganizationId, animal_id: TypedId) -> AnimalExit | None:
        encontrado = self.exit_repository.get_by_animal(animal_id)
        if encontrado is None or encontrado.organization_id != organization_id:
            return None
        return encontrado

    @staticmethod
    def _guard_occurred_at(occurred_at: datetime) -> None:
        """O relógio é lido na Application, e a saída não acontece no futuro."""
        require_utc(occurred_at, field_name="occurred_at")
        if occurred_at > datetime.now(UTC):
            raise ValueError("occurred_at não pode ser no futuro.")
