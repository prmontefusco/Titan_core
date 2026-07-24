"""Cálculo determinístico de carência (WithdrawalPeriod) — Passo 9.4 - Titan Livestock.

Regra de negócio aprovada e versionada `titan-livestock-withdrawal-v1`:

- por aplicação, `withdrawal_ends_at = applied_at + withdrawal_period_days` (dias
  corridos, em UTC — por isso o Core exige instantes UTC);
- por animal, a carência termina no MAIOR `withdrawal_ends_at` entre as aplicações
  efetivas: o animal só está livre quando todas as carências passaram;
- o animal está elegível quando `instante >= eligible_from`.

O cálculo congela (snapshot) o `withdrawal_period_days` usado e a versão da regra
no resultado. Editar o medicamento depois NÃO reescreve um cálculo já feito — é o
que permite a um dossiê reproduzir a decisão no futuro.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from packages.shared_kernel import TypedId
from packages.shared_kernel.temporal import require_utc

WITHDRAWAL_RULE_VERSION = "titan-livestock-withdrawal-v1"


def compute_withdrawal_ends(applied_at: datetime, withdrawal_period_days: int) -> datetime:
    """Fim da carência de uma aplicação: `applied_at + dias`, determinístico em UTC."""
    require_utc(applied_at, field_name="applied_at")
    if not isinstance(withdrawal_period_days, int) or withdrawal_period_days < 0:
        raise ValueError("withdrawal_period_days deve ser um inteiro >= 0.")
    return applied_at + timedelta(days=withdrawal_period_days)


@dataclass(frozen=True, slots=True)
class WithdrawalContribution:
    """A carência que UMA aplicação impõe, com o prazo congelado no cálculo."""

    application_id: TypedId
    medication_batch_id: TypedId
    applied_at: datetime
    withdrawal_period_days: int
    withdrawal_ends_at: datetime

    def __post_init__(self) -> None:
        require_utc(self.applied_at, field_name="applied_at")
        require_utc(self.withdrawal_ends_at, field_name="withdrawal_ends_at")
        if self.application_id.entity_type != "treatment_application":
            raise ValueError("application_id deve ser 'treatment_application'.")
        if self.medication_batch_id.entity_type != "medication_batch":
            raise ValueError("medication_batch_id deve ser 'medication_batch'.")
        if not isinstance(self.withdrawal_period_days, int) or self.withdrawal_period_days < 0:
            raise ValueError("withdrawal_period_days deve ser um inteiro >= 0.")
        if self.withdrawal_ends_at != compute_withdrawal_ends(
            self.applied_at, self.withdrawal_period_days
        ):
            raise ValueError("withdrawal_ends_at não confere com applied_at + dias.")

    @classmethod
    def create(
        cls,
        application_id: TypedId,
        medication_batch_id: TypedId,
        applied_at: datetime,
        withdrawal_period_days: int,
    ) -> "WithdrawalContribution":
        return cls(
            application_id=application_id,
            medication_batch_id=medication_batch_id,
            applied_at=applied_at,
            withdrawal_period_days=withdrawal_period_days,
            withdrawal_ends_at=compute_withdrawal_ends(applied_at, withdrawal_period_days),
        )


@dataclass(frozen=True, slots=True)
class AnimalWithdrawalStatus:
    """Situação de carência de um animal, com a versão da regra preservada."""

    animal_id: TypedId
    rule_version: str
    contributions: tuple[WithdrawalContribution, ...]
    eligible_from: datetime | None

    def __post_init__(self) -> None:
        if self.animal_id.entity_type != "animal":
            raise ValueError("animal_id deve ser 'animal'.")
        if self.eligible_from is not None:
            require_utc(self.eligible_from, field_name="eligible_from")
        expected = _max_ends(self.contributions)
        if self.eligible_from != expected:
            raise ValueError("eligible_from deve ser o maior withdrawal_ends_at das contribuições.")

    def is_in_withdrawal_at(self, instant: datetime) -> bool:
        """Em carência quando ainda não chegou o instante de elegibilidade."""
        require_utc(instant, field_name="instant")
        return self.eligible_from is not None and instant < self.eligible_from

    def is_eligible_at(self, instant: datetime) -> bool:
        return not self.is_in_withdrawal_at(instant)


def _max_ends(contributions: tuple[WithdrawalContribution, ...]) -> datetime | None:
    return max((c.withdrawal_ends_at for c in contributions), default=None)


def build_animal_withdrawal_status(
    animal_id: TypedId, contributions: tuple[WithdrawalContribution, ...]
) -> AnimalWithdrawalStatus:
    """Agrega as contribuições: sem tratamento, `eligible_from` é None (sempre elegível)."""
    return AnimalWithdrawalStatus(
        animal_id=animal_id,
        rule_version=WITHDRAWAL_RULE_VERSION,
        contributions=contributions,
        eligible_from=_max_ends(contributions),
    )
