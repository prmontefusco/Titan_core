"""Testes de aplicação para a navegação de Recall (Passo 7.4)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_application.recall_service import RecallService
from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier
from packages.core_domain.recall import (
    RecallDirection,
    RecallLimitReason,
    RecallMode,
    RecallRequest,
    RecallStatus,
)
from packages.core_domain.relations import UniversalRelation
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

CONFIANCA = ConfidenceLevel(tier=ConfidenceTier.DOCUMENTED, reason="Documento anexado.")


class GrafoEmMemoria:
    """Repositório de relações simulado, suficiente para exercitar a travessia."""

    def __init__(self) -> None:
        self.relations: list[UniversalRelation] = []

    def save(self, relation: UniversalRelation) -> None:
        self.relations.append(relation)

    def get_by_id(self, relation_id: TypedId) -> UniversalRelation | None:
        return next((r for r in self.relations if r.relation_id == relation_id), None)

    def list_outgoing(
        self,
        organization_id: OrganizationId,
        source_id: TypedId,
        at_time: datetime | None = None,
    ) -> list[UniversalRelation]:
        return [
            r
            for r in self.relations
            if r.organization_id == organization_id
            and r.source_reference.target_id == source_id
            and (at_time is None or r.is_valid_at(at_time))
        ]

    def list_incoming(
        self,
        organization_id: OrganizationId,
        target_id: TypedId,
        at_time: datetime | None = None,
    ) -> list[UniversalRelation]:
        return [
            r
            for r in self.relations
            if r.organization_id == organization_id
            and r.target_reference.target_id == target_id
            and (at_time is None or r.is_valid_at(at_time))
        ]


class DecisoesEmMemoria:
    def __init__(self, por_sujeito: dict[TypedId, list[TypedId]]) -> None:
        self.por_sujeito = por_sujeito

    def list_decision_ids_for_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[TypedId]:
        return list(self.por_sujeito.get(subject_id, []))


def _ref(org_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new("subject"), organization_id=org_id, contract_version=1
    )


def _ligar(
    grafo: GrafoEmMemoria,
    org_id: OrganizationId,
    origem: UniversalReference,
    destino: UniversalReference,
    at: datetime,
    tipo: str = "transformacao",
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
) -> UniversalRelation:
    relacao = UniversalRelation.create(
        organization_id=org_id,
        source_reference=origem,
        target_reference=destino,
        relation_type=tipo,
        created_at=at,
        confidence=CONFIANCA,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    grafo.save(relacao)
    return relacao


def _cadeia(
    org_id: OrganizationId, at: datetime, tamanho: int
) -> tuple[GrafoEmMemoria, list[UniversalReference]]:
    """Monta A → B → C → ... e devolve o grafo com os nós."""
    grafo = GrafoEmMemoria()
    nos = [_ref(org_id) for _ in range(tamanho)]
    for anterior, proximo in zip(nos, nos[1:], strict=False):
        _ligar(grafo, org_id, anterior, proximo, at)
    return grafo, nos


def test_prospective_navigation_finds_destinations() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    grafo, nos = _cadeia(org_id, t0, 4)

    resultado = RecallService(relations=grafo).execute(
        RecallRequest(
            organization_id=org_id,
            subject_reference=nos[0],
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
        )
    )

    alcancados = resultado.affected_subjects()
    assert nos[1] in alcancados and nos[2] in alcancados and nos[3] in alcancados
    assert resultado.status is RecallStatus.CONCLUSIVO


def test_retrospective_navigation_finds_origin() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    grafo, nos = _cadeia(org_id, t0, 4)

    resultado = RecallService(relations=grafo).execute(
        RecallRequest(
            organization_id=org_id,
            subject_reference=nos[3],
            direction=RecallDirection.RETROSPECTIVA,
            mode=RecallMode.SIMULACAO,
        )
    )

    assert nos[0] in resultado.affected_subjects()


def test_every_reached_subject_has_an_explainable_path() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    grafo, nos = _cadeia(org_id, t0, 3)

    resultado = RecallService(relations=grafo).execute(
        RecallRequest(
            organization_id=org_id,
            subject_reference=nos[0],
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
        )
    )

    for alcancado in resultado.affected_subjects():
        caminhos = resultado.paths_to(alcancado)
        assert caminhos
        assert "transformacao" in caminhos[0].explain()


def test_depth_limit_is_declared_as_a_gap() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    grafo, nos = _cadeia(org_id, t0, 5)

    resultado = RecallService(relations=grafo).execute(
        RecallRequest(
            organization_id=org_id,
            subject_reference=nos[0],
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
            max_depth=2,
        )
    )

    # Parou no limite, mas havia mais grafo: isso é lacuna, não conclusão.
    assert resultado.status is RecallStatus.INCONCLUSIVO
    assert any(g.reason is RecallLimitReason.PROFUNDIDADE_MAXIMA for g in resultado.gaps)
    assert nos[4] not in resultado.affected_subjects()


def test_cycle_is_detected_and_declared() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    grafo, nos = _cadeia(org_id, t0, 3)
    _ligar(grafo, org_id, nos[2], nos[0], t0)  # fecha o ciclo

    resultado = RecallService(relations=grafo).execute(
        RecallRequest(
            organization_id=org_id,
            subject_reference=nos[0],
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
            max_depth=10,
        )
    )

    assert any(g.reason is RecallLimitReason.CICLO_DETECTADO for g in resultado.gaps)
    assert resultado.status is RecallStatus.INCONCLUSIVO


def test_node_limit_stops_and_declares_gap() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    grafo, nos = _cadeia(org_id, t0, 6)

    resultado = RecallService(relations=grafo).execute(
        RecallRequest(
            organization_id=org_id,
            subject_reference=nos[0],
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
            max_depth=10,
            max_nodes=3,
        )
    )

    assert any(g.reason is RecallLimitReason.LIMITE_DE_NOS for g in resultado.gaps)
    assert not resultado.is_conclusive


def test_temporal_window_changes_the_reachable_graph() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    grafo = GrafoEmMemoria()
    a, b, c = _ref(org_id), _ref(org_id), _ref(org_id)

    _ligar(grafo, org_id, a, b, t0, valid_from=t0, valid_until=t0 + timedelta(days=10))
    _ligar(grafo, org_id, b, c, t0, valid_from=t0 + timedelta(days=20))

    service = RecallService(relations=grafo)

    cedo = service.execute(
        RecallRequest(
            organization_id=org_id,
            subject_reference=a,
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
            at_time=t0 + timedelta(days=5),
        )
    )
    assert b in cedo.affected_subjects()
    assert c not in cedo.affected_subjects()

    tarde = service.execute(
        RecallRequest(
            organization_id=org_id,
            subject_reference=a,
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
            at_time=t0 + timedelta(days=25),
        )
    )
    # A primeira aresta já expirou: nada é alcançado a partir de A.
    assert tarde.affected_subjects() == ()


def test_relation_type_filter_restricts_traversal() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    grafo = GrafoEmMemoria()
    a, b, c = _ref(org_id), _ref(org_id), _ref(org_id)
    _ligar(grafo, org_id, a, b, t0, tipo="transformacao")
    _ligar(grafo, org_id, a, c, t0, tipo="posse")

    resultado = RecallService(relations=grafo).execute(
        RecallRequest(
            organization_id=org_id,
            subject_reference=a,
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
            relation_types=("transformacao",),
        )
    )

    assert b in resultado.affected_subjects()
    assert c not in resultado.affected_subjects()


def test_affected_decisions_are_located() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    grafo, nos = _cadeia(org_id, t0, 3)
    decisao = TypedId.new("decision")

    resultado = RecallService(
        relations=grafo,
        decisions=DecisoesEmMemoria({nos[2].target_id: [decisao]}),
    ).execute(
        RecallRequest(
            organization_id=org_id,
            subject_reference=nos[0],
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
        )
    )

    assert decisao in resultado.affected_decision_ids


def test_recall_never_crosses_organizations() -> None:
    org_id = OrganizationId.new()
    outra_org = OrganizationId.new()

    with pytest.raises(ValueError, match="não atravessa fronteira de tenant"):
        RecallRequest(
            organization_id=org_id,
            subject_reference=_ref(outra_org),
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
        )


def test_incident_mode_requires_auditable_registry() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    grafo, nos = _cadeia(org_id, t0, 2)

    with pytest.raises(RuntimeError, match="exige repositório para registro auditável"):
        RecallService(relations=grafo).execute(
            RecallRequest(
                organization_id=org_id,
                subject_reference=nos[0],
                direction=RecallDirection.PROSPECTIVA,
                mode=RecallMode.INCIDENTE,
            )
        )


def test_traversal_is_deterministic() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    grafo, nos = _cadeia(org_id, t0, 4)
    pedido = RecallRequest(
        organization_id=org_id,
        subject_reference=nos[0],
        direction=RecallDirection.PROSPECTIVA,
        mode=RecallMode.SIMULACAO,
    )
    service = RecallService(relations=grafo)

    um = service.execute(pedido)
    outro = service.execute(pedido)

    assert [p.explain() for p in um.paths] == [p.explain() for p in outro.paths]
