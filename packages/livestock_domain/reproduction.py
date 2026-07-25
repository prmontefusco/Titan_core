"""Evento reprodutivo materno (Passo 13.3 - Titan Livestock, ADR-0040).

O evento reprodutivo é **separado do indivíduo rastreável**, e é essa separação
que faz os três casos difíceis caírem no lugar sem exceção:

    Gestação
       │
       └── Evento reprodutivo
              │
              ├── PARTO
              │    ├── Bezerro A → Animal
              │    └── Bezerro B → Animal
              │
              └── ABORTO
                   └── perda gestacional (sem Animal)

O parto é um evento **materno** capaz de produzir zero, um ou vários indivíduos,
cada qual com o seu próprio resultado de nascimento. Modelar o parto gemelar como
dois partos perderia o vínculo obstétrico entre irmãos — que é justamente o que
explica o natimorto quando o outro nasce vivo.

`Pregnancy` não existe aqui: ela pressupõe cobertura e diagnóstico, que são o
Marco 16, e exigi-la recusaria o caso majoritário do campo, em que o parto é
registrado sem que a cobertura tenha sido.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.livestock_domain.animal import BirthOutcome
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc


class ReproductiveEventType(StrEnum):
    PARTO = "PARTO"
    ABORTO = "ABORTO"


class GestationalAgeBasis(StrEnum):
    """Como a idade gestacional foi determinada.

    Existe para o dado ser útil sem fingir precisão: uma idade estimada a partir
    da data de inseminação não é uma medida de ultrassonografia, e apresentá-las
    como iguais faria o indicador afirmar mais do que se sabe.
    """

    KNOWN = "KNOWN"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Offspring:
    """Uma cria produzida pelo parto, com o seu próprio resultado.

    O gemelar com um vivo e um natimorto é o caso que justifica o resultado ser
    por cria, e não do evento.
    """

    animal_id: TypedId
    outcome: BirthOutcome

    def __post_init__(self) -> None:
        if self.animal_id.entity_type != "animal":
            raise ValueError(
                f"animal_id deve ter entity_type 'animal', recebido '{self.animal_id.entity_type}'."
            )
        if self.outcome is BirthOutcome.NAO_INFORMADO:
            raise ValueError(
                "Uma cria de parto registrado tem resultado conhecido: quem registra o "
                "parto sabe se o bezerro nasceu vivo."
            )


@dataclass(frozen=True, slots=True)
class ReproductiveEvent:
    """Registro imutável de um parto ou de uma perda gestacional."""

    event_id: TypedId
    organization_id: OrganizationId
    dam_id: TypedId
    event_type: ReproductiveEventType
    occurred_at: datetime
    offspring: tuple[Offspring, ...] = ()
    sire_id: TypedId | None = None
    gestational_age_days: int | None = None
    gestational_age_basis: GestationalAgeBasis = GestationalAgeBasis.UNKNOWN
    notes: str | None = None
    evidence_references: tuple[UniversalReference, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.occurred_at, field_name="occurred_at")
        require_utc(self.created_at, field_name="created_at")
        if self.event_id.entity_type != "reproductive_event":
            raise ValueError(
                "event_id deve ter entity_type 'reproductive_event', recebido "
                f"'{self.event_id.entity_type}'."
            )
        if self.dam_id.entity_type != "animal":
            raise ValueError("dam_id deve apontar para um animal.")
        if self.sire_id is not None and self.sire_id.entity_type != "animal":
            raise ValueError("sire_id deve apontar para um animal.")
        if not isinstance(self.event_type, ReproductiveEventType):
            raise TypeError("event_type deve ser um ReproductiveEventType.")

        if self.event_type is ReproductiveEventType.PARTO and not self.offspring:
            raise ValueError("Um parto produz ao menos uma cria; sem cria, é perda gestacional.")
        if self.event_type is ReproductiveEventType.ABORTO and self.offspring:
            raise ValueError(
                "O aborto não produz indivíduo rastreável: criar um seria fabricar "
                "entidade a partir de um fato que não a produziu."
            )

        vistos = {cria.animal_id.value for cria in self.offspring}
        if len(vistos) != len(self.offspring):
            raise ValueError("A mesma cria aparece duas vezes no parto.")
        if self.dam_id.value in vistos:
            raise ValueError("A mãe não pode ser cria do próprio parto.")

        self._guard_idade_gestacional()

        if self.notes is not None and not self.notes.strip():
            raise ValueError("notes, quando informado, não pode ser vazio.")
        for referencia in self.evidence_references:
            if referencia.target_id.entity_type != "evidence":
                raise ValueError("evidence_references deve apontar para 'evidence'.")
            if referencia.organization_id != self.organization_id:
                raise ValueError("A evidência citada pertence a outra Organization.")

    def _guard_idade_gestacional(self) -> None:
        """Ausência significa `UNKNOWN` — nunca zero, nunca estimativa fabricada."""
        if self.gestational_age_days is None:
            if self.gestational_age_basis is not GestationalAgeBasis.UNKNOWN:
                raise ValueError(
                    "Sem idade gestacional, a base tem de ser UNKNOWN: declarar como "
                    "conhecida uma idade ausente é inventar precisão."
                )
            return
        if self.gestational_age_basis is GestationalAgeBasis.UNKNOWN:
            raise ValueError(
                "Há idade gestacional, então a base de determinação precisa ser declarada."
            )
        if self.gestational_age_days <= 0:
            raise ValueError(
                "gestational_age_days deve ser positivo. Zero não é 'desconhecido' — "
                "para desconhecido, omita o campo."
            )

    @property
    def nascidos_vivos(self) -> int:
        return sum(1 for cria in self.offspring if cria.outcome is BirthOutcome.NASCIDO_VIVO)

    @property
    def natimortos(self) -> int:
        return sum(1 for cria in self.offspring if cria.outcome is BirthOutcome.NATIMORTO)
