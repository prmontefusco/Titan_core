"""Testes de aplicação para FactService e FactProviderPort com provider simulado (Passo 6.3)."""

from datetime import UTC, datetime
from typing import Any

from packages.core_application.fact_service import FactProviderPort, FactService
from packages.core_domain.facts import Fact, FactSnapshot
from packages.shared_kernel import OrganizationId, TypedId


class DummyVerticalFactProvider(FactProviderPort):
    """Simulador de provider de fatos de uma vertical (ex: pecuária ou crédito)."""

    def __init__(self, sample_facts: dict[str, list[dict[str, Any]]]) -> None:
        self.sample_facts = sample_facts

    def get_snapshot(
        self,
        organization_id: OrganizationId,
        target_id: TypedId,
        at_time: datetime,
    ) -> FactSnapshot:
        facts: list[Fact] = []
        raw_list = self.sample_facts.get(str(target_id.value), [])
        for item in raw_list:
            facts.append(
                Fact.create(
                    fact_type=item["type"],
                    payload=item["payload"],
                    observed_at=at_time,
                )
            )
        return FactSnapshot.create(
            organization_id=organization_id,
            target_id=target_id,
            as_of=at_time,
            facts=facts,
        )


def test_fact_service_with_dummy_vertical_provider() -> None:
    target_id = TypedId.new("lote")
    provider_data = {
        str(target_id.value): [
            {
                "type": "livestock.weight_record",
                "payload": {"average_weight_kg": 480},
            },
            {
                "type": "livestock.sanitary_status",
                "payload": {"quarantine_cleared": True},
            },
        ]
    }
    dummy_provider = DummyVerticalFactProvider(sample_facts=provider_data)
    service = FactService(provider=dummy_provider)

    org_id = OrganizationId.new()
    now = datetime.now(UTC)

    snapshot = service.get_snapshot_for_evaluation(org_id, target_id, now)

    assert snapshot.target_id == target_id
    assert len(snapshot.facts) == 2

    weight_facts = snapshot.get_facts_by_type("livestock.weight_record")
    assert len(weight_facts) == 1
    assert weight_facts[0].payload["average_weight_kg"] == 480

    sanitary_facts = snapshot.get_facts_by_type("livestock.sanitary_status")
    assert len(sanitary_facts) == 1
    assert sanitary_facts[0].payload["quarantine_cleared"] is True
