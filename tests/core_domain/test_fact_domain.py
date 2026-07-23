"""Testes unitários do modelo de domínio para Fatos e FactSnapshot (Passo 6.3)."""

from datetime import UTC, datetime

import pytest

from packages.core_domain.facts import Fact, FactSnapshot
from packages.shared_kernel import OrganizationId, TypedId


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
