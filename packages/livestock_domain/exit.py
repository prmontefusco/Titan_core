"""Saída do animal do rebanho (Passo 13.1 - Titan Livestock).

Até aqui o animal não tinha fim: todo animal cadastrado permanecia implicitamente
vivo e presente. Um recall varreria animais mortos há anos, a carência seria
calculada para bois que já saíram, e toda listagem nasceria enviesada.

**A saída é terminal e o estado é derivado.** Não há campo mutável em `Animal`
dizendo "ativo" ou "saiu" — quem responde isso é a existência do registro de
saída. Estado guardado em campo diverge do histórico assim que alguém o edita;
estado derivado não tem como divergir.

O que a saída encerra é o **futuro**, não o passado: ver `AnimalExit.admite_fato_em`.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc


class ExitType(StrEnum):
    """Por que o animal deixou o rebanho.

    A distinção importa porque as consequências diferem: o abate alimenta a cadeia
    de produtos, a venda transfere a responsabilidade a outra organização, e a
    morte encerra sem destino comercial.
    """

    MORTE = "MORTE"
    ABATE = "ABATE"
    VENDA = "VENDA"
    TRANSFERENCIA_DEFINITIVA = "TRANSFERENCIA_DEFINITIVA"


@dataclass(frozen=True, slots=True)
class AnimalExit:
    """Registro imutável da saída de um animal do rebanho."""

    exit_id: TypedId
    organization_id: OrganizationId
    animal_id: TypedId
    exit_type: ExitType
    occurred_at: datetime
    reason: str | None = None
    evidence_references: tuple[UniversalReference, ...] = ()
    destination: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.occurred_at, field_name="occurred_at")
        require_utc(self.created_at, field_name="created_at")
        if self.exit_id.entity_type != "animal_exit":
            raise ValueError(
                "exit_id deve ter entity_type 'animal_exit', recebido "
                f"'{self.exit_id.entity_type}'."
            )
        if self.animal_id.entity_type != "animal":
            raise ValueError(
                f"animal_id deve ter entity_type 'animal', recebido '{self.animal_id.entity_type}'."
            )
        if not isinstance(self.exit_type, ExitType):
            raise TypeError("exit_type deve ser um ExitType.")
        if self.reason is not None and not self.reason.strip():
            raise ValueError("reason, quando informado, não pode ser vazio.")
        if self.destination is not None and not self.destination.strip():
            raise ValueError("destination, quando informado, não pode ser vazio.")
        for referencia in self.evidence_references:
            if not isinstance(referencia, UniversalReference):
                raise TypeError("evidence_references deve conter UniversalReference.")
            if referencia.target_id.entity_type != "evidence":
                raise ValueError("evidence_references deve apontar para 'evidence'.")
            if referencia.organization_id != self.organization_id:
                raise ValueError("A evidência citada pertence a outra Organization.")

    def admite_fato_em(self, occurred_at: datetime) -> bool:
        """Um fato posterior à saída é recusado; um anterior, aceito.

        O critério é o instante em que o fato **ocorreu**, nunca o do registro.
        Um tratamento aplicado antes da saída e lançado com atraso é história
        real, e recusá-lo apagaria o que aconteceu — que é justamente o que um
        registro append-only não faz. Já um tratamento aplicado depois da saída
        não pôde acontecer: o animal não estava mais lá.
        """
        require_utc(occurred_at, field_name="occurred_at")
        return occurred_at <= self.occurred_at
