"""Testes unitários para VeterinarianService (Passo 8.5 - Titan Livestock)."""

from uuid import uuid4

import pytest

from packages.livestock_application.veterinarian_service import (
    VeterinarianRepositoryPort,
    VeterinarianService,
)
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.veterinarian import Veterinarian
from packages.shared_kernel import OrganizationId, TypedId


class InMemoryVeterinarianRepo(VeterinarianRepositoryPort):
    def __init__(self) -> None:
        self.vets: dict[str, Veterinarian] = {}

    def save(self, vet: Veterinarian) -> None:
        self.vets[vet.veterinarian_id.value.hex] = vet

    def update(self, vet: Veterinarian) -> None:
        self.vets[vet.veterinarian_id.value.hex] = vet

    def get_by_id(self, vet_id: TypedId) -> Veterinarian | None:
        return self.vets.get(vet_id.value.hex)

    def get_by_cpf(self, organization_id: OrganizationId, cpf: str) -> Veterinarian | None:
        for v in self.vets.values():
            if v.organization_id == organization_id and v.cpf == cpf:
                return v
        return None

    def get_by_council(
        self, organization_id: OrganizationId, state: str, number: str
    ) -> Veterinarian | None:
        for v in self.vets.values():
            if (
                v.organization_id == organization_id
                and v.council_state == state
                and v.council_number == number
            ):
                return v
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Veterinarian]:
        return [v for v in self.vets.values() if v.organization_id == organization_id]


def test_veterinarian_registration_and_evidence_attachment() -> None:
    org_id = OrganizationId(uuid4())
    repo = InMemoryVeterinarianRepo()
    service = VeterinarianService(repository=repo)

    # 1. Cadastra veterinário (inicia como DECLARADO)
    vet = service.register_veterinarian(
        organization_id=org_id,
        name="Dra. Maria Souza",
        cpf="123.456.789-01",
        council_number="98765",
        council_state="SP",
    )

    assert vet.cpf == "12345678901"
    assert vet.verification_status == VerificationStatus.DECLARADO

    # 2. Anexa evidência (promove para DOCUMENTADO)
    updated = service.attach_evidence(
        veterinarian_id=vet.veterinarian_id,
        evidence_reference="evidence:crmv-card-pdf-123",
    )

    assert updated.evidence_reference == "evidence:crmv-card-pdf-123"
    assert updated.verification_status == VerificationStatus.DOCUMENTADO

    # 3. Promove para VERIFICADO_EM_FONTE
    verified = service.update_verification_status(
        veterinarian_id=vet.veterinarian_id,
        new_status=VerificationStatus.VERIFICADO_EM_FONTE,
    )
    assert verified.verification_status == VerificationStatus.VERIFICADO_EM_FONTE

    # 4. Testar recusa de CRMV duplicado na mesma organização
    with pytest.raises(ValueError, match="Já existe um veterinário com o CRMV"):
        service.register_veterinarian(
            organization_id=org_id,
            name="Outro Dr. Silva",
            cpf="999.888.777-66",
            council_number="98765",
            council_state="SP",
        )
