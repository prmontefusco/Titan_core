"""Testes unitários para o domínio RuralProperty (Passo 8.1 - Titan Livestock)."""

from datetime import datetime
from uuid import uuid4

import pytest

from packages.livestock_domain.property import RuralProperty
from packages.shared_kernel import OrganizationId, TypedId


def test_rural_property_creation_valid() -> None:
    org_id = OrganizationId(uuid4())
    prop_id = TypedId.new("rural_property")

    prop = RuralProperty(
        property_id=prop_id,
        organization_id=org_id,
        code="PROP-SP-001",
        name="Fazenda Santa Maria",
        municipality="Ribeirão Preto",
        state_code="SP",
        registration_number="CAR-SP-12345",
        total_area_hectares=150.5,
    )

    assert prop.property_id == prop_id
    assert prop.organization_id == org_id
    assert prop.code == "PROP-SP-001"
    assert prop.name == "Fazenda Santa Maria"
    assert prop.municipality == "Ribeirão Preto"
    assert prop.state_code == "SP"
    assert prop.registration_number == "CAR-SP-12345"
    assert prop.total_area_hectares == 150.5
    assert isinstance(prop.created_at, datetime)


def test_rural_property_invalid_entity_type() -> None:
    org_id = OrganizationId(uuid4())
    invalid_id = TypedId(entity_type="animal", value=uuid4())

    with pytest.raises(ValueError, match="entity_type 'rural_property'"):
        RuralProperty(
            property_id=invalid_id,
            organization_id=org_id,
            code="PROP-SP-001",
            name="Fazenda Teste",
            municipality="Campinas",
            state_code="SP",
        )


def test_rural_property_invalid_code() -> None:
    org_id = OrganizationId(uuid4())
    prop_id = TypedId.new("rural_property")

    with pytest.raises(ValueError, match="code da propriedade rural não pode ser vazio"):
        RuralProperty(
            property_id=prop_id,
            organization_id=org_id,
            code="",
            name="Fazenda Teste",
            municipality="Campinas",
            state_code="SP",
        )


def test_rural_property_invalid_state_code() -> None:
    org_id = OrganizationId(uuid4())
    prop_id = TypedId.new("rural_property")

    with pytest.raises(ValueError, match="state_code deve conter exatamente 2 letras maiúsculas"):
        RuralProperty(
            property_id=prop_id,
            organization_id=org_id,
            code="PROP-01",
            name="Fazenda Teste",
            municipality="Campinas",
            state_code="sp",  # Minúsculo
        )


def test_rural_property_invalid_area() -> None:
    org_id = OrganizationId(uuid4())
    prop_id = TypedId.new("rural_property")

    with pytest.raises(
        ValueError, match="total_area_hectares, quando informado, deve ser um valor positivo"
    ):
        RuralProperty(
            property_id=prop_id,
            organization_id=org_id,
            code="PROP-01",
            name="Fazenda Teste",
            municipality="Campinas",
            state_code="SP",
            total_area_hectares=-10.0,
        )
