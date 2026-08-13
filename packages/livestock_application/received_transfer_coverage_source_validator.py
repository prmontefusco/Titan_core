"""Primeiro adapter concreto para fonte admissÃ­vel de coverage dimensional."""

from dataclasses import dataclass

from packages.livestock_application.coverage_contribution_service import (
    CoverageContributionSourceValidatorPort,
)
from packages.livestock_application.transfer_artifact_service import (
    ReceivedTransferArtifactRepositoryPort,
)
from packages.shared_kernel import OrganizationId, TypedId


@dataclass(frozen=True, slots=True)
class ReceivedTransferCoverageSourceValidator(CoverageContributionSourceValidatorPort):
    """Aceita somente artefato recebido pertencente ao Animal e Ã  Organization.

    O contrato continua neutro: futuros adapters implementam a mesma porta,
    sem converter documentos ou APIs em artefato de transferÃªncia.
    """

    repository: ReceivedTransferArtifactRepositoryPort

    def supports(
        self,
        *,
        organization_id: OrganizationId,
        subject_id: TypedId,
        source_id: TypedId,
    ) -> bool:
        if source_id.entity_type != "received_transfer_artifact":
            return False
        artifact = self.repository.get_by_id(source_id)
        return (
            artifact is not None
            and artifact.organization_id == organization_id
            and artifact.animal_id == subject_id
        )
