"""Testes do fato de exigibilidade sanitária no fact_provider (Item 4 da fila).

O mecanismo espelha establishment_qualification_fact_type: um fact_type por
campanha, para que uma regra governada por mercado possa referenciá-lo numa
RuleCondition, sem que market_eligibility.py precise conhecer campanhas.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_application.establishment_qualification_service import (
    establishment_qualification_fact_type,
)
from packages.livestock_application.fact_provider import (
    ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE,
    HISTORY_COVERAGE_FACT_TYPE,
    MOVEMENT_DERIVED_PROPERTY_STAY_FACT_TYPE,
    TERRITORIAL_DETER_FACT_TYPE,
    TERRITORIAL_FUNAI_FACT_TYPE,
    TERRITORIAL_PRODES_FACT_TYPE,
    LivestockFactProvider,
    sanitary_requirement_fact_type,
)
from packages.livestock_application.movement_service import (
    MovementRepositoryPort,
    PropertyStayRepositoryPort,
)
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.territorial_overlap_service import (
    PropertyTerritorialOverlapAssessment,
    TerritorialOverlapGap,
    TerritorialOverlapGapCode,
    TerritorialOverlapStatus,
)
from packages.livestock_application.territorial_timeline_service import (
    PropertyTerritorialTimelineAssessment,
    TerritorialTimelineGap,
    TerritorialTimelineGapCode,
    TerritorialTimelineStatus,
)
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
from packages.livestock_domain.external_counterparty import (
    CounterpartyType,
    ExternalCounterparty,
)
from packages.livestock_domain.imported_fact import FactOrigin, ImportedLivestockFact
from packages.livestock_domain.movement import AnimalMovement, PropertyStay, StayStatus
from packages.livestock_domain.property import RuralProperty
from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.livestock_domain.transfer_artifact import (
    HistoryCoverage,
    ReceivedTransferArtifact,
)
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


class _InMemoryMovementRepo(MovementRepositoryPort):
    def __init__(self, movements: list[AnimalMovement]) -> None:
        self._movements = movements

    def save(self, movement: AnimalMovement) -> None:
        self._movements.append(movement)

    def get_by_id(self, movement_id: TypedId) -> AnimalMovement | None:
        return next(
            (item for item in self._movements if item.movement_id == movement_id),
            None,
        )

    def list_by_animal(self, animal_id: TypedId) -> list[AnimalMovement]:
        return [item for item in self._movements if animal_id in item.animal_ids]

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[AnimalMovement]:
        return [item for item in self._movements if item.organization_id == organization_id][
            offset : offset + limit
        ]


class _TerritorialTimelineServiceFake:
    def __init__(
        self,
        *,
        prodes: PropertyTerritorialTimelineAssessment,
        deter: PropertyTerritorialTimelineAssessment,
    ) -> None:
        self.prodes = prodes
        self.deter = deter

    def assess_prodes_timeline(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
        *,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> PropertyTerritorialTimelineAssessment:
        return self.prodes

    def assess_deter_timeline(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
        *,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> PropertyTerritorialTimelineAssessment:
        return self.deter


class _TerritorialOverlapServiceFake:
    def __init__(self, *, funai: PropertyTerritorialOverlapAssessment) -> None:
        self.funai = funai

    def assess_funai_overlap(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
    ) -> PropertyTerritorialOverlapAssessment:
        return self.funai


def _org() -> OrganizationId:
    return OrganizationId(uuid4())


def _animal(org_id: OrganizationId) -> Animal:
    return Animal(
        animal_id=TypedId.new("animal"),
        organization_id=org_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.FEMALE,
    )


class _InMemoryTransferArtifactRepo:
    def __init__(self, artifacts: list[ReceivedTransferArtifact]) -> None:
        self._artifacts = artifacts

    def save(self, artifact: ReceivedTransferArtifact) -> None:
        self._artifacts.append(artifact)

    def get_by_id(self, artifact_id: TypedId) -> ReceivedTransferArtifact | None:
        return next(
            (item for item in self._artifacts if item.artifact_id == artifact_id),
            None,
        )

    def list_by_animal(self, animal_id: TypedId) -> list[ReceivedTransferArtifact]:
        return [item for item in self._artifacts if item.animal_id == animal_id]


class _InMemoryImportedFactRepo:
    def __init__(self, facts: list[ImportedLivestockFact]) -> None:
        self._facts = facts

    def save(self, fact: ImportedLivestockFact) -> None:
        self._facts.append(fact)

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[ImportedLivestockFact]:
        return [
            item
            for item in self._facts
            if item.organization_id == organization_id and item.animal_id == animal_id
        ]


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


def _territorial_assessment(
    org_id: OrganizationId,
    property_id: TypedId,
    *,
    layer: str,
    status: str = "DISPONIVEL",
    feature_count: int = 1,
) -> PropertyTerritorialTimelineAssessment:
    return PropertyTerritorialTimelineAssessment(
        property_id=property_id,
        geometry_id=TypedId.new("property_geometry"),
        geometry_version=4,
        external_reference="MS-5006606-3DCF573FEF1E44B9972057BD4C932A9E",
        source="INPE/TerraBrasilis",
        layer=layer,
        status=TerritorialTimelineStatus(status),
        property_area_hectares=1500.5,
        year_from=2020,
        year_to=2021,
        years=(
            {
                "year": 2020,
                "feature_count": feature_count,
                "overlap_area_hectares": 8.25,
                "source_area_hectares": 12.5,
                "version_ids": [f"{layer.lower()}_v1"],
            },
        ),
        response_digest="f" * 64,
        gaps=(
            ()
            if status == "DISPONIVEL"
            else (
                TerritorialTimelineGap(
                    code=TerritorialTimelineGapCode.REFERENCIA_EXTERNA_AUSENTE,
                    message="sem dados",
                ),
            )
        ),
    )


def _territorial_overlap_assessment(
    property_id: TypedId,
    *,
    status: str = "COM_RESTRICAO",
    feature_count: int = 1,
) -> PropertyTerritorialOverlapAssessment:
    return PropertyTerritorialOverlapAssessment(
        property_id=property_id,
        geometry_id=TypedId.new("property_geometry"),
        geometry_version=5,
        external_reference="MS-5006606-3DCF573FEF1E44B9972057BD4C932A9E",
        source="FUNAI",
        layer="FUNAI_TI",
        label="Terras Indigenas (FUNAI)",
        status=TerritorialOverlapStatus(status),
        feature_count=feature_count,
        area_hectares=12.5,
        source_area_hectares=80.0,
        version_ids=("funai_v1",),
        response_digest="d" * 64,
        gaps=(
            ()
            if status != "INDETERMINADA"
            else (
                TerritorialOverlapGap(
                    code=TerritorialOverlapGapCode.REFERENCIA_EXTERNA_AUSENTE,
                    message="sem dados",
                ),
            )
        ),
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


def test_emite_fato_de_cobertura_historica_a_partir_do_artefato_recebido() -> None:
    org_id = _org()
    animal = _animal(org_id)
    counterparty_id = TypedId.new("external_counterparty")
    agora = datetime.now(UTC)
    artifact = ReceivedTransferArtifact(
        artifact_id=TypedId.new("received_transfer_artifact"),
        organization_id=org_id,
        animal_id=animal.animal_id,
        source_counterparty_id=counterparty_id,
        bundle_digest="a" * 64,
        bundle_issued_at=agora - timedelta(days=2),
        transfer_effective_at=agora - timedelta(days=1),
        coverage=HistoryCoverage.from_transfer(
            known_from=agora - timedelta(days=120),
            known_until=agora - timedelta(days=2),
            transfer_effective_at=agora - timedelta(days=1),
        ),
        created_at=agora - timedelta(days=1),
    )
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        transfer_artifact_repository=_InMemoryTransferArtifactRepo([artifact]),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, agora)
    coverage_facts = [f for f in snapshot.facts if f.fact_type == HISTORY_COVERAGE_FACT_TYPE]

    assert len(coverage_facts) == 1
    payload = coverage_facts[0].payload
    assert payload["basis"] == "received_transfer_artifact"
    assert payload["source_artifact_id"] == artifact.artifact_id.value.hex
    assert payload["coverage_status"] == "PARTIAL_DECLARED"
    assert payload["has_declared_gaps"] is True
    assert payload["gaps"][0]["code"] == "COVERAGE_BEFORE_TRANSFER"


def test_sem_artefato_recebido_nao_inventa_fato_de_cobertura() -> None:
    org_id = _org()
    animal = _animal(org_id)
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        transfer_artifact_repository=_InMemoryTransferArtifactRepo([]),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, datetime.now(UTC))

    assert [f for f in snapshot.facts if f.fact_type == HISTORY_COVERAGE_FACT_TYPE] == []


def test_emite_fato_sanitario_importado_no_snapshot_com_proveniencia_e_confianca() -> None:
    org_id = _org()
    animal = _animal(org_id)
    imported_fact = ImportedLivestockFact.create(
        organization_id=org_id,
        animal_id=animal.animal_id,
        source_artifact_id=TypedId.new("received_transfer_artifact"),
        fact_type="livestock.treatment_applied",
        occurred_at=datetime.now(UTC) - timedelta(days=12),
        asserted_by="Fazenda Origem",
        received_by=TypedId.new("actor"),
        confidence_tier=ConfidenceTier.CRYPTOGRAPHICALLY_ATTESTED,
        payload={"withdrawal_period_days": 45, "substance": "produto ficticio"},
    )
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        imported_fact_repository=_InMemoryImportedFactRepo([imported_fact]),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, datetime.now(UTC))
    imported_facts = [
        fact
        for fact in snapshot.facts
        if fact.fact_type == "livestock.treatment_applied"
        and fact.payload.get("imported_fact_id") == imported_fact.imported_fact_id.value.hex
    ]

    assert len(imported_facts) == 1
    fact = imported_facts[0]
    assert fact.payload["origin"] == FactOrigin.IMPORTED_ASSERTION.value
    assert fact.payload["asserted_by"] == "Fazenda Origem"
    assert fact.payload["confidence_tier"] == "CRYPTOGRAPHICALLY_ATTESTED"
    assert fact.payload["source_artifact_id"] == imported_fact.source_artifact_id.value.hex
    assert fact.payload["withdrawal_period_days"] == 45
    assert fact.source_reference is not None
    assert fact.source_reference.target_id == imported_fact.source_artifact_id


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
    futura = replace(
        _embargo_assertion(org_id, property_id, observed_at=agora - timedelta(days=1)),
        recorded_at=agora + timedelta(days=1),
    )
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        environmental_embargo_assertion_repository=_InMemoryEmbargoAssertionRepo([futura]),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, agora)

    assert [f for f in snapshot.facts if f.fact_type == ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE] == []


def test_emite_fatos_territoriais_de_prodes_e_deter_para_a_propriedade_atual() -> None:
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
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        stay_repository=_InMemoryStayRepo({animal.animal_id: stay}),
        territorial_timeline_service=_TerritorialTimelineServiceFake(
            prodes=_territorial_assessment(org_id, property_id, layer="TB_PRODES"),
            deter=_territorial_assessment(org_id, property_id, layer="TB_DETER"),
        ),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, agora)
    facts = {fact.fact_type: fact for fact in snapshot.facts}

    assert TERRITORIAL_PRODES_FACT_TYPE in facts
    assert TERRITORIAL_DETER_FACT_TYPE in facts
    assert facts[TERRITORIAL_PRODES_FACT_TYPE].payload["has_occurrence"] is True
    assert facts[TERRITORIAL_PRODES_FACT_TYPE].payload["occurrence_years"] == [2020]
    assert facts[TERRITORIAL_PRODES_FACT_TYPE].payload["layer"] == "TB_PRODES"
    assert facts[TERRITORIAL_DETER_FACT_TYPE].payload["layer"] == "TB_DETER"
    assert facts[TERRITORIAL_DETER_FACT_TYPE].payload["total_feature_count"] == 1


def test_emite_fato_territorial_funai_para_a_propriedade_atual() -> None:
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
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        stay_repository=_InMemoryStayRepo({animal.animal_id: stay}),
        territorial_overlap_service=_TerritorialOverlapServiceFake(
            funai=_territorial_overlap_assessment(property_id)
        ),
    )

    snapshot = provider.get_snapshot(org_id, animal.animal_id, agora)
    facts = {fact.fact_type: fact for fact in snapshot.facts}

    assert TERRITORIAL_FUNAI_FACT_TYPE in facts
    assert facts[TERRITORIAL_FUNAI_FACT_TYPE].payload["has_overlap"] is True
    assert facts[TERRITORIAL_FUNAI_FACT_TYPE].payload["feature_count"] == 1
    assert facts[TERRITORIAL_FUNAI_FACT_TYPE].payload["layer"] == "FUNAI_TI"


def test_selecao_temporal_nao_reclassifica_estado_atual_como_historico() -> None:
    org_id = _org()
    animal = _animal(org_id)
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
    )
    reference_time = datetime(2026, 1, 10, tzinfo=UTC)
    knowledge_cutoff = datetime(2026, 1, 11, tzinfo=UTC)

    snapshot = provider.get_snapshot_with_temporal_context(
        org_id,
        animal.animal_id,
        reference_time=reference_time,
        knowledge_cutoff=knowledge_cutoff,
    )

    assert snapshot.reference_time == reference_time
    assert snapshot.knowledge_cutoff == knowledge_cutoff
    assert snapshot.get_facts_by_type("livestock.animal") == ()
    assert "LIVESTOCK_CURRENT_STATE_NOT_HISTORICALLY_RECONSTRUCTABLE" in (
        snapshot.knowledge_limitations
    )


def test_temporal_snapshot_derives_property_stay_only_from_known_movements() -> None:
    organization_id = _org()
    animal = _animal(organization_id)
    property_a = TypedId.new("rural_property")
    property_b = TypedId.new("rural_property")
    movement_known_then = AnimalMovement(
        movement_id=TypedId.new("animal_movement"),
        organization_id=organization_id,
        origin_property_id=animal.birth_property_id or TypedId.new("rural_property"),
        destination_property_id=property_a,
        movement_time=datetime(2026, 1, 2, tzinfo=UTC),
        animal_ids=(animal.animal_id,),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    movement_later = AnimalMovement(
        movement_id=TypedId.new("animal_movement"),
        organization_id=organization_id,
        origin_property_id=property_a,
        destination_property_id=property_b,
        movement_time=datetime(2026, 1, 10, tzinfo=UTC),
        animal_ids=(animal.animal_id,),
        created_at=datetime(2026, 1, 10, tzinfo=UTC),
    )
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        movement_repository=_InMemoryMovementRepo([movement_known_then, movement_later]),
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal.animal_id,
        reference_time=datetime(2026, 1, 5, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 5, tzinfo=UTC),
    )

    facts = snapshot.get_facts_by_type(MOVEMENT_DERIVED_PROPERTY_STAY_FACT_TYPE)
    assert len(facts) == 1
    assert facts[0].payload["property_id"] == property_a.value.hex
    assert facts[0].recorded_at == movement_known_then.created_at
    assert facts[0].known_at is None


def test_temporal_snapshot_excludes_retroactive_movement_known_after_cutoff() -> None:
    organization_id = _org()
    animal = _animal(organization_id)
    movement = AnimalMovement(
        movement_id=TypedId.new("animal_movement"),
        organization_id=organization_id,
        origin_property_id=animal.birth_property_id or TypedId.new("rural_property"),
        destination_property_id=TypedId.new("rural_property"),
        movement_time=datetime(2026, 1, 2, tzinfo=UTC),
        animal_ids=(animal.animal_id,),
        created_at=datetime(2026, 1, 10, tzinfo=UTC),
    )
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        movement_repository=_InMemoryMovementRepo([movement]),
    )

    before_knowledge = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal.animal_id,
        reference_time=datetime(2026, 1, 5, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 5, tzinfo=UTC),
    )
    after_knowledge = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal.animal_id,
        reference_time=datetime(2026, 1, 5, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 11, tzinfo=UTC),
    )

    assert before_knowledge.get_facts_by_type(MOVEMENT_DERIVED_PROPERTY_STAY_FACT_TYPE) == ()
    assert "LIVESTOCK_MOVEMENT_HISTORY_ABSENT_AT_CONTEXT" in before_knowledge.knowledge_limitations
    assert len(after_knowledge.get_facts_by_type(MOVEMENT_DERIVED_PROPERTY_STAY_FACT_TYPE)) == 1


def test_temporal_snapshot_refuses_conflicting_movement_sequence() -> None:
    organization_id = _org()
    animal = _animal(organization_id)
    movement_1 = AnimalMovement(
        movement_id=TypedId.new("animal_movement"),
        organization_id=organization_id,
        origin_property_id=animal.birth_property_id or TypedId.new("rural_property"),
        destination_property_id=TypedId.new("rural_property"),
        movement_time=datetime(2026, 1, 2, tzinfo=UTC),
        animal_ids=(animal.animal_id,),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    movement_2 = AnimalMovement(
        movement_id=TypedId.new("animal_movement"),
        organization_id=organization_id,
        origin_property_id=TypedId.new("rural_property"),
        destination_property_id=TypedId.new("rural_property"),
        movement_time=datetime(2026, 1, 3, tzinfo=UTC),
        animal_ids=(animal.animal_id,),
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        movement_repository=_InMemoryMovementRepo([movement_1, movement_2]),
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal.animal_id,
        reference_time=datetime(2026, 1, 5, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 5, tzinfo=UTC),
    )

    assert snapshot.get_facts_by_type(MOVEMENT_DERIVED_PROPERTY_STAY_FACT_TYPE) == ()
    assert "LIVESTOCK_MOVEMENT_HISTORY_CONFLICT" in snapshot.knowledge_limitations


def test_temporal_snapshot_ignores_movement_from_other_organization() -> None:
    organization_id = _org()
    other_organization_id = _org()
    animal = _animal(organization_id)
    foreign_movement = AnimalMovement(
        movement_id=TypedId.new("animal_movement"),
        organization_id=other_organization_id,
        origin_property_id=animal.birth_property_id or TypedId.new("rural_property"),
        destination_property_id=TypedId.new("rural_property"),
        movement_time=datetime(2026, 1, 2, tzinfo=UTC),
        animal_ids=(animal.animal_id,),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    provider = LivestockFactProvider(
        property_repository=_NullPropertyRepo(),
        animal_repository=InMemoryAnimalRepo({animal.animal_id.value.hex: animal}),
        movement_repository=_InMemoryMovementRepo([foreign_movement]),
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal.animal_id,
        reference_time=datetime(2026, 1, 5, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 5, tzinfo=UTC),
    )

    assert snapshot.get_facts_by_type(MOVEMENT_DERIVED_PROPERTY_STAY_FACT_TYPE) == ()
    assert "LIVESTOCK_MOVEMENT_HISTORY_ABSENT_AT_CONTEXT" in snapshot.knowledge_limitations
