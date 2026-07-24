"""Cálculo de carência por animal (WithdrawalPeriod) — Passo 9.4 - Titan Livestock.

Monta a situação de carência a partir das aplicações de tratamento do animal,
resolvendo lote → medicamento para obter o prazo, e ignorando aplicações
superseded por uma correção (o registro corrigido não conta; conta a correção).
"""

from dataclasses import dataclass

from packages.livestock_application.medication_service import (
    MedicationBatchRepositoryPort,
    MedicationRepositoryPort,
)
from packages.livestock_application.treatment_service import (
    TreatmentApplicationRepositoryPort,
)
from packages.livestock_domain.treatment import TreatmentApplication
from packages.livestock_domain.withdrawal import (
    AnimalWithdrawalStatus,
    WithdrawalContribution,
    build_animal_withdrawal_status,
)
from packages.shared_kernel import OrganizationId, TypedId


@dataclass(frozen=True, slots=True)
class WithdrawalCalculator:
    application_repository: TreatmentApplicationRepositoryPort
    batch_repository: MedicationBatchRepositoryPort
    medication_repository: MedicationRepositoryPort

    def assess_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> AnimalWithdrawalStatus:
        applications = self.application_repository.list_by_animal(organization_id, animal_id)
        contributions = tuple(
            self._contribution_of(organization_id, application)
            for application in _effective(applications)
        )
        return build_animal_withdrawal_status(animal_id, contributions)

    def _contribution_of(
        self, organization_id: OrganizationId, application: TreatmentApplication
    ) -> WithdrawalContribution:
        batch = self.batch_repository.get_by_id(application.medication_batch_id)
        if batch is None or batch.organization_id != organization_id:
            raise KeyError(
                f"Lote '{application.medication_batch_id.value}' da aplicação "
                f"'{application.application_id.value}' não encontrado."
            )
        medication = self.medication_repository.get_by_id(batch.medication_id)
        if medication is None or medication.organization_id != organization_id:
            raise KeyError(
                f"Medicamento '{batch.medication_id.value}' do lote "
                f"'{batch.batch_id.value}' não encontrado."
            )
        # O prazo é congelado aqui: o snapshot vive na contribuição, não numa
        # releitura futura do medicamento.
        return WithdrawalContribution.create(
            application_id=application.application_id,
            medication_batch_id=application.medication_batch_id,
            applied_at=application.applied_at,
            withdrawal_period_days=medication.withdrawal_period_days,
        )


def _effective(applications: list[TreatmentApplication]) -> list[TreatmentApplication]:
    """Descarta aplicações corrigidas: a que foi apontada por uma correção não conta."""
    superseded = {
        application.corrects_application_id
        for application in applications
        if application.corrects_application_id is not None
    }
    return [
        application for application in applications if application.application_id not in superseded
    ]
