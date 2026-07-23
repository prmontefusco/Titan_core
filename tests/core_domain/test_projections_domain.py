"""Testes unitários das projeções reconstruíveis (Passo 7.2)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_domain.projections import (
    ReferenceRole,
    ReferencingKind,
    ReverseReference,
    compute_projection_digest,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _entry(
    org_id: OrganizationId,
    referenced: UniversalReference,
    referencing_id: TypedId,
    role: ReferenceRole = ReferenceRole.AGGREGATE,
    kind: ReferencingKind = ReferencingKind.DOMAIN_EVENT,
    occurred_at: datetime | None = None,
) -> ReverseReference:
    return ReverseReference(
        organization_id=org_id,
        referenced=referenced,
        referencing_kind=kind,
        referencing_id=referencing_id,
        role=role,
        occurred_at=occurred_at or datetime.now(UTC),
    )


def _ref(org_id: OrganizationId | None) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new("subject"), organization_id=org_id, contract_version=1
    )


def test_projection_never_crosses_organizations() -> None:
    org_id = OrganizationId.new()
    outra_org = OrganizationId.new()
    with pytest.raises(ValueError, match="não atravessa Organizations"):
        _entry(org_id, _ref(outra_org), TypedId.new("domain_event"))


def test_digest_is_order_independent() -> None:
    org_id = OrganizationId.new()
    a = _entry(org_id, _ref(org_id), TypedId.new("domain_event"))
    b = _entry(org_id, _ref(org_id), TypedId.new("domain_event"), role=ReferenceRole.ACTOR)
    c = _entry(org_id, _ref(org_id), TypedId.new("relation"), kind=ReferencingKind.RELATION)

    assert compute_projection_digest([a, b, c]) == compute_projection_digest([c, a, b])


def test_digest_ignores_rebuild_instant_but_not_content() -> None:
    org_id = OrganizationId.new()
    referenced = _ref(org_id)
    event_id = TypedId.new("domain_event")
    t0 = datetime.now(UTC)

    cedo = _entry(org_id, referenced, event_id, occurred_at=t0)
    tarde = _entry(org_id, referenced, event_id, occurred_at=t0 + timedelta(days=1))

    # O instante descreve a execução, não o conteúdo derivado.
    assert compute_projection_digest([cedo]) == compute_projection_digest([tarde])

    # O papel faz parte do conteúdo.
    outro_papel = _entry(org_id, referenced, event_id, role=ReferenceRole.ACTOR)
    assert compute_projection_digest([cedo]) != compute_projection_digest([outro_papel])


def test_empty_projection_has_stable_digest() -> None:
    assert compute_projection_digest([]) == compute_projection_digest([])


def test_sort_key_gives_total_stable_order() -> None:
    org_id = OrganizationId.new()
    entries = [
        _entry(org_id, _ref(org_id), TypedId.new("domain_event")),
        _entry(org_id, _ref(org_id), TypedId.new("relation"), kind=ReferencingKind.RELATION),
        _entry(org_id, _ref(org_id), TypedId.new("domain_event"), role=ReferenceRole.SOURCE),
    ]
    uma = sorted(entries, key=lambda e: e.sort_key())
    outra = sorted(reversed(entries), key=lambda e: e.sort_key())
    assert [e.sort_key() for e in uma] == [e.sort_key() for e in outra]


def test_entry_is_immutable() -> None:
    org_id = OrganizationId.new()
    entry = _entry(org_id, _ref(org_id), TypedId.new("domain_event"))
    with pytest.raises(AttributeError):
        entry.role = ReferenceRole.ACTOR  # type: ignore[misc]
