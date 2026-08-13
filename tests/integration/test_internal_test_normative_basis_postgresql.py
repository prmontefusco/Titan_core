"""Round-trip, RLS e append-only do catálogo normativo sintético."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text

from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.rule import Rule, SeverityLevel
from packages.core_infrastructure.persistence import set_local_organization_context
from packages.livestock_application.internal_test_normative_basis import (
    MARKET_TEST_A_CODE,
    MARKET_TEST_A_PURPOSE,
    InternalTestNormativeBasis,
    PersistedInternalTestNormativeBasisSnapshotProvider,
)
from packages.livestock_infrastructure.persistence import (
    TransactionalInternalTestNormativeBasisRepository,
)
from packages.shared_kernel import TypedId
from tests.livestock_api_support import Ambiente


def _item(ambiente: Ambiente) -> InternalTestNormativeBasis:
    return InternalTestNormativeBasis(
        normative_basis_id=TypedId.new("normative_basis"),
        organization_id=ambiente.org_a.organization_id,
        code=f"TEST-BASIS-A-{uuid4().hex[:8]}",
        version=1,
        policy_id=TypedId.new("policy"),
        policy_code=MARKET_TEST_A_CODE,
        policy_version=1,
        purpose=MARKET_TEST_A_PURPOSE,
        valid_from=datetime(2026, 1, 1, tzinfo=UTC),
        valid_until=datetime(2026, 7, 1, tzinfo=UTC),
        known_at=datetime(2026, 1, 1, tzinfo=UTC),
        approved_by="SYSTEM:INTERNAL_TEST_CATALOG",
        approved_at=datetime(2026, 1, 1, tzinfo=UTC),
        instrument_code="TEST-BASIS-A",
        instrument_version="1",
        provision="synthetic-market-test",
        content_digest="a" * 64,
        limitations=("SYNTHETIC_MATERIAL",),
    )


def test_internal_test_catalog_round_trip_is_tenant_isolated_and_append_only(
    ambiente: Ambiente,
) -> None:
    connection = ambiente.connection
    item = _item(ambiente)
    set_local_organization_context(connection, ambiente.org_a.organization_id)
    repository = TransactionalInternalTestNormativeBasisRepository(connection)
    repository.save(item)

    reloaded = repository.list_by_policy(ambiente.org_a.organization_id, item.policy_id)
    assert reloaded == [item]

    set_local_organization_context(connection, ambiente.org_b.organization_id)
    assert repository.list_by_policy(ambiente.org_b.organization_id, item.policy_id) == []

    set_local_organization_context(connection, ambiente.org_a.organization_id)
    selected_policy = Policy(
        policy_id=item.policy_id,
        organization_id=ambiente.org_a.organization_id,
        code=MARKET_TEST_A_CODE,
        name="Mercado sintético A",
        description="teste",
        status=PolicyStatus.PUBLISHED,
        valid_from=item.valid_from,
        valid_to=item.valid_until,
        published_at=item.known_at,
    )
    selected_rule = Rule(
        rule_id=TypedId.new("rule"),
        policy_id=item.policy_id,
        organization_id=ambiente.org_a.organization_id,
        code="market-test-a-rule",
        name="Regra sintética",
        description="teste",
        severity=SeverityLevel.BLOCKING,
        normative_source="material interno sintético",
    )
    snapshot = PersistedInternalTestNormativeBasisSnapshotProvider(repository).select(
        policy=selected_policy,
        rules=(selected_rule,),
        purpose=MARKET_TEST_A_PURPOSE,
        reference_time=datetime(2026, 5, 1, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 5, 1, tzinfo=UTC),
    )
    assert snapshot is not None
    assert snapshot.normative_basis_id == item.normative_basis_id

    role_name = f"titan_internal_catalog_probe_{uuid4().hex[:12]}"
    quoted_role = connection.dialect.identifier_preparer.quote(role_name)
    connection.execute(
        text(
            f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    connection.execute(
        text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON core_audit.internal_test_normative_bases "
            f"TO {quoted_role}"
        )
    )
    try:
        connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
        connection.execute(
            text("SELECT set_config('titan.organization_id', :organization_id, true)"),
            {"organization_id": str(ambiente.org_b.organization_id.value)},
        )
        assert repository.list_by_policy(ambiente.org_b.organization_id, item.policy_id) == []
        assert (
            connection.execute(
                text(
                    "UPDATE core_audit.internal_test_normative_bases SET code = 'alterado' "
                    "WHERE normative_basis_id = :normative_basis_id"
                ),
                {"normative_basis_id": item.normative_basis_id.value},
            ).rowcount
            == 0
        )
        assert (
            connection.execute(
                text(
                    "DELETE FROM core_audit.internal_test_normative_bases "
                    "WHERE normative_basis_id = :normative_basis_id"
                ),
                {"normative_basis_id": item.normative_basis_id.value},
            ).rowcount
            == 0
        )
    finally:
        connection.execute(text("RESET ROLE"))
        connection.execute(text(f"DROP OWNED BY {quoted_role}"))
        connection.execute(text(f"DROP ROLE {quoted_role}"))

    policy_commands = (
        connection.execute(
            text(
                "SELECT cmd FROM pg_policies WHERE schemaname = 'core_audit' "
                "AND tablename = 'internal_test_normative_bases' ORDER BY cmd"
            )
        )
        .scalars()
        .all()
    )
    assert policy_commands == ["INSERT", "SELECT"]
