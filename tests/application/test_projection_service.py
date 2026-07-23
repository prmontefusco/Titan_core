"""Testes de aplicação para a reconstrução de projeções (Passo 7.2)."""

from datetime import UTC, datetime

import pytest

from packages.core_application.projection_service import ProjectionRebuildService
from packages.core_domain.projections import (
    ReferenceRole,
    ReferencingKind,
    ReverseReference,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class FakeSource:
    """Fonte imutável simulada: eventos e relações já registrados."""

    def __init__(self, events: list[ReverseReference], relations: list[ReverseReference]) -> None:
        self.events = events
        self.relations = relations
        self.leituras = 0

    def read_event_references(self, organization_id: OrganizationId) -> list[ReverseReference]:
        self.leituras += 1
        return [e for e in self.events if e.organization_id == organization_id]

    def read_relation_references(self, organization_id: OrganizationId) -> list[ReverseReference]:
        return [e for e in self.relations if e.organization_id == organization_id]


class InMemoryProjectionRepository:
    def __init__(self) -> None:
        self.rows: dict[OrganizationId, list[ReverseReference]] = {}

    def replace_all(self, organization_id: OrganizationId, entries: list[ReverseReference]) -> None:
        self.rows[organization_id] = list(entries)

    def clear(self, organization_id: OrganizationId) -> None:
        self.rows.pop(organization_id, None)

    def list_all(self, organization_id: OrganizationId) -> list[ReverseReference]:
        return list(self.rows.get(organization_id, []))

    def list_referencing(
        self, organization_id: OrganizationId, referenced: UniversalReference
    ) -> list[ReverseReference]:
        return [
            e
            for e in self.rows.get(organization_id, [])
            if e.referenced.target_id == referenced.target_id
        ]


def _ref(org_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new("subject"), organization_id=org_id, contract_version=1
    )


def _build(
    org_id: OrganizationId,
) -> tuple[ProjectionRebuildService, FakeSource, InMemoryProjectionRepository, UniversalReference]:
    now = datetime.now(UTC)
    alvo = _ref(org_id)
    evento = ReverseReference(
        organization_id=org_id,
        referenced=alvo,
        referencing_kind=ReferencingKind.DOMAIN_EVENT,
        referencing_id=TypedId.new("domain_event"),
        role=ReferenceRole.AGGREGATE,
        occurred_at=now,
    )
    relacao = ReverseReference(
        organization_id=org_id,
        referenced=alvo,
        referencing_kind=ReferencingKind.RELATION,
        referencing_id=TypedId.new("relation"),
        role=ReferenceRole.RELATION_TARGET,
        occurred_at=now,
    )
    source = FakeSource(events=[evento], relations=[relacao])
    repo = InMemoryProjectionRepository()
    return ProjectionRebuildService(source=source, repository=repo), source, repo, alvo


def test_rebuild_is_idempotent_and_reproducible() -> None:
    org_id = OrganizationId.new()
    service, _, _, _ = _build(org_id)

    primeiro = service.rebuild(org_id)
    segundo = service.rebuild(org_id)

    assert primeiro == segundo
    assert service.current_digest(org_id) == primeiro


def test_projection_can_be_discarded_and_rebuilt_identically() -> None:
    org_id = OrganizationId.new()
    service, source, repo, _ = _build(org_id)

    original = service.rebuild(org_id)

    # Apaga somente a projeção; a fonte permanece intacta.
    repo.clear(org_id)
    assert repo.list_all(org_id) == []
    assert len(source.events) == 1
    assert len(source.relations) == 1

    reconstruido = service.rebuild(org_id)
    assert reconstruido == original


def test_projection_detects_divergence_from_sources() -> None:
    org_id = OrganizationId.new()
    service, source, _, alvo = _build(org_id)
    service.rebuild(org_id)
    assert service.is_consistent_with_sources(org_id)

    # Um novo evento chega e a projeção fica defasada até ser reconstruída.
    source.events.append(
        ReverseReference(
            organization_id=org_id,
            referenced=alvo,
            referencing_kind=ReferencingKind.DOMAIN_EVENT,
            referencing_id=TypedId.new("domain_event"),
            role=ReferenceRole.ACTOR,
            occurred_at=datetime.now(UTC),
        )
    )
    assert not service.is_consistent_with_sources(org_id)

    service.rebuild(org_id)
    assert service.is_consistent_with_sources(org_id)


def test_derived_content_does_not_depend_on_read_order() -> None:
    org_id = OrganizationId.new()
    service, source, _, _ = _build(org_id)

    direto = [e.sort_key() for e in service.derive(org_id)]
    source.events.reverse()
    source.relations.reverse()
    invertido = [e.sort_key() for e in service.derive(org_id)]

    assert direto == invertido


def test_reverse_lookup_returns_every_referencing_record() -> None:
    org_id = OrganizationId.new()
    service, _, _, alvo = _build(org_id)
    service.rebuild(org_id)

    encontrados = service.list_referencing(org_id, alvo)
    assert {e.referencing_kind for e in encontrados} == {
        ReferencingKind.DOMAIN_EVENT,
        ReferencingKind.RELATION,
    }


def test_lookup_into_another_organization_is_rejected() -> None:
    org_id = OrganizationId.new()
    outra_org = OrganizationId.new()
    service, _, _, _ = _build(org_id)

    with pytest.raises(ValueError, match="não atravessa Organizations"):
        service.list_referencing(org_id, _ref(outra_org))


def test_empty_organization_rebuilds_to_empty_projection() -> None:
    org_id = OrganizationId.new()
    vazia = OrganizationId.new()
    service, _, repo, _ = _build(org_id)

    digest = service.rebuild(vazia)
    assert repo.list_all(vazia) == []
    assert digest == service.current_digest(vazia)
