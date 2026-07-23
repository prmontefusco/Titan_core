"""Testes de integração PostgreSQL para projeções reconstruíveis (Passo 7.2)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.projection_service import ProjectionRebuildService
from packages.core_application.relation_service import RelationService
from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier
from packages.core_domain.projections import ReferencingKind
from packages.core_domain.relations import UniversalRelation
from packages.core_infrastructure.persistence.projections import (
    PostgresProjectionSource,
    TransactionalProjectionRepository,
)
from packages.core_infrastructure.persistence.relations import TransactionalRelationRepository
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


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


def _count_relations(conn: Connection, org_id: OrganizationId) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT count(*) FROM core_audit.relations
                WHERE record_owner_organization_id = :org_id
                """
            ),
            {"org_id": org_id.value},
        ).scalar_one()
    )


def test_projection_is_rebuildable_without_touching_the_source(
    db_connection: Connection,
) -> None:
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
    projection_repo = TransactionalProjectionRepository(connection=db_connection)
    service = ProjectionRebuildService(
        source=PostgresProjectionSource(connection=db_connection),
        repository=projection_repo,
    )

    origem = _ref(org_id_1)
    destino = _ref(org_id_1)
    confianca = ConfidenceLevel(tier=ConfidenceTier.DOCUMENTED, reason="Documento anexado.")

    relation_service.register_relation(
        UniversalRelation.create(
            organization_id=org_id_1,
            source_reference=origem,
            target_reference=destino,
            relation_type="composicao",
            created_at=t0,
            confidence=confianca,
            valid_from=t0,
        )
    )

    relacoes_antes = _count_relations(db_connection, org_id_1)
    assert relacoes_antes == 1

    digest_original = service.rebuild(org_id_1)
    assert service.is_consistent_with_sources(org_id_1)

    # Referências reversas: quem aponta para o destino.
    apontando = service.list_referencing(org_id_1, destino)
    assert len(apontando) == 1
    assert apontando[0].referencing_kind is ReferencingKind.RELATION

    # Validação central do passo: apagar SOMENTE a projeção e reconstruir.
    projection_repo.clear(org_id_1)
    assert projection_repo.list_all(org_id_1) == []

    digest_reconstruido = service.rebuild(org_id_1)

    assert digest_reconstruido == digest_original
    # A fonte histórica permaneceu intacta durante todo o ciclo.
    assert _count_relations(db_connection, org_id_1) == relacoes_antes

    # Reconstruir de novo não altera nada: a operação é idempotente.
    assert service.rebuild(org_id_1) == digest_original

    # Isolamento de tenant: o usuario titan e superusuario e ignora RLS.
    role_name = f"titan_test_rls_{uuid4().hex}"
    quoted_role = db_connection.engine.dialect.identifier_preparer.quote(role_name)
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT SELECT ON core_audit.reference_projection TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_2.value)},
    )

    repo_2 = TransactionalProjectionRepository(connection=db_connection)
    assert repo_2.list_all(org_id_2) == []
    assert repo_2.list_referencing(org_id_2, destino) == []

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
