"""Testes do fato de exigibilidade sanitária no fact_provider (Item 4 da fila).

O mecanismo espelha establishment_qualification_fact_type: um fact_type por
campanha, para que uma regra governada por mercado possa referenciá-lo numa
RuleCondition, sem que market_eligibility.py precise conhecer campanhas.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from packages.livestock_application.fact_provider import (
    LivestockFactProvider,
    sanitary_requirement_fact_type,
)
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.animal import Animal, AnimalSex
from packages.livestock_domain.property import RuralProperty
from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.test_treatment_service import InMemoryAnimalRepo


class _NullPropertyRepo(RuralPropertyRepositoryPort):
    def save(self, property: RuralProperty) -> None: ...

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None:
        return None

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        return []


class _InMemoryCampaignRepo:
    def __init__(self, campaigns: list[SanitaryCampaign]) -> None:
        self._campaigns = campaigns

    def save(self, campaign: SanitaryCampaign) -> None:
        self._campaigns.append(campaign)

    def get_by_id(self, campaign_id: TypedId) -> SanitaryCampaign | None:
        return next((c for c in self._campaigns if c.campaign_id == campaign_id), None)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> SanitaryCampaign | None:
        return next(
            (c for c in self._campaigns if c.organization_id == organization_id and c.code == code),
            None,
        )

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[SanitaryCampaign]:
        return [c for c in self._campaigns if c.organization_id == organization_id][
            offset : offset + limit
        ]


class _InMemoryApplicationRepo:
    def __init__(self, applications: list[TreatmentApplication]) -> None:
        self._applications = applications

    def save(self, application: TreatmentApplication) -> None:
        self._applications.append(application)

    def get_by_id(self, application_id: TypedId) -> TreatmentApplication | None:
        return next((a for a in self._applications if a.application_id == application_id), None)

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[TreatmentApplication]:
        return [
            a
            for a in self._applications
            if a.organization_id == organization_id and a.animal_id == animal_id
        ]

    def list_by_batch(
        self, organization_id: OrganizationId, medication_batch_id: TypedId
    ) -> list[TreatmentApplication]:
        return []


def _org() -> OrganizationId:
    return OrganizationId(uuid4())


def _animal(org_id: OrganizationId) -> Animal:
    return Animal(
        animal_id=TypedId.new("animal"),
        organization_id=org_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.FEMALE,
    )


def _campaign(org_id: OrganizationId, code: str) -> SanitaryCampaign:
    agora = datetime.now(UTC)
    return SanitaryCampaign(
        campaign_id=TypedId.new("sanitary_campaign"),
        organization_id=org_id,
        code=code,
        name=f"Campanha {code}",
        starts_at=agora - timedelta(days=90),
        ends_at=agora + timedelta(days=90),
    )


def test_sanitary_requirement_fact_type_normaliza_o_codigo() -> None:
    assert sanitary_requirement_fact_type("Febre-Aftosa") == (
        "livestock.sanitary_requirement.febre-aftosa"
    )
    assert sanitary_requirement_fact_type("Brucelose.2026") == (
        "livestock.sanitary_requirement.brucelose_2026"
    )


def test_emite_fato_atendida_quando_ha_aplicacao_para_a_campanha() -> None:
    org_id = _org()
    animal = _animal(org_id)
    campanha = _campaign(org_id, "febre-aftosa")
    aplicacao = TreatmentApplication(
        application_id=TypedId.new("treatment_application"),
        organization_id=org_id,
        animal_id=animal.animal_id,
        medication_batch_id=TypedId.new("medication_batch"),
        actor_id=TypedId.new("actor"),
        applied_at=datetime.now(UTC) - timedelta(days=10),
        sanitary_campaign_id=campanha.campaign_id,
    )

    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        sanitary_campaign_repository=_InMemoryCampaignRepo([campanha]),
        treatment_application_repository=_InMemoryApplicationRepo([aplicacao]),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, datetime.now(UTC))
    fatos_sanitarios = [
        f for f in snapshot.facts if f.fact_type == sanitary_requirement_fact_type("febre-aftosa")
    ]

    assert len(fatos_sanitarios) == 1
    assert fatos_sanitarios[0].payload["status"] == "ATENDIDA"
    assert fatos_sanitarios[0].payload["application_id"] == aplicacao.application_id.value.hex


def test_emite_fato_ausente_quando_falta_aplicacao_para_a_campanha() -> None:
    org_id = _org()
    animal = _animal(org_id)
    campanha = _campaign(org_id, "brucelose")

    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        sanitary_campaign_repository=_InMemoryCampaignRepo([campanha]),
        treatment_application_repository=_InMemoryApplicationRepo([]),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, datetime.now(UTC))
    fatos_sanitarios = [
        f for f in snapshot.facts if f.fact_type == sanitary_requirement_fact_type("brucelose")
    ]

    assert len(fatos_sanitarios) == 1
    assert fatos_sanitarios[0].payload["status"] == "AUSENTE"
    assert fatos_sanitarios[0].payload["application_id"] is None


def test_emite_um_fato_por_campanha_conhecida_da_organizacao() -> None:
    org_id = _org()
    animal = _animal(org_id)
    campanha_a = _campaign(org_id, "febre-aftosa")
    campanha_b = _campaign(org_id, "brucelose")

    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        sanitary_campaign_repository=_InMemoryCampaignRepo([campanha_a, campanha_b]),
        treatment_application_repository=_InMemoryApplicationRepo([]),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, datetime.now(UTC))
    tipos_sanitarios = {
        f.fact_type
        for f in snapshot.facts
        if f.fact_type.startswith("livestock.sanitary_requirement.")
    }

    assert tipos_sanitarios == {
        sanitary_requirement_fact_type("febre-aftosa"),
        sanitary_requirement_fact_type("brucelose"),
    }


def test_sem_repositorios_configurados_nao_emite_fato_sanitario() -> None:
    """Sem sanitary_campaign_repository/treatment_application_repository, o
    provider continua funcionando -- o mecanismo é opt-in, como os demais
    campos opcionais de LivestockFactProvider."""
    org_id = _org()
    animal = _animal(org_id)

    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, datetime.now(UTC))
    tipos_sanitarios = [
        f for f in snapshot.facts if f.fact_type.startswith("livestock.sanitary_requirement.")
    ]

    assert tipos_sanitarios == []
