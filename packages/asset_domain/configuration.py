"""Agregado `ConfigurationBaseline` — Titan Asset & Sustainment (A2).

Modelo: `docs/asset/05_DOMAIN_MODEL.md` §1.3. Invariantes:
`docs/asset/07_INVARIANTS.md` I‑CFG‑1 (cadeia de revisão acíclica) e I‑CFG‑2
(efetividade não sobrepõe para a mesma posição).

**Diferença de `Part`/`Supersession` (`part.py`):** ali a cadeia inteira vive
dentro de UM agregado (`Part.revisions`/`Part.supersessions`), então o ciclo é
verificável só com o próprio estado. Aqui cada `ConfigurationBaseline` é um
agregado **imutável e publicado separadamente** — a cadeia cruza várias
instâncias ao longo do tempo. Por isso I‑CFG‑1/I‑CFG‑2 não são só validação de
`__post_init__`: são funções puras (`require_acyclic_revision_chain`,
`require_no_overlapping_effectivity`) que a camada de aplicação chama depois de
buscar o histórico relevante no repositório — a lógica do invariante mora no
domínio; os dados para avaliá‑lo vêm de fora, como em qualquer aggregate‑spanning
rule (mesmo motivo de `docs/asset/06_AGGREGATE_ANALYSIS.md` §4).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class ConfigurationView(StrEnum):
    AS_DESIGNED = "AS_DESIGNED"
    AS_BUILT = "AS_BUILT"
    AS_MAINTAINED = "AS_MAINTAINED"


class CadeiaDeRevisaoCiclica(ValueError):
    """A cadeia de `supersedes_ref` entre baselines fechou ciclo (I‑CFG‑1)."""


class EfetividadeSobreposta(ValueError):
    """Duas baselines ativas cobrem a mesma posição no mesmo intervalo (I‑CFG‑2)."""


@dataclass(frozen=True, slots=True)
class ConfigurationRevision:
    """VO — `05_DOMAIN_MODEL.md` §1.3."""

    number: int
    supersedes_ref: TypedId | None = None

    def __post_init__(self) -> None:
        if isinstance(self.number, bool) or not isinstance(self.number, int):
            raise TypeError("number deve ser inteiro.")
        if self.number < 1:
            raise ValueError("number deve ser >= 1.")
        if (
            self.supersedes_ref is not None
            and self.supersedes_ref.entity_type != "configuration_baseline"
        ):
            raise ValueError(
                "supersedes_ref deve ter entity_type 'configuration_baseline', recebido "
                f"'{self.supersedes_ref.entity_type}'."
            )


@dataclass(frozen=True, slots=True)
class Effectivity:
    """VO — faixa de série + tempo válido em que a baseline vale (`05` §1.3)."""

    valid_from: datetime
    valid_to: datetime | None = None
    serial_from: str | None = None
    serial_to: str | None = None

    def __post_init__(self) -> None:
        require_utc(self.valid_from, field_name="valid_from")
        if self.valid_to is not None:
            require_utc(self.valid_to, field_name="valid_to")
            if self.valid_to <= self.valid_from:
                raise ValueError("valid_to deve ser posterior a valid_from.")
        if (
            self.serial_from is not None
            and self.serial_to is not None
            and self.serial_from > self.serial_to
        ):
            raise ValueError("serial_from não pode ser posterior a serial_to.")

    def _overlaps_temporal(self, other: "Effectivity") -> bool:
        starts_before_other_ends = self.valid_to is None or self.valid_to > other.valid_from
        other_starts_before_self_ends = other.valid_to is None or other.valid_to > self.valid_from
        return starts_before_other_ends and other_starts_before_self_ends

    def _overlaps_serial(self, other: "Effectivity") -> bool:
        # Faixa aberta (None) numa ponta cobre "sem limite" naquela ponta.
        self_from, self_to = self.serial_from, self.serial_to
        other_from, other_to = other.serial_from, other.serial_to
        starts_before_other_ends = self_to is None or other_from is None or self_to >= other_from
        other_starts_before_self_ends = (
            other_to is None or self_from is None or other_to >= self_from
        )
        return starts_before_other_ends and other_starts_before_self_ends

    def conflicts_with(self, other: "Effectivity") -> bool:
        return self._overlaps_temporal(other) and self._overlaps_serial(other)


@dataclass(frozen=True, slots=True)
class BaselinePosition:
    """VO — `05_DOMAIN_MODEL.md` §1.3."""

    position_code: str
    part_ref: TypedId
    part_revision_ref: TypedId

    def __post_init__(self) -> None:
        if not self.position_code or not self.position_code.strip():
            raise ValueError("position_code não pode ser vazio.")
        if self.part_ref.entity_type != "part":
            raise ValueError(
                f"part_ref deve ter entity_type 'part', recebido '{self.part_ref.entity_type}'."
            )
        if self.part_revision_ref.entity_type != "part_revision":
            raise ValueError(
                "part_revision_ref deve ter entity_type 'part_revision', recebido "
                f"'{self.part_revision_ref.entity_type}'."
            )


@dataclass(frozen=True, slots=True)
class ConfigurationBaseline:
    """Raiz de agregado. `05_DOMAIN_MODEL.md` §1.3; `06_AGGREGATE_ANALYSIS.md` §1.

    Publicada uma vez; correções/supersessão criam uma **nova** instância que
    referencia esta por `revision.supersedes_ref` (constituição §24) — este
    objeto, uma vez construído, não tem método de mutação além do `version`
    interno de infraestrutura (nem isso é usado aqui: publicar de novo é criar
    outra baseline, não `replace()` esta).
    """

    baseline_id: TypedId
    organization_id: OrganizationId
    model_ref: TypedId
    revision: ConfigurationRevision
    effectivity: Effectivity
    positions: tuple[BaselinePosition, ...] = ()
    variant_ref: TypedId | None = None
    view: ConfigurationView = ConfigurationView.AS_DESIGNED
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.created_at, field_name="created_at")
        if self.baseline_id.entity_type != "configuration_baseline":
            raise ValueError(
                "baseline_id deve ter entity_type 'configuration_baseline', recebido "
                f"'{self.baseline_id.entity_type}'."
            )
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
        if self.revision.supersedes_ref == self.baseline_id:
            raise CadeiaDeRevisaoCiclica("Uma baseline não pode superseder a si mesma.")
        seen_positions: set[str] = set()
        for position in self.positions:
            if position.position_code in seen_positions:
                raise ValueError(
                    f"position_code '{position.position_code}' duplicado nesta baseline."
                )
            seen_positions.add(position.position_code)


def require_acyclic_revision_chain(
    candidate: ConfigurationBaseline, history: Sequence[ConfigurationBaseline]
) -> None:
    """I‑CFG‑1. `history` é o conjunto de baselines já publicadas que a
    aplicação buscou no repositório (tipicamente: todas as do mesmo
    `model_ref`/`variant_ref`). Chamar **antes** de persistir `candidate`.
    """
    if candidate.revision.supersedes_ref is None:
        return
    by_id = {baseline.baseline_id: baseline for baseline in history}
    visited = {candidate.baseline_id}
    current: TypedId | None = candidate.revision.supersedes_ref
    while current is not None:
        if current in visited:
            raise CadeiaDeRevisaoCiclica(
                f"Publicar esta baseline fecharia um ciclo envolvendo '{current.value}'."
            )
        visited.add(current)
        previous = by_id.get(current)
        current = previous.revision.supersedes_ref if previous is not None else None


def require_no_overlapping_effectivity(
    candidate: ConfigurationBaseline, others: Sequence[ConfigurationBaseline]
) -> None:
    """I‑CFG‑2. `others` é o conjunto de baselines ativas do mesmo
    `model_ref`/`variant_ref` que a aplicação buscou no repositório."""
    candidate_positions = {position.position_code for position in candidate.positions}
    if not candidate_positions:
        return
    for other in others:
        if other.baseline_id == candidate.baseline_id:
            continue
        if other.model_ref != candidate.model_ref or other.variant_ref != candidate.variant_ref:
            continue
        if not candidate.effectivity.conflicts_with(other.effectivity):
            continue
        other_positions = {position.position_code for position in other.positions}
        shared = candidate_positions & other_positions
        if shared:
            raise EfetividadeSobreposta(
                f"Baseline '{candidate.baseline_id.value}' sobrepõe a efetividade de "
                f"'{other.baseline_id.value}' na(s) posição(ões) {sorted(shared)}."
            )
