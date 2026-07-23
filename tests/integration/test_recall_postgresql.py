"""Integração PostgreSQL para Recall sobre grafo fictício genérico (Passo 7.4)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.recall_service import RecallService
from packages.core_application.relation_service import RelationService
from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier
from packages.core_domain.recall import (
    RecallDirection,
    RecallLimitReason,
    RecallMode,
    RecallRequest,
    RecallStatus,
)
from packages.core_domain.relations import UniversalRelation
from packages.core_infrastructure.persistence.recall import (
    PostgresAffectedDecisionLookup,
    TransactionalRecallRepository,
)
from packages.core_infrastructure.persistence.relations import TransactionalRelationRepository
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

CONFIANCA = ConfidenceLevel(tier=ConfidenceTier.DOCUMENTED, reason="Documento anexado.")


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        with conn.begin():
            yield conn


def _ref(org_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new("subject"), organization_id=org_id, contract_version=1
    )


def test_recall_over_fictional_graph(db_connection: Connection) -> None:
    org_id_1 = OrganizationId.new()
    org_id_2 = OrganizationId.new()
    t0 = datetime.now(UTC)

    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations
            (organization_id, record_owner_organization_id)
            VALUES (:id1, :id1), (:id2, :id2)
            """
        ),
        {"id1": org_id_1.value, "id2": org_id_2.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_1.value)},
    )

    relation_service = RelationService(
        repository=TransactionalRelationRepository(connection=db_connection)
    )
    recall_repo = TransactionalRecallRepository(connection=db_connection)
    service = RecallService(
        relations=TransactionalRelationRepository(connection=db_connection),
        decisions=PostgresAffectedDecisionLookup(connection=db_connection),
        result_repository=recall_repo,
    )

    # Grafo fictício genérico: origem → intermediario → destino
    origem, intermediario, destino = _ref(org_id_1), _ref(org_id_1), _ref(org_id_1)
    for de, para in ((origem, intermediario), (intermediario, destino)):
        relation_service.register_relation(
            UniversalRelation.create(
                organization_id=org_id_1,
                source_reference=de,
                target_reference=para,
                relation_type="transformacao",
                created_at=t0,
                confidence=CONFIANCA,
                valid_from=t0,
            )
        )

    # 1. Prospectivo: encontrar os destinos a partir da origem.
    prospectivo = service.execute(
        RecallRequest(
            organization_id=org_id_1,
            subject_reference=origem,
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
        )
    )
    alcancados = prospectivo.affected_subjects()
    assert intermediario in alcancados and destino in alcancados
    assert prospectivo.status is RecallStatus.CONCLUSIVO

    # 2. Cada caminho é explicável.
    for alcancado in alcancados:
        caminhos = prospectivo.paths_to(alcancado)
        assert caminhos and "transformacao" in caminhos[0].explain()

    # 3. Retrospectivo: encontrar a origem a partir do destino.
    retrospectivo = service.execute(
        RecallRequest(
            organization_id=org_id_1,
            subject_reference=destino,
            direction=RecallDirection.RETROSPECTIVA,
            mode=RecallMode.SIMULACAO,
        )
    )
    assert origem in retrospectivo.affected_subjects()

    # 4. Lacuna vira resultado inconclusivo, nunca silêncio.
    limitado = service.execute(
        RecallRequest(
            organization_id=org_id_1,
            subject_reference=origem,
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
            max_depth=1,
        )
    )
    assert limitado.status is RecallStatus.INCONCLUSIVO
    assert any(g.reason is RecallLimitReason.PROFUNDIDADE_MAXIMA for g in limitado.gaps)
    assert limitado.explain_gaps()

    # 5. Incidente fica registrado e é recuperável na íntegra.
    incidente = service.execute(
        RecallRequest(
            organization_id=org_id_1,
            subject_reference=origem,
            direction=RecallDirection.AMBAS,
            mode=RecallMode.INCIDENTE,
        )
    )
    recuperado = recall_repo.get_by_id(incidente.recall_id)
    assert recuperado is not None
    assert recuperado.status is incidente.status
    assert [p.explain() for p in recuperado.paths] == [p.explain() for p in incidente.paths]
    assert recuperado.request.mode is RecallMode.INCIDENTE

    # Simulação não deixa rastro: é hipótese, não ato.
    assert recall_repo.get_by_id(prospectivo.recall_id) is None
    assert len(recall_repo.list_by_subject(org_id_1, origem.target_id)) == 1

    # 6. Janela temporal muda o grafo alcançável.
    relation_service.register_relation(
        UniversalRelation.create(
            organization_id=org_id_1,
            source_reference=destino,
            target_reference=_ref(org_id_1),
            relation_type="transformacao",
            created_at=t0,
            confidence=CONFIANCA,
            valid_from=t0 + timedelta(days=30),
        )
    )
    antes = service.execute(
        RecallRequest(
            organization_id=org_id_1,
            subject_reference=origem,
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
            at_time=t0 + timedelta(days=1),
        )
    )
    depois = service.execute(
        RecallRequest(
            organization_id=org_id_1,
            subject_reference=origem,
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
            at_time=t0 + timedelta(days=40),
        )
    )
    assert len(depois.affected_subjects()) > len(antes.affected_subjects())

    # 7. Isolamento: o usuario titan e superusuario e ignora RLS.
    role_name = f"titan_test_rls_{uuid4().hex}"
    quoted_role = db_connection.engine.dialect.identifier_preparer.quote(role_name)
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT SELECT ON core_audit.recalls TO {quoted_role}"))
    db_connection.execute(text(f"GRANT SELECT ON core_audit.relations TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_2.value)},
    )

    repo_2 = TransactionalRecallRepository(connection=db_connection)
    assert repo_2.get_by_id(incidente.recall_id) is None

    # A travessia de outra Organization não enxerga o grafo alheio.
    service_2 = RecallService(relations=TransactionalRelationRepository(connection=db_connection))
    vazio = service_2.execute(
        RecallRequest(
            organization_id=org_id_2,
            subject_reference=UniversalReference(
                target_id=origem.target_id,
                organization_id=org_id_2,
                contract_version=1,
            ),
            direction=RecallDirection.PROSPECTIVA,
            mode=RecallMode.SIMULACAO,
        )
    )
    assert vazio.affected_subjects() == ()

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
