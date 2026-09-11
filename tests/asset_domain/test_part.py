"""Testes unitários de domínio para `Part` e `InterchangeabilityGroup` (A2).

Cobre I‑PRT‑1 (supersessão acíclica) e I‑PRT‑2 (intercambiabilidade simétrica).
`docs/asset/07_INVARIANTS.md`.
"""

from uuid import uuid4

import pytest

from packages.asset_domain.part import (
    InterchangeabilityGroup,
    Part,
    PartIdentity,
    PartLifecycleState,
    PartRevision,
    RevisaoNaoEncontrada,
    SupersessaoCiclica,
)
from packages.shared_kernel import OrganizationId, TypedId


def _identity(**overrides: object) -> PartIdentity:
    defaults: dict[str, object] = dict(
        part_number="PN-0001", description="Freio a disco", manufacturer="Acme"
    )
    defaults.update(overrides)
    return PartIdentity(**defaults)  # type: ignore[arg-type]


def _part(**overrides: object) -> Part:
    defaults: dict[str, object] = dict(
        part_id=TypedId.new("part"),
        organization_id=OrganizationId(uuid4()),
        identity=_identity(),
    )
    defaults.update(overrides)
    return Part(**defaults)  # type: ignore[arg-type]


def _revision(code: str) -> PartRevision:
    return PartRevision(revision_id=TypedId.new("part_revision"), revision_code=code)


def test_part_number_cannot_be_blank() -> None:
    with pytest.raises(ValueError, match="part_number não pode ser vazio"):
        _identity(part_number="  ")


def test_add_revision_appends_and_versions() -> None:
    part = _part()
    revision = _revision("R1")
    updated = part.add_revision(revision)
    assert updated.revisions == (revision,)
    assert updated.version == part.version + 1


def test_add_revision_rejects_duplicate_code_on_construction() -> None:
    with pytest.raises(ValueError, match="duplicado"):
        _part(
            revisions=(
                PartRevision(revision_id=TypedId.new("part_revision"), revision_code="R1"),
                PartRevision(revision_id=TypedId.new("part_revision"), revision_code="R1"),
            )
        )


# --- I-PRT-1 --------------------------------------------------------------------


def test_supersede_revision_marks_predecessor_superseded() -> None:
    r1, r2 = _revision("R1"), _revision("R2")
    part = _part().add_revision(r1).add_revision(r2)

    superseded = part.supersede_revision(
        predecessor_revision_id=r1.revision_id,
        successor_revision_id=r2.revision_id,
        reason="Peça descontinuada pelo fabricante.",
    )

    predecessor = next(r for r in superseded.revisions if r.revision_id == r1.revision_id)
    successor = next(r for r in superseded.revisions if r.revision_id == r2.revision_id)
    assert predecessor.lifecycle_state is PartLifecycleState.SUPERSEDED
    assert successor.lifecycle_state is PartLifecycleState.ACTIVE
    assert len(superseded.supersessions) == 1


def test_supersede_revision_rejects_unknown_revision() -> None:
    part = _part().add_revision(_revision("R1"))
    with pytest.raises(RevisaoNaoEncontrada):
        part.supersede_revision(
            predecessor_revision_id=TypedId.new("part_revision"),
            successor_revision_id=part.revisions[0].revision_id,
            reason="motivo",
        )


def test_supersede_revision_rejects_self_supersession() -> None:
    r1 = _revision("R1")
    part = _part().add_revision(r1)
    with pytest.raises(ValueError, match="não pode superseder a si mesma"):
        part.supersede_revision(
            predecessor_revision_id=r1.revision_id,
            successor_revision_id=r1.revision_id,
            reason="motivo",
        )


def test_supersede_revision_rejects_direct_cycle() -> None:
    r1, r2 = _revision("R1"), _revision("R2")
    part = (
        _part()
        .add_revision(r1)
        .add_revision(r2)
        .supersede_revision(
            predecessor_revision_id=r1.revision_id,
            successor_revision_id=r2.revision_id,
            reason="R2 substitui R1.",
        )
    )
    with pytest.raises(SupersessaoCiclica):
        # R2 -> R1 fecharia o ciclo R1 -> R2 -> R1.
        part.supersede_revision(
            predecessor_revision_id=r2.revision_id,
            successor_revision_id=r1.revision_id,
            reason="tentativa de reverter",
        )


def test_supersede_revision_rejects_transitive_cycle() -> None:
    r1, r2, r3 = _revision("R1"), _revision("R2"), _revision("R3")
    part = (
        _part()
        .add_revision(r1)
        .add_revision(r2)
        .add_revision(r3)
        .supersede_revision(
            predecessor_revision_id=r1.revision_id,
            successor_revision_id=r2.revision_id,
            reason="R2 substitui R1.",
        )
        .supersede_revision(
            predecessor_revision_id=r2.revision_id,
            successor_revision_id=r3.revision_id,
            reason="R3 substitui R2.",
        )
    )
    with pytest.raises(SupersessaoCiclica):
        # R3 -> R1 fecharia o ciclo R1 -> R2 -> R3 -> R1.
        part.supersede_revision(
            predecessor_revision_id=r3.revision_id,
            successor_revision_id=r1.revision_id,
            reason="tentativa de reverter",
        )


def test_historical_installation_is_not_the_concern_of_supersede() -> None:
    """I-PRT-1: supersessão não apaga nem reescreve o passado — este agregado só
    garante o grafo acíclico; preservação de baseline histórica é de quem lê."""
    r1, r2 = _revision("R1"), _revision("R2")
    part = _part().add_revision(r1).add_revision(r2)
    superseded = part.supersede_revision(
        predecessor_revision_id=r1.revision_id,
        successor_revision_id=r2.revision_id,
        reason="motivo",
    )
    # A revisão superseded continua existindo e consultável — nada foi apagado.
    assert any(r.revision_id == r1.revision_id for r in superseded.revisions)


# --- I-PRT-2 --------------------------------------------------------------------


def test_interchangeability_group_membership_is_symmetric() -> None:
    r1 = TypedId.new("part_revision")
    r2 = TypedId.new("part_revision")
    r3 = TypedId.new("part_revision")
    group = InterchangeabilityGroup(
        group_id=TypedId.new("interchangeability_group"),
        organization_id=OrganizationId(uuid4()),
        member_part_revisions=(r1, r2, r3),
    )

    assert set(group.interchanges_with(r1)) == {r2, r3}
    assert r1 in group.interchanges_with(r2)
    assert r1 in group.interchanges_with(r3)


def test_add_member_rejects_duplicate() -> None:
    r1 = TypedId.new("part_revision")
    group = InterchangeabilityGroup(
        group_id=TypedId.new("interchangeability_group"),
        organization_id=OrganizationId(uuid4()),
        member_part_revisions=(r1,),
    )
    with pytest.raises(ValueError, match="já é membro"):
        group.add_member(r1)


def test_remove_member_updates_symmetry() -> None:
    r1 = TypedId.new("part_revision")
    r2 = TypedId.new("part_revision")
    group = InterchangeabilityGroup(
        group_id=TypedId.new("interchangeability_group"),
        organization_id=OrganizationId(uuid4()),
        member_part_revisions=(r1, r2),
    )
    updated = group.remove_member(r2)
    assert updated.interchanges_with(r1) == ()


def test_interchanges_with_rejects_non_member() -> None:
    group = InterchangeabilityGroup(
        group_id=TypedId.new("interchangeability_group"),
        organization_id=OrganizationId(uuid4()),
    )
    with pytest.raises(KeyError):
        group.interchanges_with(TypedId.new("part_revision"))
