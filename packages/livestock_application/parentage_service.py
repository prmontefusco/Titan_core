"""Registro e travessia da genealogia (Passo 13.2 - Titan Livestock).

Primeira vez que a vertical usa a Relação Universal do Passo 7.1. O que ela
acrescenta ao Core são as regras que só o gado tem: qual sexo cabe em qual
papel, quantos progenitores de cada tipo um animal pode ter, e o fato de a
linhagem subir pela maternidade **genética** e não pela gestacional.

**A guarda de saída do rebanho não se aplica aqui.** Parentesco é fato anterior
ao nascimento, e descobrir a mãe de um boi já abatido é exatamente a
regularização que a decisão D-2 protege — é o que uma auditoria pós-abate faz.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from packages.core_application.relation_service import RelationService
from packages.core_domain.relations import UniversalRelation
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    AGGREGATE_CONTRACT_VERSION,
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_domain.animal import Animal
from packages.livestock_domain.events import PARENTAGE_REGISTERED, parentage_registered_payload
from packages.livestock_domain.parentage import (
    PAPEIS_DE_LINHAGEM,
    PAPEIS_EXCLUSIVOS,
    RELATION_TYPE_BY_ROLE,
    ROLE_BY_RELATION_TYPE,
    SEXO_EXIGIDO,
    ParentageConfidence,
    ParentageRole,
    confidence_from_tier,
    confidence_level,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc

# Descer a árvore ramifica muito mais depressa do que subir: uma matriz tem
# dezenas de crias, e cada cria tem duas ascendências. O padrão sobe três
# gerações, que é o que um registro genealógico costuma exibir.
GERACOES_PADRAO = 3
GERACOES_MAXIMAS = 10


class ParentescoInvalido(ValueError):
    """O vínculo declarado não pode existir."""


class ProgenitorJaRegistrado(ValueError):
    """Já existe vínculo vigente deste papel para esta cria."""


@dataclass(frozen=True, slots=True)
class ParentageLink:
    """Um vínculo de parentesco, já desligado da relação que o originou."""

    relation_id: TypedId
    parent_id: TypedId
    offspring_id: TypedId
    role: ParentageRole
    confidence: ParentageConfidence | None
    confidence_reason: str
    occurred_at: datetime | None


@dataclass(frozen=True, slots=True)
class AncestorBranch:
    """Como se chegou ao ancestral, e o que há acima dele."""

    link: ParentageLink
    ancestry: "Ancestry"


@dataclass(frozen=True, slots=True)
class Ancestry:
    """A árvore genealógica de um animal, subindo pela linhagem genética."""

    animal_id: TypedId
    parents: tuple[AncestorBranch, ...]


@dataclass(frozen=True, slots=True)
class ParentageService:
    """Registra parentesco e percorre a genealogia dentro de uma Organization."""

    relation_service: RelationService
    animal_repository: AnimalRepositoryPort
    recorder: LivestockEventRecorder

    # -- Escrita -------------------------------------------------------------

    def register_parentage(
        self,
        context: LivestockOperationContext,
        offspring_id: TypedId,
        parent_id: TypedId,
        role: ParentageRole,
        occurred_at: datetime,
        confidence: ParentageConfidence,
        confidence_reason: str | None = None,
        evidence_references: tuple[UniversalReference, ...] = (),
    ) -> UniversalRelation:
        organization_id = context.organization_id
        if not isinstance(role, ParentageRole):
            raise TypeError("role deve ser um ParentageRole.")
        self._guard_occurred_at(occurred_at)

        cria = self._require_animal(organization_id, offspring_id, "cria")
        progenitor = self._require_animal(organization_id, parent_id, "progenitor")
        self._guard_distintos(cria, progenitor)
        self._guard_sexo(progenitor, role)
        self._guard_idade(cria, progenitor)

        vigentes = self._links_de_ascendencia(organization_id, offspring_id, occurred_at)
        self._guard_exclusividade(vigentes, role, parent_id)
        self._guard_paternidade_multipla(vigentes, role, confidence)
        self._guard_ciclo(organization_id, offspring_id, parent_id, occurred_at)

        nivel = confidence_level(confidence, confidence_reason)
        relacao = UniversalRelation.create(
            organization_id=organization_id,
            source_reference=self._referencia(organization_id, parent_id),
            target_reference=self._referencia(organization_id, offspring_id),
            relation_type=RELATION_TYPE_BY_ROLE[role],
            created_at=datetime.now(UTC),
            confidence=nivel,
            valid_from=occurred_at,
            evidence_references=evidence_references,
        )

        # O evento nasce antes de a relação ser gravada porque é ele que dá ao
        # vínculo a autoria e a correlação. O agregado é a própria relação: é a
        # entidade criada aqui, e as duas pontas a enxergam por citação.
        evento = self.recorder.record(
            context=context,
            aggregate_id=relacao.relation_id,
            event_type=PARENTAGE_REGISTERED,
            payload=parentage_registered_payload(
                relation_id=relacao.relation_id,
                offspring_id=offspring_id,
                parent_id=parent_id,
                role=role.value,
                relation_type=relacao.relation_type,
                confidence=confidence.value,
                confidence_reason=nivel.reason,
                occurred_at=occurred_at,
                evidence_references=evidence_references,
            ),
            occurred_at=occurred_at,
        )
        registrada = replace(relacao, created_by_event=evento.event_id)
        return self.relation_service.register_relation(registrada)

    def register_maternity(
        self,
        context: LivestockOperationContext,
        offspring_id: TypedId,
        genetic_mother_id: TypedId,
        occurred_at: datetime,
        confidence: ParentageConfidence,
        gestational_mother_id: TypedId | None = None,
        confidence_reason: str | None = None,
        evidence_references: tuple[UniversalReference, ...] = (),
    ) -> tuple[UniversalRelation, UniversalRelation]:
        """Um ato do operador, dois fatos no registro.

        Sem transferência de embrião, doadora e receptora são a mesma vaca — e
        ainda assim as duas relações são gravadas. Deixar a gestacional implícita
        obrigaria toda consulta futura a inferir, e inferência silenciosa é o que
        produz o dado que se contradiz. **Ausência se declara, nunca se omite.**
        """
        genetica = self.register_parentage(
            context=context,
            offspring_id=offspring_id,
            parent_id=genetic_mother_id,
            role=ParentageRole.MAE_GENETICA,
            occurred_at=occurred_at,
            confidence=confidence,
            confidence_reason=confidence_reason,
            evidence_references=evidence_references,
        )
        gestacional = self.register_parentage(
            context=context,
            offspring_id=offspring_id,
            parent_id=gestational_mother_id or genetic_mother_id,
            role=ParentageRole.MAE_GESTACIONAL,
            occurred_at=occurred_at,
            confidence=confidence,
            confidence_reason=confidence_reason,
            evidence_references=evidence_references,
        )
        return genetica, gestacional

    # -- Leitura -------------------------------------------------------------

    def ancestry(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        generations: int = GERACOES_PADRAO,
        at_time: datetime | None = None,
    ) -> Ancestry:
        """Sobe pela linhagem genética: mãe doadora e pai, nunca a receptora."""
        if generations < 1 or generations > GERACOES_MAXIMAS:
            raise ValueError(f"generations deve estar entre 1 e {GERACOES_MAXIMAS}.")
        return self._subir(organization_id, animal_id, generations, at_time, set())

    def descendants(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        at_time: datetime | None = None,
    ) -> tuple[ParentageLink, ...]:
        """As crias diretas, pela linhagem genética."""
        return tuple(
            link
            for link in self._links_de_descendencia(organization_id, animal_id, at_time)
            if link.role in PAPEIS_DE_LINHAGEM
        )

    def gestational_history(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        at_time: datetime | None = None,
    ) -> tuple[ParentageLink, ...]:
        """As crias que esta fêmea gestou — pergunta distinta da descendência.

        Uma receptora gestou bezerros que não descendem dela. Misturar as duas
        consultas faria a árvore genealógica ganhar ancestrais que não são.
        """
        return tuple(
            link
            for link in self._links_de_descendencia(organization_id, animal_id, at_time)
            if link.role is ParentageRole.MAE_GESTACIONAL
        )

    def parents_of(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        at_time: datetime | None = None,
    ) -> tuple[ParentageLink, ...]:
        """Todos os progenitores vigentes, inclusive a receptora."""
        return self._links_de_ascendencia(organization_id, animal_id, at_time)

    # -- Travessia -----------------------------------------------------------

    def _subir(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        restantes: int,
        at_time: datetime | None,
        visitados: set[str],
    ) -> Ancestry:
        chave = str(animal_id.value)
        if restantes <= 0 or chave in visitados:
            return Ancestry(animal_id=animal_id, parents=())
        visitados = visitados | {chave}

        ramos: list[AncestorBranch] = []
        for link in self._links_de_ascendencia(organization_id, animal_id, at_time):
            if link.role not in PAPEIS_DE_LINHAGEM:
                continue
            ramos.append(
                AncestorBranch(
                    link=link,
                    ancestry=self._subir(
                        organization_id, link.parent_id, restantes - 1, at_time, visitados
                    ),
                )
            )
        return Ancestry(animal_id=animal_id, parents=tuple(ramos))

    def _links_de_ascendencia(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        at_time: datetime | None,
    ) -> tuple[ParentageLink, ...]:
        relacoes = self.relation_service.list_incoming_at(
            organization_id=organization_id,
            target_reference=self._referencia(organization_id, animal_id),
            at_time=at_time,
        )
        return _somente_parentesco(relacoes)

    def _links_de_descendencia(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        at_time: datetime | None,
    ) -> tuple[ParentageLink, ...]:
        relacoes = self.relation_service.list_outgoing_at(
            organization_id=organization_id,
            source_reference=self._referencia(organization_id, animal_id),
            at_time=at_time,
        )
        return _somente_parentesco(relacoes)

    # -- Guardas -------------------------------------------------------------

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
            raise ParentescoInvalido("occurred_at não pode ser no futuro.")

    @staticmethod
    def _guard_distintos(cria: Animal, progenitor: Animal) -> None:
        if cria.animal_id == progenitor.animal_id:
            raise ParentescoInvalido("Um animal não pode ser progenitor de si mesmo.")

    @staticmethod
    def _guard_sexo(progenitor: Animal, role: ParentageRole) -> None:
        exigido = SEXO_EXIGIDO[role]
        if progenitor.sex is not exigido:
            raise ParentescoInvalido(
                f"O papel {role.value} exige um animal {exigido.value}, e o informado é "
                f"{progenitor.sex.value}."
            )

    @staticmethod
    def _guard_idade(cria: Animal, progenitor: Animal) -> None:
        """Só confere quando as duas datas existem: sem data, não se inventa a conferência."""
        if cria.birth_date is None or progenitor.birth_date is None:
            return
        if progenitor.birth_date >= cria.birth_date:
            raise ParentescoInvalido(
                "O progenitor não nasceu antes da cria: "
                f"{progenitor.birth_date.isoformat()} contra {cria.birth_date.isoformat()}."
            )

    @staticmethod
    def _guard_exclusividade(
        vigentes: Sequence[ParentageLink], role: ParentageRole, parent_id: TypedId
    ) -> None:
        for link in vigentes:
            if link.role is not role:
                continue
            if link.parent_id == parent_id:
                raise ProgenitorJaRegistrado(
                    f"Este animal já está registrado como {role.value} desta cria."
                )
            if role in PAPEIS_EXCLUSIVOS:
                raise ProgenitorJaRegistrado(
                    f"A cria já possui {role.value} vigente. Duas são contradição, "
                    "e não dado incompleto: encerre a vigente antes de declarar outra."
                )

    @staticmethod
    def _guard_paternidade_multipla(
        vigentes: Sequence[ParentageLink],
        role: ParentageRole,
        confidence: ParentageConfidence,
    ) -> None:
        """Vários pais possíveis só se todos forem declarados.

        É o caso do touro do lote: monta natural com vários reprodutores, em que
        a paternidade só se resolve por exame de DNA. Quem tem registro de
        cobertura ou exame afirma **um** pai — admitir um segundo ao lado de um
        vínculo documentado transformaria prova em palpite.
        """
        if role is not ParentageRole.PAI:
            return
        pais = [link for link in vigentes if link.role is ParentageRole.PAI]
        if not pais:
            return
        if confidence is not ParentageConfidence.DECLARADO or any(
            link.confidence is not ParentageConfidence.DECLARADO for link in pais
        ):
            raise ProgenitorJaRegistrado(
                "Paternidade múltipla só é admitida quando todos os vínculos são "
                "DECLARADO — é o caso do touro do lote."
            )

    def _guard_ciclo(
        self,
        organization_id: OrganizationId,
        offspring_id: TypedId,
        parent_id: TypedId,
        at_time: datetime,
    ) -> None:
        """Barra o inverso imediato: se A já é progenitor de B, B não pode sê-lo de A.

        Ciclo profundo exigiria varrer a árvore a cada escrita, e o custo não se
        paga. Fica como limite conhecido, e a travessia se defende com o conjunto
        de visitados.
        """
        for link in self._links_de_ascendencia(organization_id, parent_id, at_time):
            if link.parent_id == offspring_id:
                raise ParentescoInvalido(
                    "Vínculo circular: o progenitor informado já descende desta cria."
                )

    @staticmethod
    def _referencia(organization_id: OrganizationId, animal_id: TypedId) -> UniversalReference:
        return UniversalReference(
            target_id=animal_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )


def _somente_parentesco(relacoes: Sequence[UniversalRelation]) -> tuple[ParentageLink, ...]:
    """A tabela de relações é do Core e guarda vínculos de toda natureza."""
    encontrados: list[ParentageLink] = []
    for relacao in relacoes:
        papel = ROLE_BY_RELATION_TYPE.get(relacao.relation_type)
        if papel is None:
            continue
        encontrados.append(
            ParentageLink(
                relation_id=relacao.relation_id,
                parent_id=relacao.source_reference.target_id,
                offspring_id=relacao.target_reference.target_id,
                role=papel,
                confidence=confidence_from_tier(relacao.confidence.tier),
                confidence_reason=relacao.confidence.reason,
                occurred_at=relacao.period.valid_from,
            )
        )
    return tuple(encontrados)
