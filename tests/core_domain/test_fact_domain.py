"""Testes unitários do modelo de domínio para Fatos e FactSnapshot (Passo 6.3)."""

from datetime import UTC, datetime

import pytest

from packages.core_domain.facts import Fact, FactSnapshot
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def test_fact_creation_and_invariants() -> None:
    now = datetime.now(UTC)
    fact = Fact.create(
        fact_type="livestock.vaccination_record",
        payload={"animal_count": 50, "vaccine": "aftosa"},
        observed_at=now,
    )

    assert fact.fact_type == "livestock.vaccination_record"
    assert fact.payload["animal_count"] == 50
    assert fact.observed_at == now

    with pytest.raises(ValueError, match="fact_type deve ser uma string não vazia"):
        Fact.create(fact_type="  ", payload={}, observed_at=now)


def test_fact_snapshot_deterministic_hash_and_querying() -> None:
    org_id = OrganizationId.new()
    target_id = TypedId.new("batch")
    t0 = datetime.now(UTC)

    f1 = Fact.create(
        fact_type="sanitary.inspection",
        payload={"result": "approved"},
        observed_at=t0,
    )
    f2 = Fact.create(
        fact_type="sanitary.inspection",
        payload={"result": "approved_with_warning"},
        observed_at=t0,
    )
    f3 = Fact.create(
        fact_type="transport.gta",
        payload={"gta_number": "123456"},
        observed_at=t0,
    )

    snapshot_1 = FactSnapshot.create(
        organization_id=org_id,
        target_id=target_id,
        as_of=t0,
        facts=[f3, f1, f2],  # ordem intencionalmente misturada
    )

    snapshot_2 = FactSnapshot.create(
        organization_id=org_id,
        target_id=target_id,
        as_of=t0,
        facts=[f1, f2, f3],  # ordem diferente
    )

    # Hash deve ser 100% determinístico independente da ordem de inserção dos fatos
    assert snapshot_1.snapshot_hash != ""
    assert snapshot_1.snapshot_hash == snapshot_2.snapshot_hash

    # Consulta de fatos por tipo
    inspections = snapshot_1.get_facts_by_type("sanitary.inspection")
    assert len(inspections) == 2

    gtas = snapshot_1.get_facts_by_type("transport.gta")
    assert len(gtas) == 1
    assert gtas[0].payload["gta_number"] == "123456"


def test_fact_snapshot_hash_includes_fact_source_reference() -> None:
    org_id = OrganizationId.new()
    target_id = TypedId.new("batch")
    t0 = datetime.now(UTC)
    source_a = UniversalReference(
        target_id=TypedId.new("evidence"),
        organization_id=org_id,
        contract_version=1,
    )
    source_b = UniversalReference(
        target_id=TypedId.new("evidence"),
        organization_id=org_id,
        contract_version=1,
    )

    snapshot_a = FactSnapshot.create(
        organization_id=org_id,
        target_id=target_id,
        as_of=t0,
        facts=[
            Fact.create(
                fact_type="sanitary.inspection",
                payload={"result": "approved"},
                observed_at=t0,
                source_reference=source_a,
            )
        ],
    )
    snapshot_b = FactSnapshot.create(
        organization_id=org_id,
        target_id=target_id,
        as_of=t0,
        facts=[
            Fact.create(
                fact_type="sanitary.inspection",
                payload={"result": "approved"},
                observed_at=t0,
                source_reference=source_b,
            )
        ],
    )

    assert snapshot_a.snapshot_hash != snapshot_b.snapshot_hash


def test_fact_snapshot_hash_is_stable_when_source_reference_is_the_same() -> None:
    org_id = OrganizationId.new()
    target_id = TypedId.new("batch")
    t0 = datetime.now(UTC)
    source_reference = UniversalReference(
        target_id=TypedId.new("evidence"),
        organization_id=org_id,
        contract_version=1,
    )
    fact = Fact.create(
        fact_type="sanitary.inspection",
        payload={"result": "approved"},
        observed_at=t0,
        source_reference=source_reference,
    )

    snapshot_1 = FactSnapshot.create(
        organization_id=org_id,
        target_id=target_id,
        as_of=t0,
        facts=[fact],
    )
    snapshot_2 = FactSnapshot.create(
        organization_id=org_id,
        target_id=target_id,
        as_of=t0,
        facts=[fact],
    )

    assert snapshot_1.snapshot_hash == snapshot_2.snapshot_hash


def test_fact_snapshot_excludes_future_knowledge_beyond_cutoff() -> None:
    org_id = OrganizationId.new()
    target_id = TypedId.new("batch")
    reference_time = datetime.now(UTC)
    knowledge_cutoff = reference_time
    before_cutoff = Fact.create(
        fact_type="sanitary.inspection",
        payload={"result": "approved"},
        observed_at=reference_time,
        known_at=reference_time,
    )
    after_cutoff = Fact.create(
        fact_type="sanitary.inspection",
        payload={"result": "rejected"},
        observed_at=reference_time,
        known_at=reference_time.replace(year=reference_time.year + 1),
    )

    snapshot = FactSnapshot.create(
        organization_id=org_id,
        target_id=target_id,
        as_of=reference_time,
        reference_time=reference_time,
        knowledge_cutoff=knowledge_cutoff,
        facts=[before_cutoff, after_cutoff],
    )

    assert snapshot.reference_time == reference_time
    assert snapshot.knowledge_cutoff == knowledge_cutoff
    assert snapshot.facts == (before_cutoff,)


def test_fact_snapshot_declares_when_knowledge_cutoff_uses_fallbacks() -> None:
    org_id = OrganizationId.new()
    target_id = TypedId.new("batch")
    instant = datetime.now(UTC)
    fact = Fact.create(
        fact_type="sanitary.inspection",
        payload={"result": "approved"},
        observed_at=instant,
        recorded_at=instant,
        known_at=None,
    )

    snapshot = FactSnapshot.create(
        organization_id=org_id,
        target_id=target_id,
        as_of=instant,
        facts=[fact],
    )

    assert snapshot.knowledge_limitations
    assert any(
        "recorded_at_fallback" in limitation for limitation in snapshot.knowledge_limitations
    )


def test_fact_snapshot_declares_when_normative_acceptance_is_not_known() -> None:
    org_id = OrganizationId.new()
    target_id = TypedId.new("batch")
    instant = datetime.now(UTC)
    fact = Fact.create(
        fact_type="sanitary.inspection",
        payload={"result": "approved"},
        observed_at=instant,
        known_at=instant,
        accepted_at=None,
    )

    snapshot = FactSnapshot.create(
        organization_id=org_id,
        target_id=target_id,
        as_of=instant,
        facts=[fact],
    )

    assert any("accepted_at" in limitation for limitation in snapshot.knowledge_limitations)
