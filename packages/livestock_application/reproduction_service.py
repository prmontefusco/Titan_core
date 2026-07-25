"""Registro do parto e da perda gestacional (Passo 13.3 - Titan Livestock, ADR-0040).

**Um ato, uma transação.** O parto cria o evento, cada cria e as relações de
parentesco de uma vez só. Fazê-lo em duas chamadas — cadastrar o bezerro e depois
declarar de quem ele é — deixa uma janela em que o animal existe sem linhagem, e
se a segunda falha resta um órfão silencioso. Era assim até o Passo 13.2.

O agregado do evento é o **próprio evento reprodutivo**: mãe e crias o enxergam
por citação, e a linha do tempo da mãe contém o parto enquanto a do bezerro
começa nele. Um fato, duas histórias, sem duplicação.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.parentage_service import ParentageService
from packages.livestock_domain.animal import (
    Animal,
    AnimalSex,
    BirthOutcome,
    BirthPropertySource,
)
from packages.livestock_domain.events import (
    ANIMAL_REGISTERED,
    REPRODUCTIVE_EVENT_RECORDED,
    animal_registered_payload,
    reproductive_event_recorded_payload,
)
from packages.livestock_domain.parentage import ParentageConfidence, ParentageRole
from packages.livestock_domain.reproduction import (
    GestationalAgeBasis,
    Offspring,
    ReproductiveEvent,
    ReproductiveEventType,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc


class ReproductiveEventRepositoryPort(Protocol):
    def save(self, event: ReproductiveEvent) -> None: ...

    def get_by_id(self, event_id: TypedId) -> ReproductiveEvent | None: ...

    def list_by_dam(
        self, organization_id: OrganizationId, dam_id: TypedId
    ) -> list[ReproductiveEvent]: ...

    def get_by_offspring(self, animal_id: TypedId) -> ReproductiveEvent | None: ...


class MaternalStayReaderPort(Protocol):
    """Onde a mãe estava no instante do parto.

    Contrato mínimo de propósito: o serviço não precisa do histórico de estadias,
    precisa da propriedade determinável naquele instante — e de `None` quando não
    houver uma só.
    """

    def property_at(self, animal_id: TypedId, instant: datetime) -> TypedId | None: ...


class PropertyStayTimelinePort(Protocol):
    def get_timeline(self, animal_id: TypedId) -> list[Any]: ...


@dataclass(frozen=True, slots=True)
class StayBasedPropertyReader(MaternalStayReaderPort):
    """Onde a mãe estava, segundo a linha do tempo de permanências do Passo 8.4.

    **Só responde quando a permanência é única.** Duas estadias cobrindo o mesmo
    instante é dado contraditório, e escolher uma delas seria o sistema decidindo
    no lugar de quem sabe — melhor devolver nada e deixar o parto seguir com a
    propriedade declarada ou desconhecida.
    """

    stay_repository: PropertyStayTimelinePort

    def property_at(self, animal_id: TypedId, instant: datetime) -> TypedId | None:
        cobrindo = [
            estadia
            for estadia in self.stay_repository.get_timeline(animal_id)
            if estadia.start_time <= instant
            and (estadia.end_time is None or instant <= estadia.end_time)
        ]
        if len(cobrindo) != 1:
            return None
        return TypedId(entity_type="rural_property", value=cobrindo[0].property_id.value)


class PartoInvalido(ValueError):
    """O evento reprodutivo declarado não pode existir."""


class PropriedadeDivergeDaPermanencia(ValueError):
    """A propriedade declarada contradiz a permanência conhecida da mãe."""


@dataclass(frozen=True, slots=True)
class CriaDeclarada:
    """O que se sabe de cada cria no instante do parto."""

    outcome: BirthOutcome
    sex: AnimalSex = AnimalSex.UNKNOWN
    breed: str | None = None


@dataclass(frozen=True, slots=True)
class PartoRegistrado:
    """O que o ato produziu, para quem chamou não precisar consultar de novo."""

    event: ReproductiveEvent
    animals: tuple[Animal, ...]


@dataclass(frozen=True, slots=True)
class ReproductionService:
    """Registra o parto e a perda gestacional, com a linhagem no mesmo ato."""

    event_repository: ReproductiveEventRepositoryPort
    animal_repository: AnimalRepositoryPort
    parentage_service: ParentageService
    stay_reader: MaternalStayReaderPort
    recorder: LivestockEventRecorder

    def register_parturition(
        self,
        context: LivestockOperationContext,
        dam_id: TypedId,
        occurred_at: datetime,
        offspring: tuple[CriaDeclarada, ...],
        sire_id: TypedId | None = None,
        birth_property_id: TypedId | None = None,
        confidence: ParentageConfidence = ParentageConfidence.DECLARADO,
        gestational_age_days: int | None = None,
        gestational_age_basis: GestationalAgeBasis = GestationalAgeBasis.UNKNOWN,
        notes: str | None = None,
        evidence_references: tuple[UniversalReference, ...] = (),
    ) -> PartoRegistrado:
        """Um parto, N crias, e a linhagem de cada uma — tudo na mesma transação."""
        if not offspring:
            raise PartoInvalido(
                "Um parto produz ao menos uma cria. Para gestação encerrada sem "
                "indivíduo, registre uma perda gestacional."
            )
        organization_id = context.organization_id
        self._guard_occurred_at(occurred_at)
        mae = self._require_animal(organization_id, dam_id, "mãe")
        if mae.sex is not AnimalSex.FEMALE:
            raise PartoInvalido("Quem pare é fêmea; o animal informado como mãe não é.")
        if sire_id is not None:
            self._require_animal(organization_id, sire_id, "pai")

        propriedade, procedencia = self._resolver_propriedade(
            dam_id=dam_id, occurred_at=occurred_at, declarada=birth_property_id
        )

        criadas: list[Animal] = []
        crias: list[Offspring] = []
        for declarada in offspring:
            animal = self._criar_cria(
                context=context,
                declarada=declarada,
                occurred_at=occurred_at,
                propriedade=propriedade,
                procedencia=procedencia,
            )
            criadas.append(animal)
            crias.append(Offspring(animal_id=animal.animal_id, outcome=declarada.outcome))

        evento = ReproductiveEvent(
            event_id=TypedId.new("reproductive_event"),
            organization_id=organization_id,
            dam_id=dam_id,
            sire_id=sire_id,
            event_type=ReproductiveEventType.PARTO,
            occurred_at=occurred_at,
            offspring=tuple(crias),
            gestational_age_days=gestational_age_days,
            gestational_age_basis=gestational_age_basis,
            notes=notes,
            evidence_references=evidence_references,
            created_at=datetime.now(UTC),
        )
        self.event_repository.save(evento)
        self._registrar_evento(context, evento)

        # A linhagem entra depois das crias existirem, e no mesmo ato: é o que
        # elimina a janela em que o bezerro estava no rebanho sem saber de quem é.
        for animal in criadas:
            self.parentage_service.register_maternity(
                context=context,
                offspring_id=animal.animal_id,
                genetic_mother_id=dam_id,
                occurred_at=occurred_at,
                confidence=confidence,
            )
            if sire_id is not None:
                self.parentage_service.register_parentage(
                    context=context,
                    offspring_id=animal.animal_id,
                    parent_id=sire_id,
                    role=ParentageRole.PAI,
                    occurred_at=occurred_at,
                    confidence=confidence,
                )

        return PartoRegistrado(event=evento, animals=tuple(criadas))

    def register_pregnancy_loss(
        self,
        context: LivestockOperationContext,
        dam_id: TypedId,
        occurred_at: datetime,
        gestational_age_days: int | None = None,
        gestational_age_basis: GestationalAgeBasis = GestationalAgeBasis.UNKNOWN,
        notes: str | None = None,
        evidence_references: tuple[UniversalReference, ...] = (),
    ) -> ReproductiveEvent:
        """Aborto: encerra a gestação **sem** criar indivíduo.

        Criar um `Animal` com estado morto para um produto de gestação sem
        identidade atribuível seria fabricar entidade rastreável a partir de um
        fato que não a produziu.

        A classificação em precoce ou tardio é **derivada** por regra versionada,
        e nunca gravada aqui — mesmo princípio da carência no Passo 9.4: gravar a
        derivação criaria segunda fonte de verdade, que diverge no dia em que a
        regra mudar.
        """
        organization_id = context.organization_id
        self._guard_occurred_at(occurred_at)
        mae = self._require_animal(organization_id, dam_id, "mãe")
        if mae.sex is not AnimalSex.FEMALE:
            raise PartoInvalido("Quem gesta é fêmea; o animal informado não é.")

        evento = ReproductiveEvent(
            event_id=TypedId.new("reproductive_event"),
            organization_id=organization_id,
            dam_id=dam_id,
            event_type=ReproductiveEventType.ABORTO,
            occurred_at=occurred_at,
            gestational_age_days=gestational_age_days,
            gestational_age_basis=gestational_age_basis,
            notes=notes,
            evidence_references=evidence_references,
            created_at=datetime.now(UTC),
        )
        self.event_repository.save(evento)
        self._registrar_evento(context, evento)
        return evento

    def history_of(
        self, organization_id: OrganizationId, dam_id: TypedId
    ) -> tuple[ReproductiveEvent, ...]:
        return tuple(self.event_repository.list_by_dam(organization_id, dam_id))

    def origin_of(self, animal_id: TypedId) -> ReproductiveEvent | None:
        """O parto de onde este animal veio, quando houver."""
        return self.event_repository.get_by_offspring(animal_id)

    # -- Internos ------------------------------------------------------------

    def _criar_cria(
        self,
        context: LivestockOperationContext,
        declarada: CriaDeclarada,
        occurred_at: datetime,
        propriedade: TypedId | None,
        procedencia: BirthPropertySource,
    ) -> Animal:
        animal = Animal(
            animal_id=TypedId.new("animal"),
            organization_id=context.organization_id,
            birth_property_id=propriedade,
            sex=declarada.sex,
            breed=declarada.breed,
            birth_date=occurred_at.date(),
            birth_outcome=declarada.outcome,
            birth_property_source=procedencia,
            created_at=datetime.now(UTC),
        )
        self.animal_repository.save(animal)
        self.recorder.record(
            context=context,
            aggregate_id=animal.animal_id,
            event_type=ANIMAL_REGISTERED,
            payload=animal_registered_payload(
                animal_id=animal.animal_id,
                birth_property_id=propriedade,
                sex=animal.sex.value,
                breed=animal.breed,
                birth_date=_iso(animal.birth_date),
            ),
            occurred_at=occurred_at,
        )
        return animal

    def _registrar_evento(
        self, context: LivestockOperationContext, evento: ReproductiveEvent
    ) -> None:
        self.recorder.record(
            context=context,
            aggregate_id=evento.event_id,
            event_type=REPRODUCTIVE_EVENT_RECORDED,
            payload=reproductive_event_recorded_payload(
                event_id=evento.event_id,
                dam_id=evento.dam_id,
                sire_id=evento.sire_id,
                event_type=evento.event_type.value,
                occurred_at=evento.occurred_at,
                offspring=tuple((cria.animal_id, cria.outcome.value) for cria in evento.offspring),
                gestational_age_days=evento.gestational_age_days,
                gestational_age_basis=evento.gestational_age_basis.value,
                notes=evento.notes,
                evidence_references=evento.evidence_references,
            ),
            occurred_at=evento.occurred_at,
        )

    def _resolver_propriedade(
        self, dam_id: TypedId, occurred_at: datetime, declarada: TypedId | None
    ) -> tuple[TypedId | None, BirthPropertySource]:
        """Deriva da permanência materna; recua para a declaração; admite lacuna.

        **Ausência de dado contextual não impede o registro de um fato real.** É
        melhor ter "parto ocorrido, propriedade desconhecida" do que nenhum parto
        registrado porque a linha do tempo da mãe estava incompleta.

        Divergência, porém, não se resolve em silêncio: se a declarada contradiz
        a permanência conhecida, o registro é recusado para que alguém decida
        conscientemente qual das duas está certa.
        """
        permanencia = self.stay_reader.property_at(dam_id, occurred_at)
        if permanencia is not None:
            if declarada is not None and declarada != permanencia:
                raise PropriedadeDivergeDaPermanencia(
                    f"A propriedade declarada ('{declarada.value}') contradiz a permanência "
                    f"da mãe no parto ('{permanencia.value}'). A contradição precisa ser "
                    "corrigida conscientemente, e não escolhida pelo sistema."
                )
            return permanencia, BirthPropertySource.DERIVED_FROM_MATERNAL_STAY
        if declarada is not None:
            return declarada, BirthPropertySource.DECLARED
        return None, BirthPropertySource.UNKNOWN

    def _require_animal(
        self, organization_id: OrganizationId, animal_id: TypedId, papel: str
    ) -> Animal:
        encontrado = self.animal_repository.get_by_id(animal_id)
        if encontrado is None or encontrado.organization_id != organization_id:
            raise KeyError(f"Animal '{animal_id.value}' ({papel}) não encontrado.")
        return encontrado

    @staticmethod
    def _guard_occurred_at(occurred_at: datetime) -> None:
        require_utc(occurred_at, field_name="occurred_at")
        if occurred_at > datetime.now(UTC):
            raise PartoInvalido("occurred_at não pode ser no futuro.")


def _iso(valor: date | None) -> str | None:
    return None if valor is None else valor.isoformat()
