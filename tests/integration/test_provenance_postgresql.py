"""Testes de integração PostgreSQL com RLS para Linhagem e Proveniência (Passo 5.8)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.provenance_service import ProvenanceService
from packages.core_domain.events import CanonicalPayload, DomainEvent
from packages.core_domain.evidence import (
    ConfidenceLevel,
    ConfidenceTier,
    Evidence,
    Source,
    SourceType,
)
from packages.core_domain.provenance import ProvenanceNodeType
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.core_infrastructure.persistence.evidence import TransactionalEvidenceRepository
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference


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


def test_provenance_service_full_trace_upstream_and_downstream(
    db_connection: Connection,
) -> None:
    org_id = OrganizationId.new()

    # 1. Cadastra a organizacao
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:id, :id)
            """
        ),
        {"id": org_id.value},
    )

    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id.value)},
    )

    # 2. Registra Source e Evidence
    source_id = TypedId.new("source")
    source = Source(source_id=source_id, source_type=SourceType.DOCUMENT)
    author_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )
    cl = ConfidenceLevel(tier=ConfidenceTier.VERIFIED_SOURCE, reason="Fonte oficial")
    evidence = Evidence.create(
        organization_id=org_id,
        source=source,
        author_reference=author_ref,
        content=b"laudo sanitario de proveniencia 2026",
        confidence_level=cl,
    )

    ev_repo = TransactionalEvidenceRepository(connection=db_connection)
    ev_repo.save(evidence)

    # 3. Registra DomainEvent associado à Evidence
    event_id = TypedId.new("domain_event")
    payload = CanonicalPayload(
        schema="lote.sanitario.v1",
        version=1,
        value={"status": "APROVADO"},
    )
    domain_event = DomainEvent(
        event_id=event_id,
        organization_id=org_id,
        aggregate_reference=UniversalReference(
            target_id=TypedId(entity_type="lote", value=TypedId.new("lote").value),
            organization_id=org_id,
            contract_version=1,
        ),
        aggregate_version=1,
        event_type="lote_sanitario_registrado",
        event_version=1,
        timestamps=RecordTimestamps(
            occurred_at=datetime.now(UTC),
            recorded_at=datetime.now(UTC),
        ),
        actor_reference=author_ref,
        source_reference=UniversalReference(
            target_id=source_id,
            organization_id=org_id,
            contract_version=1,
        ),
        correlation_id=TypedId.new("correlation"),
        causation_id=None,
        payload=payload,
    )

    event_log = DomainEventRepository(connection=db_connection)
    event_log.append(domain_event)

    # 4. Instancia o ProvenanceService e executa rastreamentos
    prov_service = ProvenanceService(evidence_repository=ev_repo, event_repository=event_log)

    # Rastreio a partir do evento (upstream trace)
    trace_event = prov_service.trace_from_event(event_id)
    assert trace_event.root_id == event_id
    node_types_event = [n.node_type for n in trace_event.nodes]
    assert ProvenanceNodeType.EVENT in node_types_event
    assert ProvenanceNodeType.EVIDENCE in node_types_event
    assert ProvenanceNodeType.SOURCE in node_types_event
    assert len(trace_event.edges) == 2

    # Rastreio a partir da evidencia (downstream e upstream trace)
    trace_evidence = prov_service.trace_from_evidence(evidence.evidence_id)
    assert trace_evidence.root_id == evidence.evidence_id
    node_types_ev = [n.node_type for n in trace_evidence.nodes]
    assert ProvenanceNodeType.EVIDENCE in node_types_ev
    assert ProvenanceNodeType.SOURCE in node_types_ev
    assert ProvenanceNodeType.EVENT in node_types_ev

    # Rastreio a partir da fonte (downstream trace)
    trace_source = prov_service.trace_from_source(source_id)
    assert trace_source.root_id == source_id
    assert len(trace_source.nodes) >= 3
