"""Agregado `Applicability` — Titan Asset & Sustainment (A2).

Modelo: `docs/asset/05_DOMAIN_MODEL.md` §1.5. Raiz de agregado própria — **não**
é campo de `Part` (`06_AGGREGATE_ANALYSIS.md` §3: aplicabilidade muda numa
cadência e por atores diferentes do catálogo da peça).

Invariantes (`docs/asset/07_INVARIANTS.md`):
I‑APP‑1 — toda `Applicability` `ASSERTED` tem `evidence_ref` obrigatório; nunca
existe aplicabilidade booleana sem evidência (constituição §11, §42).
I‑APP‑2 — retirada é por correção (`withdraw`), nunca por delete; o registro
original permanece no histórico/event log.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class ApplicabilityState(StrEnum):
    ASSERTED = "ASSERTED"
    WITHDRAWN = "WITHDRAWN"


class AplicabilidadeJaRetirada(ValueError):
    """`withdraw` chamado numa `Applicability` que já está `WITHDRAWN` (I‑APP‑2)."""


@dataclass(frozen=True, slots=True)
class ApplicabilityTarget:
    """VO — a que a peça se aplica. `05_DOMAIN_MODEL.md` §1.5.

    `serial_from`/`serial_to` abertos (`None`) cobrem uma faixa sem limite
    naquela ponta; `valid_until=None` significa "ainda vigente".
    """

    model_ref: TypedId
    variant_ref: TypedId | None
    serial_from: str | None
    serial_to: str | None
    valid_from: datetime
    valid_until: datetime | None

    def __post_init__(self) -> None:
        if self.model_ref.entity_type != "vehicle_model":
            raise ValueError(
                "model_ref deve ter entity_type 'vehicle_model', recebido "
                f"'{self.model_ref.entity_type}'."
            )
        if self.variant_ref is not None and self.variant_ref.entity_type != "vehicle_variant":
            raise ValueError(
                "variant_ref deve ter entity_type 'vehicle_variant', recebido "
                f"'{self.variant_ref.entity_type}'."
            )
        require_utc(self.valid_from, field_name="valid_from")
        if self.valid_until is not None:
            require_utc(self.valid_until, field_name="valid_until")
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until deve ser posterior a valid_from.")
        if (
            self.serial_from is not None
            and self.serial_to is not None
            and self.serial_from > self.serial_to
        ):
            raise ValueError("serial_from não pode ser posterior a serial_to.")

    def covers(self, *, at: datetime) -> bool:
        """A faixa de efetividade cobre o instante `at`? (`09_COMMAND_MODEL.md`
        `ResolvePartApplicability`)."""
        require_utc(at, field_name="at")
        if at < self.valid_from:
            return False
        return self.valid_until is None or at < self.valid_until


@dataclass(frozen=True, slots=True)
class Applicability:
    """Raiz de agregado. `05_DOMAIN_MODEL.md` §1.5; I‑APP‑1, I‑APP‑2."""

    applicability_id: TypedId
    organization_id: OrganizationId
    part_ref: TypedId
    part_revision_ref: TypedId
    target: ApplicabilityTarget
    evidence_ref: TypedId
    asserted_at: datetime
    asserted_by: TypedId
    state: ApplicabilityState = ApplicabilityState.ASSERTED
    withdrawal_reason: str | None = None
    withdrawn_at: datetime | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if self.applicability_id.entity_type != "applicability":
            raise ValueError(
                "applicability_id deve ter entity_type 'applicability', recebido "
                f"'{self.applicability_id.entity_type}'."
            )
        if self.part_ref.entity_type != "part":
            raise ValueError(
                f"part_ref deve ter entity_type 'part', recebido '{self.part_ref.entity_type}'."
            )
        if self.part_revision_ref.entity_type != "part_revision":
            raise ValueError(
                "part_revision_ref deve ter entity_type 'part_revision', recebido "
                f"'{self.part_revision_ref.entity_type}'."
            )
        # I-APP-1: sem evidência não há asserção. TypedId já é não-nulo pelo
        # tipo; a checagem de entity_type é a garantia de que é uma Evidence de
        # verdade, não qualquer referência solta.
        if self.evidence_ref.entity_type != "evidence":
            raise ValueError(
                "evidence_ref deve ter entity_type 'evidence' (core_domain.evidence), recebido "
                f"'{self.evidence_ref.entity_type}'."
            )
        require_utc(self.asserted_at, field_name="asserted_at")
        if self.state is ApplicabilityState.WITHDRAWN:
            if self.withdrawal_reason is None or not self.withdrawal_reason.strip():
                raise ValueError("withdrawal_reason é obrigatório quando state é WITHDRAWN.")
            if self.withdrawn_at is None:
                raise ValueError("withdrawn_at é obrigatório quando state é WITHDRAWN.")
            require_utc(self.withdrawn_at, field_name="withdrawn_at")
        elif self.withdrawal_reason is not None or self.withdrawn_at is not None:
            raise ValueError("withdrawal_reason/withdrawn_at só fazem sentido em state WITHDRAWN.")

    def withdraw(self, *, reason: str, withdrawn_at: datetime) -> "Applicability":
        """I‑APP‑2: correção aditiva — o registro `ASSERTED` original permanece
        no event log; este método só marca o estado corrente do agregado."""
        if self.state is ApplicabilityState.WITHDRAWN:
            raise AplicabilidadeJaRetirada(
                f"Applicability '{self.applicability_id.value}' já está retirada."
            )
        if not reason or not reason.strip():
            raise ValueError("reason é obrigatório para retirar uma aplicabilidade.")
        require_utc(withdrawn_at, field_name="withdrawn_at")
        return replace(
            self,
            state=ApplicabilityState.WITHDRAWN,
            withdrawal_reason=reason,
            withdrawn_at=withdrawn_at,
            version=self.version + 1,
        )

    def is_active_at(self, instant: datetime) -> bool:
        """Usado por `ResolvePartApplicability` — nunca retorna só `bool` para o
        chamador final sem o `evidence_ref` junto (I‑APP‑1); este método é o
        predicado interno que a query usa para filtrar."""
        return self.state is ApplicabilityState.ASSERTED and self.target.covers(at=instant)
