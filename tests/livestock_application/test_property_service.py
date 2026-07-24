"""Testes unitários para RuralPropertyService (Passo 8.1 - Titan Livestock)."""

from decimal import Decimal

import pytest

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.property_service import (
    RuralPropertyRepositoryPort,
    RuralPropertyService,
)
from packages.livestock_domain.events import PROPERTY_REGISTERED
from packages.livestock_domain.property import RuralProperty
from packages.shared_kernel import CanonicalSerializer, OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog


class InMemoryRuralPropertyRepository(RuralPropertyRepositoryPort):
    def __init__(self) -> None:
        self.properties: dict[str, RuralProperty] = {}

    def save(self, property: RuralProperty) -> None:
        self.properties[property.property_id.value.hex] = property

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None:
        return self.properties.get(property_id.value.hex)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        for prop in self.properties.values():
            if prop.organization_id == organization_id and prop.code == code:
                return prop
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        filtered = [p for p in self.properties.values() if p.organization_id == organization_id]
        return filtered[offset : offset + limit]


def build_service(
    recorder: LivestockEventRecorder,
) -> tuple[RuralPropertyService, InMemoryRuralPropertyRepository]:
    repo = InMemoryRuralPropertyRepository()
    return RuralPropertyService(repository=repo, recorder=recorder), repo


def test_register_property_success(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    service, repo = build_service(recorder)

    prop = service.register_property(
        context=context,
        code="PROP-MG-001",
        name="Fazenda Boa Vista",
        municipality="Uberaba",
        state_code="MG",
        registration_number="CAR-MG-9981",
        total_area_hectares=500.0,
    )

    assert prop.code == "PROP-MG-001"
    assert prop.organization_id == context.organization_id
    assert repo.get_by_id(prop.property_id) == prop


def test_register_property_records_event_on_the_property_stream(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, _ = build_service(recorder)

    prop = service.register_property(
        context=context,
        code="PROP-MG-001",
        name="Fazenda Boa Vista",
        municipality="Uberaba",
        state_code="MG",
        total_area_hectares=500.0,
    )

    event = event_log.only(PROPERTY_REGISTERED)
    assert event.aggregate_reference.target_id == prop.property_id
    assert event.aggregate_version == 1
    assert event.actor_reference == context.actor_reference


def test_registered_payload_carries_the_declared_content(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """A área é float no agregado e Decimal no payload: o serializador recusa float."""
    service, _ = build_service(recorder)

    service.register_property(
        context=context,
        code="PROP-MG-001",
        name="Fazenda Boa Vista",
        municipality="Uberaba",
        state_code="MG",
        total_area_hectares=500.5,
    )

    event = event_log.only(PROPERTY_REGISTERED)
    assert event.payload.schema == "livestock_property_registered_payload"
    assert event.payload.canonical_bytes == CanonicalSerializer().serialize(
        {
            "data": {
                "code": "PROP-MG-001",
                "municipality": "Uberaba",
                "name": "Fazenda Boa Vista",
                "property_id": str(event.aggregate_reference.target_id.value),
                "registration_number": None,
                "state_code": "MG",
                "total_area_hectares": Decimal("500.5"),
            },
            "schema": "livestock_property_registered_payload",
            "version": 1,
        }
    )


def test_register_property_duplicate_code_fails(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, _ = build_service(recorder)

    service.register_property(
        context=context,
        code="PROP-MG-001",
        name="Fazenda Boa Vista",
        municipality="Uberaba",
        state_code="MG",
    )

    with pytest.raises(ValueError, match="já cadastrada para a organização"):
        service.register_property(
            context=context,
            code="PROP-MG-001",
            name="Outra Fazenda com mesmo código",
            municipality="Uberlândia",
            state_code="MG",
        )

    assert len(event_log.of_type(PROPERTY_REGISTERED)) == 1, (
        "Operação recusada não pode deixar evento no log."
    )
