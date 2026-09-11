"""Agregados `Part` e `InterchangeabilityGroup` — Titan Asset & Sustainment (A2).

Modelo: `docs/asset/05_DOMAIN_MODEL.md` §1.4, §1.6. Invariantes:
`docs/asset/07_INVARIANTS.md` I‑PRT‑1 (supersessão acíclica; instalação histórica
preservada — a preservação é responsabilidade de quem lê `ConfigurationBaseline`,
não deste agregado) e I‑PRT‑2 (intercambiabilidade simétrica).

**Part não tem quantidade** (constituição §8, I‑INV‑0) — nenhum campo de estoque
aqui; isso é `StockPosition` (`packages/asset_domain/inventory.py`, próximo
incremento).
"""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class PartLifecycleState(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    OBSOLETE = "OBSOLETE"
    ALTERNATE = "ALTERNATE"


class SupersessaoCiclica(ValueError):
    """Uma cadeia de `Supersession` fechou ciclo (I‑PRT‑1)."""


class RevisaoNaoEncontrada(KeyError):
    """Uma `PartRevision` referenciada não existe neste `Part`."""


@dataclass(frozen=True, slots=True)
class PartIdentity:
    """VO — `05_DOMAIN_MODEL.md` §1.4."""

    part_number: str
    description: str
    manufacturer: str
    manufacturer_pn: str | None = None
    nsn: str | None = None
    external_classifications: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.part_number or not self.part_number.strip():
            raise ValueError("part_number não pode ser vazio.")
        if not self.description or not self.description.strip():
            raise ValueError("description não pode ser vazia.")
        if not self.manufacturer or not self.manufacturer.strip():
            raise ValueError("manufacturer não pode ser vazio.")


@dataclass(frozen=True, slots=True)
class PartRevision:
    """Entidade interna de `Part` — versão de engenharia (`05` §1.4)."""

    revision_id: TypedId
    revision_code: str
    lifecycle_state: PartLifecycleState = PartLifecycleState.ACTIVE
    spec_ref: TypedId | None = None
    drawing_ref: TypedId | None = None
    materials: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.revision_id.entity_type != "part_revision":
            raise ValueError(
                "revision_id deve ter entity_type 'part_revision', recebido "
                f"'{self.revision_id.entity_type}'."
            )
        if not self.revision_code or not self.revision_code.strip():
            raise ValueError("revision_code não pode ser vazio.")


@dataclass(frozen=True, slots=True)
class Supersession:
    """VO — aresta do grafo de supersessão (I‑PRT‑1)."""

    predecessor_revision_id: TypedId
    successor_revision_id: TypedId
    reason: str

    def __post_init__(self) -> None:
        if self.predecessor_revision_id == self.successor_revision_id:
            raise ValueError("Uma revisão não pode superseder a si mesma.")
        if not self.reason or not self.reason.strip():
            raise ValueError("reason é obrigatório para registrar uma supersessão.")


@dataclass(frozen=True, slots=True)
class Part:
    """Raiz de agregado. `05_DOMAIN_MODEL.md` §1.4; `06_AGGREGATE_ANALYSIS.md` §1."""

    part_id: TypedId
    organization_id: OrganizationId
    identity: PartIdentity
    revisions: tuple[PartRevision, ...] = ()
    supersessions: tuple[Supersession, ...] = ()
    interchangeability_group_ref: TypedId | None = None
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.created_at, field_name="created_at")
        if self.part_id.entity_type != "part":
            raise ValueError(
                f"part_id deve ter entity_type 'part', recebido '{self.part_id.entity_type}'."
            )
        if (
            self.interchangeability_group_ref is not None
            and self.interchangeability_group_ref.entity_type != "interchangeability_group"
        ):
            raise ValueError(
                "interchangeability_group_ref deve ter entity_type 'interchangeability_group', "
                f"recebido '{self.interchangeability_group_ref.entity_type}'."
            )
        seen_codes: set[str] = set()
        for revision in self.revisions:
            if revision.revision_code in seen_codes:
                raise ValueError(f"revision_code '{revision.revision_code}' duplicado neste Part.")
            seen_codes.add(revision.revision_code)
        self._require_acyclic(self.supersessions)

    def _revision_ids(self) -> frozenset[TypedId]:
        return frozenset(revision.revision_id for revision in self.revisions)

    @staticmethod
    def _require_acyclic(supersessions: tuple[Supersession, ...]) -> None:
        """Alcançabilidade: um ciclo existe sse alguma revisão alcança a si
        mesma seguindo arestas predecessor->successor."""
        graph: dict[TypedId, list[TypedId]] = {}
        for edge in supersessions:
            graph.setdefault(edge.predecessor_revision_id, []).append(edge.successor_revision_id)

        for start in graph:
            visited: set[TypedId] = set()
            stack = list(graph.get(start, ()))
            while stack:
                current = stack.pop()
                if current == start:
                    raise SupersessaoCiclica(
                        f"Registrar essa supersessão fecharia um ciclo envolvendo a revisão "
                        f"'{start.value}'."
                    )
                if current in visited:
                    continue
                visited.add(current)
                stack.extend(graph.get(current, ()))

    def add_revision(self, revision: PartRevision) -> "Part":
        if revision.revision_id in self._revision_ids():
            raise ValueError(f"Revisão '{revision.revision_id.value}' já existe neste Part.")
        return replace(self, revisions=self.revisions + (revision,), version=self.version + 1)

    def _get_revision(self, revision_id: TypedId) -> PartRevision:
        for revision in self.revisions:
            if revision.revision_id == revision_id:
                return revision
        raise RevisaoNaoEncontrada(f"Revisão '{revision_id.value}' não encontrada neste Part.")

    def supersede_revision(
        self, *, predecessor_revision_id: TypedId, successor_revision_id: TypedId, reason: str
    ) -> "Part":
        """I‑PRT‑1: grafo acíclico. A revisão predecessora vira `SUPERSEDED`; a
        sucessora não muda de estado aqui (pode já estar `ACTIVE` de `add_revision`).
        Instalações históricas (`ConfigurationBaseline` de outros veículos) **não**
        são tocadas — isso é responsabilidade de quem lê, não deste método.
        """
        self._get_revision(predecessor_revision_id)
        self._get_revision(successor_revision_id)
        new_edge = Supersession(
            predecessor_revision_id=predecessor_revision_id,
            successor_revision_id=successor_revision_id,
            reason=reason,
        )
        candidate_supersessions = self.supersessions + (new_edge,)
        self._require_acyclic(candidate_supersessions)

        updated_revisions = tuple(
            replace(revision, lifecycle_state=PartLifecycleState.SUPERSEDED)
            if revision.revision_id == predecessor_revision_id
            else revision
            for revision in self.revisions
        )
        return replace(
            self,
            revisions=updated_revisions,
            supersessions=candidate_supersessions,
            version=self.version + 1,
        )

    def join_interchangeability_group(self, group_ref: TypedId) -> "Part":
        if group_ref.entity_type != "interchangeability_group":
            raise ValueError(
                "group_ref deve ter entity_type 'interchangeability_group', recebido "
                f"'{group_ref.entity_type}'."
            )
        return replace(self, interchangeability_group_ref=group_ref, version=self.version + 1)


@dataclass(frozen=True, slots=True)
class InterchangeabilityGroup:
    """`05_DOMAIN_MODEL.md` §1.6. Pertencer ao grupo é simétrico por construção:
    a pertinência não distingue "de quem para quem" — qualquer membro consultado
    enxerga todos os outros (I‑PRT‑2)."""

    group_id: TypedId
    organization_id: OrganizationId
    member_part_revisions: tuple[TypedId, ...] = ()
    version: int = 1

    def __post_init__(self) -> None:
        if self.group_id.entity_type != "interchangeability_group":
            raise ValueError(
                "group_id deve ter entity_type 'interchangeability_group', recebido "
                f"'{self.group_id.entity_type}'."
            )
        for member in self.member_part_revisions:
            if member.entity_type != "part_revision":
                raise ValueError(
                    "member_part_revisions deve conter apenas TypedId de "
                    f"entity_type 'part_revision', recebido '{member.entity_type}'."
                )
        if len(set(self.member_part_revisions)) != len(self.member_part_revisions):
            raise ValueError("member_part_revisions não pode repetir a mesma revisão.")

    def add_member(self, revision_ref: TypedId) -> "InterchangeabilityGroup":
        if revision_ref in self.member_part_revisions:
            raise ValueError(f"Revisão '{revision_ref.value}' já é membro do grupo.")
        return replace(
            self,
            member_part_revisions=self.member_part_revisions + (revision_ref,),
            version=self.version + 1,
        )

    def remove_member(self, revision_ref: TypedId) -> "InterchangeabilityGroup":
        if revision_ref not in self.member_part_revisions:
            raise KeyError(f"Revisão '{revision_ref.value}' não é membro do grupo.")
        return replace(
            self,
            member_part_revisions=tuple(
                member for member in self.member_part_revisions if member != revision_ref
            ),
            version=self.version + 1,
        )

    def interchanges_with(self, revision_ref: TypedId) -> tuple[TypedId, ...]:
        """Substitutos de `revision_ref` dentro do grupo — simétrico por
        construção: se X está no resultado de Y, Y está no resultado de X."""
        if revision_ref not in self.member_part_revisions:
            raise KeyError(f"Revisão '{revision_ref.value}' não é membro do grupo.")
        return tuple(member for member in self.member_part_revisions if member != revision_ref)
