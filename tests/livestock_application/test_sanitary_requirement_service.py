"""Testes da exigibilidade sanitaria minima (Passo 14.3)."""

from datetime import UTC, datetime

from packages.livestock_application.sanitary_requirement_service import (
    SanitaryRequirementGapCode,
    SanitaryRequirementService,
    SanitaryRequirementStatus,
)
from packages.livestock_domain.animal import Animal, AnimalSex
from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.test_sanitary_campaign_service import InMemoryCampaignRepo
from tests.livestock_application.test_treatment_service import (
    InMemoryAnimalRepo,
    InMemoryApplicationRepo,
)


def _animal(organization_id: OrganizationId) -> Animal:
    return Animal(
        animal_id=TypedId.new("animal"),
        organization_id=organization_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.FEMALE,
    )


def _campaign(organization_id: OrganizationId) -> SanitaryCampaign:
    return SanitaryCampaign(
        campaign_id=TypedId.new("sanitary_campaign"),
        organization_id=organization_id,
        code="PNCEBT-BRUCELOSE-2026",
        name="Campanha Brucelose 2026",
        starts_at=datetime(2026, 1, 1, tzinfo=UTC),
        ends_at=datetime(2026, 12, 31, tzinfo=UTC),
    )


def _application(
    organization_id: OrganizationId,
    animal_id: TypedId,
    campaign_id: TypedId | None,
    corrects: TypedId | None = None,
) -> TreatmentApplication:
    return TreatmentApplication(
        application_id=TypedId.new("treatment_application"),
        organization_id=organization_id,
        animal_id=animal_id,
        medication_batch_id=TypedId.new("medication_batch"),
        actor_id=TypedId.new("actor"),
        applied_at=datetime(2026, 7, 1, tzinfo=UTC),
        sanitary_campaign_id=campaign_id,
        corrects_application_id=corrects,
    )


def _service(
    animal: Animal,
) -> tuple[SanitaryRequirementService, InMemoryCampaignRepo, InMemoryApplicationRepo]:
    animals = InMemoryAnimalRepo({animal.animal_id.value.hex: animal})
    campaigns = InMemoryCampaignRepo()
    applications = InMemoryApplicationRepo()
    return (
        SanitaryRequirementService(
            animal_repository=animals,
            campaign_repository=campaigns,
            application_repository=applications,
        ),
        campaigns,
        applications,
    )


def test_required_campaign_is_met_when_effective_application_is_linked() -> None:
    org_id = OrganizationId.new()
    animal = _animal(org_id)
    service, campaigns, applications = _service(animal)
    campaign = _campaign(org_id)
    campaigns.save(campaign)
    application = _application(org_id, animal.animal_id, campaign.campaign_id)
    applications.save(application)

    result = service.assess_required_campaign(
        org_id,
        animal.animal_id,
        "PNCEBT-BRUCELOSE-2026",
    )

    assert result.status is SanitaryRequirementStatus.ATENDIDA
    assert result.campaign_id == campaign.campaign_id
    assert result.application_id == application.application_id
    assert result.gaps == ()


def test_required_campaign_is_absent_without_application() -> None:
    org_id = OrganizationId.new()
    animal = _animal(org_id)
    service, campaigns, _ = _service(animal)
    campaign = _campaign(org_id)
    campaigns.save(campaign)

    result = service.assess_required_campaign(
        org_id,
        animal.animal_id,
        "PNCEBT-BRUCELOSE-2026",
    )

    assert result.status is SanitaryRequirementStatus.AUSENTE
    assert result.campaign_id == campaign.campaign_id
    assert result.application_id is None
    assert result.gaps[0].code is SanitaryRequirementGapCode.APLICACAO_NAO_ENCONTRADA


def test_undeclared_required_campaign_is_indeterminate() -> None:
    org_id = OrganizationId.new()
    animal = _animal(org_id)
    service, _, _ = _service(animal)

    result = service.assess_required_campaign(
        org_id,
        animal.animal_id,
        "PNCEBT-BRUCELOSE-2026",
    )

    assert result.status is SanitaryRequirementStatus.INDETERMINADA
    assert result.campaign_id is None
    assert result.application_id is None
    assert result.gaps[0].code is SanitaryRequirementGapCode.CAMPANHA_NAO_DECLARADA


def test_corrected_application_no_longer_satisfies_required_campaign() -> None:
    org_id = OrganizationId.new()
    animal = _animal(org_id)
    service, campaigns, applications = _service(animal)
    campaign = _campaign(org_id)
    campaigns.save(campaign)
    original = _application(org_id, animal.animal_id, campaign.campaign_id)
    correction = _application(
        org_id,
        animal.animal_id,
        campaign_id=None,
        corrects=original.application_id,
    )
    applications.save(original)
    applications.save(correction)

    result = service.assess_required_campaign(
        org_id,
        animal.animal_id,
        "PNCEBT-BRUCELOSE-2026",
    )

    assert result.status is SanitaryRequirementStatus.AUSENTE
    assert result.application_id is None
