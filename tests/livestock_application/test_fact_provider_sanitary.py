"""Testes do fato de exigibilidade sanitária no fact_provider (Item 4 da fila).

O mecanismo espelha establishment_qualification_fact_type: um fact_type por
campanha, para que uma regra governada por mercado possa referenciá-lo numa
RuleCondition, sem que market_eligibility.py precise conhecer campanhas.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_application.establishment_qualification_service import (
    establishment_qualification_fact_type,
)
from packages.livestock_application.fact_provider import (
    ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE,
    LivestockFactProvider,
    sanitary_requirement_fact_type,
)
from packages.livestock_application.movement_service import PropertyStayRepositoryPort
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.animal import Animal, AnimalSex
from packages.livestock_domain.environmental_embargo_assertion import (
    EnvironmentalEmbargoAssertionStatus,
    PropertyEnvironmentalEmbargoAssertion,
)
from packages.livestock_domain.establishment_qualification import (
    EstablishmentQualification,
    EstablishmentQualificationStatus,
)
from packages.livestock_domain.establishment_qualification_assertion import (
    AssertionStatus,
    EstablishmentQualificationAssertion,
)
from packages.livestock_domain.external_counterparty import CounterpartyType, ExternalCounterparty
from packages.livestock_domain.movement import PropertyStay, StayStatus
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


class _InMemoryCounterpartyRepo:
    def __init__(self, counterparties: list[ExternalCounterparty]) -> None:
        self._counterparties = counterparties

    def save(self, counterparty: ExternalCounterparty) -> None:
        self._counterparties.append(counterparty)

    def get_by_id(self, counterparty_id: TypedId) -> ExternalCounterparty | None:
        return next((c for c in self._counterparties if c.counterparty_id == counterparty_id), None)

    def list_by_organization(self, organization_id: OrganizationId) -> list[ExternalCounterparty]:
        return [c for c in self._counterparties if c.organization_id == organization_id]


class _InMemoryLegacyQualificationRepo:
    def __init__(self, qualifications: list[EstablishmentQualification]) -> None:
        self._qualifications = qualifications

    def save(self, qualification: EstablishmentQualification) -> None:
        self._qualifications.append(qualification)

    def list_by_counterparty(
        self, organization_id: OrganizationId, counterparty_id: TypedId
    ) -> list[EstablishmentQualification]:
        return [
            item
            for item in self._qualifications
            if item.organization_id == organization_id and item.counterparty_id == counterparty_id
        ]


class _InMemoryAssertionRepo:
    def __init__(self, assertions: list[EstablishmentQualificationAssertion]) -> None:
        self._assertions = assertions

    def list_by_establishment(
        self, organization_id: OrganizationId, establishment_id: TypedId
    ) -> list[EstablishmentQualificationAssertion]:
        return [
            item
            for item in self._assertions
            if item.organization_id == organization_id and item.establishment_id == establishment_id
        ]


class _InMemoryEmbargoAssertionRepo:
    def __init__(self, assertions: list[PropertyEnvironmentalEmbargoAssertion]) -> None:
        self._assertions = assertions

    def save(self, assertion: PropertyEnvironmentalEmbargoAssertion) -> None:
        self._assertions.append(assertion)

    def list_by_property(
        self, organization_id: OrganizationId, property_id: TypedId
    ) -> list[PropertyEnvironmentalEmbargoAssertion]:
        return [
            item
            for item in self._assertions
            if item.organization_id == organization_id and item.property_id == property_id
        ]


class _InMemoryStayRepo(PropertyStayRepositoryPort):
    def __init__(self, active_by_animal: dict[TypedId, PropertyStay]) -> None:
        self._active_by_animal = active_by_animal

    def save(self, stay: PropertyStay) -> None: ...

    def update(self, stay: PropertyStay) -> None: ...

    def delete_by_animal(self, animal_id: TypedId) -> None: ...

    def get_active_stay(self, animal_id: TypedId) -> PropertyStay | None:
        return self._active_by_animal.get(animal_id)

    def get_timeline(self, animal_id: TypedId) -> list[PropertyStay]:
        active = self.get_active_stay(animal_id)
        return [] if active is None else [active]


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


def _embargo_assertion(
    org_id: OrganizationId,
    property_id: TypedId,
    *,
    observed_at: datetime,
    status: EnvironmentalEmbargoAssertionStatus = EnvironmentalEmbargoAssertionStatus.COM_RESTRICAO,
) -> PropertyEnvironmentalEmbargoAssertion:
    return PropertyEnvironmentalEmbargoAssertion.create(
        organization_id=org_id,
        property_id=property_id,
        geometry_id=TypedId.new("property_geometry"),
        geometry_version=3,
        source_name="IBAMA",
        source_layer="IBAMA_EMBARGOS",
        operation="intersects",
        status=status,
        source_digest="a" * 64,
        response_digest="b" * 64,
        version_ids=("ibama_v3",),
        restrictions_payload=(
            {
                "source": "IBAMA",
                "layer": "IBAMA_EMBARGOS",
                "feature_id": 99,
                "version_id": "ibama_v3",
                "polygon_digest": "c" * 64,
                "attributes": {"nom_embarg": "Area teste"},
            },
        )
        if status is EnvironmentalEmbargoAssertionStatus.COM_RESTRICAO
        else (),
        observed_at=observed_at,
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


def test_qualificacao_de_estabelecimento_prefere_assercao_bitemporal_ao_legado() -> None:
    org_id = _org()
    counterparty = ExternalCounterparty(
        counterparty_id=TypedId.new("external_counterparty"),
        organization_id=org_id,
        name="Frigorifico Teste",
        counterparty_type=CounterpartyType.SLAUGHTERHOUSE,
    )
    agora = datetime.now(UTC)
    legado = EstablishmentQualification.create(
        organization_id=org_id,
        counterparty_id=counterparty.counterparty_id,
        market_purpose="exportacao-china",
        status=EstablishmentQualificationStatus.NAO_HABILITADO,
        source_name="legado",
        source_version="v1",
        assessed_at=agora - timedelta(days=2),
    )
    assertion = EstablishmentQualificationAssertion.create(
        organization_id=org_id,
        establishment_id=counterparty.counterparty_id,
        qualification_type="exportacao-china",
        asserted_status=AssertionStatus.QUALIFIED,
        effective_from=None,
        effective_until=None,
        observed_at=agora - timedelta(days=1),
        source_artifact_id=TypedId.new("qualification_source_artifact"),
        confidence_tier=ConfidenceTier.DOCUMENTED,
    )
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({}),
        external_counterparty_repository=_InMemoryCounterpartyRepo([counterparty]),
        establishment_qualification_repository=_InMemoryLegacyQualificationRepo([legado]),
        establishment_qualification_assertion_repository=_InMemoryAssertionRepo([assertion]),
    )

    snapshot = provider.get_snapshot(org_id, counterparty.counterparty_id, agora)
    fatos = [
        f
        for f in snapshot.facts
        if f.fact_type == establishment_qualification_fact_type("exportacao-china")
    ]

    assert len(fatos) == 1
    assert fatos[0].payload["qualification_status"] == "HABILITADO"
    assert fatos[0].payload["asserted_status"] == "QUALIFIED"


def test_emite_fato_de_embargo_ambiental_da_assertion_mais_recente_da_propriedade_atual() -> None:
    org_id = _org()
    property_id = TypedId.new("rural_property")
    animal = Animal(
        animal_id=TypedId.new("animal"),
        organization_id=org_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.MALE,
    )
    agora = datetime.now(UTC)
    stay = PropertyStay(
        stay_id=TypedId.new("property_stay"),
        organization_id=org_id,
        animal_id=animal.animal_id,
        property_id=property_id,
        start_time=agora - timedelta(days=5),
        end_time=None,
        status=StayStatus.ACTIVE,
        source_movement_id=TypedId.new("animal_movement"),
    )
    antiga = _embargo_assertion(org_id, property_id, observed_at=agora - timedelta(days=3))
    recente = _embargo_assertion(org_id, property_id, observed_at=agora - timedelta(days=1))
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        stay_repository=_InMemoryStayRepo({animal.animal_id: stay}),
        environmental_embargo_assertion_repository=_InMemoryEmbargoAssertionRepo([antiga, recente]),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, agora)
    fatos = [f for f in snapshot.facts if f.fact_type == ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE]

    assert len(fatos) == 1
    assert fatos[0].observed_at == recente.observed_at
    assert fatos[0].payload["assertion_id"] == recente.assertion_id.value.hex
    assert fatos[0].payload["property_id"] == property_id.value.hex
    assert fatos[0].payload["status"] == "COM_RESTRICAO"
    assert fatos[0].payload["restriction_count"] == 1


def test_nao_emite_fato_de_embargo_sem_assertion_conhecida_ate_o_instante() -> None:
    org_id = _org()
    property_id = TypedId.new("rural_property")
    animal = Animal(
        animal_id=TypedId.new("animal"),
        organization_id=org_id,
        birth_property_id=property_id,
        sex=AnimalSex.MALE,
    )
    agora = datetime.now(UTC)
    futura = _embargo_assertion(org_id, property_id, observed_at=agora + timedelta(days=1))
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        environmental_embargo_assertion_repository=_InMemoryEmbargoAssertionRepo([futura]),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, agora)

    assert [f for f in snapshot.facts if f.fact_type == ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE] == []
