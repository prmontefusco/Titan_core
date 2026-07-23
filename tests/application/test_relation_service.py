"""Testes de aplicação para o RelationService com repositório simulado (Passo 7.1)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_application.relation_service import (
    CrossOrganizationTraversalDenied,
    RelationService,
)
from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier
from packages.core_domain.relations import UniversalRelation
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class InMemoryRelationRepository:
    def __init__(self) -> None:
        self.relations: dict[TypedId, UniversalRelation] = {}

    def save(self, relation: UniversalRelation) -> None:
        self.relations[relation.relation_id] = relation

    def get_by_id(self, relation_id: TypedId) -> UniversalRelation | None:
        return self.relations.get(relation_id)

    def list_outgoing(
        self,
        organization_id: OrganizationId,
        source_id: TypedId,
        at_time: datetime | None = None,
    ) -> list[UniversalRelation]:
        return self._filter(
            lambda r: r.source_reference.target_id == source_id, organization_id, at_time
        )

    def list_incoming(
        self,
        organization_id: OrganizationId,
        target_id: TypedId,
        at_time: datetime | None = None,
    ) -> list[UniversalRelation]:
        return self._filter(
            lambda r: r.target_reference.target_id == target_id, organization_id, at_time
        )

    def _filter(
        self,
        matches: object,
        organization_id: OrganizationId,
        at_time: datetime | None,
    ) -> list[UniversalRelation]:
        found = []
        for relation in self.relations.values():
            if relation.organization_id != organization_id:
                continue
            if not matches(relation):  # type: ignore[operator]
                continue
            if at_time is not None and not relation.is_valid_at(at_time):
                continue
            found.append(relation)
        return found


def _ref(org_id: OrganizationId, entity_type: str = "subject") -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new(entity_type), organization_id=org_id, contract_version=1
    )


def _service() -> tuple[RelationService, InMemoryRelationRepository]:
    repo = InMemoryRelationRepository()
    return RelationService(repository=repo), repo


def test_temporal_query_returns_only_relations_valid_at_instant() -> None:
    service, _ = _service()
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    origem = _ref(org_id)
    confianca = ConfidenceLevel(tier=ConfidenceTier.DOCUMENTED, reason="Documento anexado.")

    antiga = UniversalRelation.create(
        organization_id=org_id,
        source_reference=origem,
        target_reference=_ref(org_id),
        relation_type="composicao",
        created_at=t0,
        confidence=confianca,
        valid_from=t0,
        valid_until=t0 + timedelta(days=10),
    )
    atual = UniversalRelation.create(
        organization_id=org_id,
        source_reference=origem,
        target_reference=_ref(org_id),
        relation_type="composicao",
        created_at=t0,
        confidence=confianca,
        valid_from=t0 + timedelta(days=11),
    )
    service.register_relation(antiga)
    service.register_relation(atual)

    no_inicio = service.list_outgoing_at(org_id, origem, t0 + timedelta(days=5))
    assert [r.relation_id for r in no_inicio] == [antiga.relation_id]

    depois = service.list_outgoing_at(org_id, origem, t0 + timedelta(days=20))
    assert [r.relation_id for r in depois] == [atual.relation_id]

    # Sem instante, a consulta devolve o histórico completo.
    assert len(service.list_outgoing_at(org_id, origem)) == 2


def test_traversal_into_another_organization_is_denied() -> None:
    service, _ = _service()
    org_id = OrganizationId.new()
    outra_org = OrganizationId.new()

    with pytest.raises(CrossOrganizationTraversalDenied):
        service.list_outgoing_at(org_id, _ref(outra_org))

    with pytest.raises(CrossOrganizationTraversalDenied):
        service.list_incoming_at(org_id, _ref(outra_org))


def test_closing_relation_keeps_it_queryable_in_the_past() -> None:
    service, _ = _service()
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    origem = _ref(org_id)

    relation = service.register_relation(
        UniversalRelation.create(
            organization_id=org_id,
            source_reference=origem,
            target_reference=_ref(org_id),
            relation_type="posse",
            created_at=t0,
            confidence=ConfidenceLevel(tier=ConfidenceTier.INFORMED, reason="Declarada."),
            valid_from=t0,
        )
    )

    service.close_relation(relation.relation_id, t0 + timedelta(days=7))

    assert service.list_outgoing_at(org_id, origem, t0 + timedelta(days=3))
    assert not service.list_outgoing_at(org_id, origem, t0 + timedelta(days=8))


def test_closing_unknown_relation_fails() -> None:
    service, _ = _service()
    with pytest.raises(KeyError, match="não encontrada"):
        service.close_relation(TypedId.new("relation"), datetime.now(UTC))
