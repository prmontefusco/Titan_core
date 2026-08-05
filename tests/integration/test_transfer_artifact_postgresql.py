"""Testes de integração PostgreSQL com RLS para ReceivedTransferArtifact.

Fecha a prova do LIV-C02 no banco autoritativo: a cobertura derivada continua
vindo de conceitos existentes (`HistoryCoverage` + artifact recebido), persiste
sem inventar entidade nova e permanece isolada por Organization.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.livestock_domain.transfer_artifact import (
    HistoryCoverage,
    ReceivedTransferArtifact,
    TransferArtifactGapCode,
)
from packages.livestock_infrastructure.persistence.transfer_artifact_repository import (
    TransactionalReceivedTransferArtifactRepository,
)
from packages.shared_kernel import OrganizationId, TypedId


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


def test_received_transfer_artifact_persists_coverage_and_respects_rls(
    db_connection: Connection,
) -> None:
    org_1 = OrganizationId(uuid4())
    org_2 = OrganizationId(uuid4())
    animal_id = TypedId.new("animal")
    counterparty_id = TypedId.new("external_counterparty")
    transfer_effective_at = datetime.now(UTC) - timedelta(days=1)
    known_until = transfer_effective_at - timedelta(hours=6)

    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:org1, :org1), (:org2, :org2)
            """
        ),
        {"org1": org_1.value, "org2": org_2.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_1.value)},
    )
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.rural_properties (
                property_id, record_owner_organization_id, code, name,
                municipality, state_code, created_at
            ) VALUES (:p, :org, 'FAZ-C02', 'Fazenda C02', 'Cuiaba', 'MT', NOW())
            """
        ),
        {"p": TypedId.new("rural_property").value, "org": org_1.value},
    )
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.animals (
                animal_id, record_owner_organization_id, birth_property_id, sex, created_at
            ) VALUES (:a, :org, :p, 'FEMALE', NOW())
            """
        ),
        {
            "a": animal_id.value,
            "org": org_1.value,
            "p": db_connection.execute(
                text(
                    """
                    SELECT property_id
                    FROM core_audit.rural_properties
                    WHERE record_owner_organization_id = :org
                    LIMIT 1
                    """
                ),
                {"org": org_1.value},
            ).scalar_one(),
        },
    )
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.external_counterparties (
                counterparty_id, record_owner_organization_id, name, counterparty_type, created_at
            ) VALUES (:c, :org, 'Fazenda Origem', 'FARM', NOW())
            """
        ),
        {"c": counterparty_id.value, "org": org_1.value},
    )

    repo = TransactionalReceivedTransferArtifactRepository(connection=db_connection)
    artifact = ReceivedTransferArtifact(
        artifact_id=TypedId.new("received_transfer_artifact"),
        organization_id=org_1,
        animal_id=animal_id,
        source_counterparty_id=counterparty_id,
        bundle_digest="a" * 64,
        bundle_issued_at=transfer_effective_at - timedelta(hours=1),
        transfer_effective_at=transfer_effective_at,
        coverage=HistoryCoverage.from_transfer(
            known_from=transfer_effective_at - timedelta(days=200),
            known_until=known_until,
            transfer_effective_at=transfer_effective_at,
        ),
        issuer_name="Fazenda Origem",
        created_at=datetime.now(UTC),
    )
    repo.save(artifact)

    encontrados = repo.list_by_animal(animal_id)
    assert len(encontrados) == 1
    recarregado = encontrados[0]
    assert recarregado.coverage.known_until == known_until
    assert recarregado.coverage.gaps[0].code is TransferArtifactGapCode.COVERAGE_BEFORE_TRANSFER

    role_name = f"titan_rls_transfer_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(
        text(f"GRANT SELECT ON core_audit.received_transfer_artifacts TO {quoted_role}")
    )
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )

    repo_2 = TransactionalReceivedTransferArtifactRepository(connection=db_connection)
    assert repo_2.list_by_animal(animal_id) == []

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
