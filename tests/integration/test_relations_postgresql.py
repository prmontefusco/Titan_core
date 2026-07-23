"""Testes de integração PostgreSQL com RLS para Relações Universais (Passo 7.1)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.relation_service import RelationService
from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier
from packages.core_domain.relations import UniversalRelation
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


def _ref(org_id: OrganizationId, entity_type: str = "subject") -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new(entity_type), organization_id=org_id, contract_version=1
    )


def test_temporal_graph_traversal_and_tenant_isolation(db_connection: Connection) -> None:
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

    repo = TransactionalRelationRepository(connection=db_connection)
    service = RelationService(repository=repo)
    confianca = ConfidenceLevel(tier=ConfidenceTier.DOCUMENTED, reason="Documento anexado.")

    # Grafo fictício e genérico: origem -> intermediario -> destino, sem termos de vertical.
    origem = _ref(org_id_1)
    intermediario = _ref(org_id_1)
    destino = _ref(org_id_1)

    primeira = service.register_relation(
        UniversalRelation.create(
            organization_id=org_id_1,
            source_reference=origem,
            target_reference=intermediario,
            relation_type="transformacao",
            created_at=t0,
            confidence=confianca,
            valid_from=t0,
            quantity=Decimal("120.500"),
            unit="kg",
            created_by_event=TypedId.new("domain_event"),
            evidence_references=(_ref(org_id_1, "evidence"),),
            metadata={"nota": "origem declarada"},
        )
    )
    service.register_relation(
        UniversalRelation.create(
            organization_id=org_id_1,
            source_reference=intermediario,
            target_reference=destino,
            relation_type="transformacao",
            created_at=t0,
            confidence=confianca,
            valid_from=t0 + timedelta(days=20),
        )
    )

    # Round-trip preserva quantidade decimal, evidências, evento e metadados.
    recarregada = repo.get_by_id(primeira.relation_id)
    assert recarregada is not None
    assert recarregada.quantity == Decimal("120.500")
    assert recarregada.unit == "kg"
    assert recarregada.evidence_references == primeira.evidence_references
    assert recarregada.created_by_event == primeira.created_by_event
    assert recarregada.metadata == {"nota": "origem declarada"}

    # Consulta em datas diferentes devolve grafos diferentes.
    no_dia_1 = service.list_outgoing_at(org_id_1, intermediario, t0 + timedelta(days=1))
    assert no_dia_1 == []
    no_dia_30 = service.list_outgoing_at(org_id_1, intermediario, t0 + timedelta(days=30))
    assert len(no_dia_30) == 1

    # Navegação retrospectiva: quem aponta para o intermediário.
    entrando = service.list_incoming_at(org_id_1, intermediario, t0 + timedelta(days=1))
    assert [r.relation_id for r in entrando] == [primeira.relation_id]

    # Encerrar preserva o passado.
    service.close_relation(primeira.relation_id, t0 + timedelta(days=10))
    assert service.list_outgoing_at(org_id_1, origem, t0 + timedelta(days=5))
    assert not service.list_outgoing_at(org_id_1, origem, t0 + timedelta(days=15))

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
    db_connection.execute(text(f"GRANT SELECT ON core_audit.relations TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_2.value)},
    )

    repo_2 = TransactionalRelationRepository(connection=db_connection)
    assert repo_2.get_by_id(primeira.relation_id) is None
    assert repo_2.list_outgoing(org_id_2, origem.target_id) == []

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
