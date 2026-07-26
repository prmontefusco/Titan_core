"""Exigibilidade sanitaria minima (Passo 14.3)."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.sanitary_campaign_service import (
    SanitaryCampaignRepositoryPort,
)
from packages.livestock_application.treatment_service import (
    TreatmentApplicationRepositoryPort,
)
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId


class SanitaryRequirementStatus(Enum):
    ATENDIDA = "ATENDIDA"
    AUSENTE = "AUSENTE"
    INDETERMINADA = "INDETERMINADA"


class SanitaryRequirementGapCode(Enum):
    CAMPANHA_NAO_DECLARADA = "CAMPANHA_NAO_DECLARADA"
    APLICACAO_NAO_ENCONTRADA = "APLICACAO_NAO_ENCONTRADA"


@dataclass(frozen=True, slots=True)
class SanitaryRequirementGap:
    code: SanitaryRequirementGapCode
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True, slots=True)
class SanitaryRequirementAssessment:
    animal_id: TypedId
    campaign_code: str
    status: SanitaryRequirementStatus
    campaign_id: TypedId | None = None
    application_id: TypedId | None = None
    gaps: tuple[SanitaryRequirementGap, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "animal_id": str(self.animal_id.value),
            "campaign_code": self.campaign_code,
            "status": self.status.value,
            "campaign_id": None if self.campaign_id is None else str(self.campaign_id.value),
            "application_id": (
                None if self.application_id is None else str(self.application_id.value)
            ),
            "gaps": [gap.to_dict() for gap in self.gaps],
        }


@dataclass(frozen=True, slots=True)
class SanitaryRequirementService:
    animal_repository: AnimalRepositoryPort
    campaign_repository: SanitaryCampaignRepositoryPort
    application_repository: TreatmentApplicationRepositoryPort

    def assess_required_campaign(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        campaign_code: str,
    ) -> SanitaryRequirementAssessment:
        normalized_code = campaign_code.strip()
        if not normalized_code:
            raise ValueError("campaign_code nao pode ser vazio.")
        animal = self.animal_repository.get_by_id(animal_id)
        if animal is None or animal.organization_id != organization_id:
            raise KeyError(
                f"Animal '{animal_id.value}' nao encontrado ou pertencente a outra organizacao."
            )

        campaign = self.campaign_repository.get_by_code(organization_id, normalized_code)
        if campaign is None:
            return SanitaryRequirementAssessment(
                animal_id=animal_id,
                campaign_code=normalized_code,
                status=SanitaryRequirementStatus.INDETERMINADA,
                gaps=(
                    SanitaryRequirementGap(
                        code=SanitaryRequirementGapCode.CAMPANHA_NAO_DECLARADA,
                        message="Campanha sanitaria exigida ainda nao foi declarada no Titan.",
                    ),
                ),
            )

        application = _application_for_campaign(
            self.application_repository.list_by_animal(organization_id, animal_id),
            campaign.campaign_id,
        )
        if application is None:
            return SanitaryRequirementAssessment(
                animal_id=animal_id,
                campaign_code=normalized_code,
                status=SanitaryRequirementStatus.AUSENTE,
                campaign_id=campaign.campaign_id,
                gaps=(
                    SanitaryRequirementGap(
                        code=SanitaryRequirementGapCode.APLICACAO_NAO_ENCONTRADA,
                        message="Nenhuma aplicacao vinculada a campanha sanitaria exigida.",
                    ),
                ),
            )

        return SanitaryRequirementAssessment(
            animal_id=animal_id,
            campaign_code=normalized_code,
            status=SanitaryRequirementStatus.ATENDIDA,
            campaign_id=campaign.campaign_id,
            application_id=application.application_id,
        )


def _application_for_campaign(
    applications: Sequence[TreatmentApplication],
    campaign_id: TypedId,
) -> TreatmentApplication | None:
    superseded = {
        application.corrects_application_id
        for application in applications
        if application.corrects_application_id is not None
    }
    for application in applications:
        if application.application_id in superseded:
            continue
        if application.sanitary_campaign_id == campaign_id:
            return application
    return None
