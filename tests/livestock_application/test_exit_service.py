"""Saída do animal do rebanho (Passo 13.1 - Titan Livestock).

O que estes testes protegem é a assimetria da regra: a saída fecha o **futuro**,
não o passado. Uma guarda que recusasse tudo depois da saída — inclusive um fato
anterior lançado com atraso — impediria a regularização de registro, que é
justamente o caso mais comum no campo.
"""

from datetime import UTC, datetime, timedelta

import pytest

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.exit_service import (
    AnimalExitRepositoryPort,
    AnimalExitService,
    AnimalForaDoRebanho,
    SaidaJaRegistrada,
    guard_animal_active,
)
from packages.livestock_application.external_counterparty_service import (
    ExternalCounterpartyRepositoryPort,
)
from packages.livestock_domain.animal import Animal, AnimalSex, IdentifierType
from packages.livestock_domain.events import ANIMAL_EXITED
from packages.livestock_domain.exit import AnimalExit, ExitType
from packages.livestock_domain.external_counterparty import CounterpartyType, ExternalCounterparty
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog


class InMemoryExitRepo(AnimalExitRepositoryPort):
    def __init__(self) -> None:
        self.saidas: dict[str, AnimalExit] = {}

    def save(self, exit_record: AnimalExit) -> None:
        self.saidas[exit_record.animal_id.value.hex] = exit_record

    def get_by_animal(self, animal_id: TypedId) -> AnimalExit | None:
        return self.saidas.get(animal_id.value.hex)


class InMemoryAnimalRepo(AnimalRepositoryPort):
    """Compartilha o dicionário de saídas com o repositório de saída.

    É o que a infraestrutura faz de verdade: `get_exit` do repositório de animal
    delega ao repositório de saída, na mesma transação.
    """

    def __init__(self, saidas: InMemoryExitRepo) -> None:
        self.animals: dict[str, Animal] = {}
        self._saidas = saidas

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
        return self._saidas.get_by_animal(animal_id)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Animal]:
        return list(self.animals.values())


class InMemoryCounterpartyRepo(ExternalCounterpartyRepositoryPort):
    def __init__(self) -> None:
        self.counterparties: dict[str, ExternalCounterparty] = {}

    def save(self, counterparty: ExternalCounterparty) -> None:
        self.counterparties[counterparty.counterparty_id.value.hex] = counterparty

    def get_by_id(self, counterparty_id: TypedId) -> ExternalCounterparty | None:
        return self.counterparties.get(counterparty_id.value.hex)

    def list_by_organization(self, organization_id: OrganizationId) -> list[ExternalCounterparty]:
        return [
            item for item in self.counterparties.values() if item.organization_id == organization_id
        ]


def _cenario(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> tuple[AnimalExitService, InMemoryAnimalRepo, TypedId]:
    exit_repo = InMemoryExitRepo()
    animal_repo = InMemoryAnimalRepo(exit_repo)
    counterparty_repo = InMemoryCounterpartyRepo()
    animal = Animal(
        animal_id=TypedId.new("animal"),
        organization_id=context.organization_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.FEMALE,
    )
    animal_repo.save(animal)
    service = AnimalExitService(
        exit_repository=exit_repo,
        animal_repository=animal_repo,
        recorder=recorder,
        counterparty_repository=counterparty_repo,
    )
    return service, animal_repo, animal.animal_id


def test_registra_a_saida_e_grava_o_fato(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, _, animal_id = _cenario(recorder, context)
    momento = datetime.now(UTC) - timedelta(days=1)

    saida = service.register_exit(
        context=context,
        animal_id=animal_id,
        exit_type=ExitType.ABATE,
        occurred_at=momento,
        reason="Abate programado",
        destination="Frigorífico Central",
    )

    assert saida.exit_type is ExitType.ABATE
    evento = event_log.only(ANIMAL_EXITED)
    # O fato pertence ao fluxo do animal: é o fim da história dele.
    assert evento.aggregate_reference.target_id == animal_id
    assert evento.timestamps.occurred_at == momento


def test_saida_pode_apontar_para_contraparte_externa_local(
    recorder: LivestockEventRecorder,
    context: LivestockOperationContext,
) -> None:
    service, _, animal_id = _cenario(recorder, context)
    assert service.counterparty_repository is not None
    contraparte = ExternalCounterparty(
        counterparty_id=TypedId.new("external_counterparty"),
        organization_id=context.organization_id,
        name="Fazenda Destino",
        counterparty_type=CounterpartyType.FARM,
    )
    service.counterparty_repository.save(contraparte)

    saida = service.register_exit(
        context=context,
        animal_id=animal_id,
        exit_type=ExitType.VENDA,
        occurred_at=datetime.now(UTC) - timedelta(days=1),
        destination_counterparty_id=contraparte.counterparty_id,
    )

    assert saida.destination_counterparty_id == contraparte.counterparty_id


def test_saida_nao_alcanca_contraparte_de_outra_organizacao(
    recorder: LivestockEventRecorder,
    context: LivestockOperationContext,
) -> None:
    service, _, animal_id = _cenario(recorder, context)
    assert service.counterparty_repository is not None
    contraparte = ExternalCounterparty(
        counterparty_id=TypedId.new("external_counterparty"),
        organization_id=OrganizationId.new(),
        name="Fazenda Fora",
        counterparty_type=CounterpartyType.FARM,
    )
    service.counterparty_repository.save(contraparte)

    with pytest.raises(KeyError, match="Contraparte"):
        service.register_exit(
            context=context,
            animal_id=animal_id,
            exit_type=ExitType.VENDA,
            occurred_at=datetime.now(UTC) - timedelta(days=1),
            destination_counterparty_id=contraparte.counterparty_id,
        )


def test_sair_e_terminal(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    service, _, animal_id = _cenario(recorder, context)
    service.register_exit(
        context=context,
        animal_id=animal_id,
        exit_type=ExitType.MORTE,
        occurred_at=datetime.now(UTC) - timedelta(days=2),
    )

    with pytest.raises(SaidaJaRegistrada, match="já deixou o rebanho"):
        service.register_exit(
            context=context,
            animal_id=animal_id,
            exit_type=ExitType.VENDA,
            occurred_at=datetime.now(UTC) - timedelta(days=1),
        )


def test_saida_no_futuro_e_recusada(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    service, _, animal_id = _cenario(recorder, context)

    with pytest.raises(ValueError, match="não pode ser no futuro"):
        service.register_exit(
            context=context,
            animal_id=animal_id,
            exit_type=ExitType.MORTE,
            occurred_at=datetime.now(UTC) + timedelta(days=1),
        )


def test_animal_de_outra_organizacao_nao_e_alcancado(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    service, _, animal_id = _cenario(recorder, context)
    intruso = LivestockOperationContext.create(
        organization_id=OrganizationId.new(),
        actor_id=TypedId.new("actor"),
        source_id=TypedId.new("system"),
    )

    with pytest.raises(KeyError, match="não encontrado"):
        service.register_exit(
            context=intruso,
            animal_id=animal_id,
            exit_type=ExitType.MORTE,
            occurred_at=datetime.now(UTC) - timedelta(days=1),
        )


def test_guarda_recusa_fato_posterior_a_saida(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    service, animal_repo, animal_id = _cenario(recorder, context)
    saida_em = datetime.now(UTC) - timedelta(days=10)
    service.register_exit(
        context=context,
        animal_id=animal_id,
        exit_type=ExitType.MORTE,
        occurred_at=saida_em,
    )

    with pytest.raises(AnimalForaDoRebanho, match="não pôde ocorrer"):
        guard_animal_active(animal_repo, animal_id, saida_em + timedelta(days=1))


def test_guarda_aceita_fato_anterior_lancado_depois(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """Regularizar registro atrasado é história real, e não contradição."""
    service, animal_repo, animal_id = _cenario(recorder, context)
    saida_em = datetime.now(UTC) - timedelta(days=10)
    service.register_exit(
        context=context,
        animal_id=animal_id,
        exit_type=ExitType.ABATE,
        occurred_at=saida_em,
    )

    guard_animal_active(animal_repo, animal_id, saida_em - timedelta(days=3))
    # O instante exato da saída ainda pertence ao animal: o abate e o último
    # manejo podem coincidir no registro.
    guard_animal_active(animal_repo, animal_id, saida_em)


def test_guarda_e_silenciosa_para_animal_no_rebanho(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    _, animal_repo, animal_id = _cenario(recorder, context)

    guard_animal_active(animal_repo, animal_id, datetime.now(UTC))
