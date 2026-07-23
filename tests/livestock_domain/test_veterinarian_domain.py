"""Testes unitários de domínio para Veterinarian (Passo 8.5 - Titan Livestock)."""

from uuid import uuid4

import pytest

from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.veterinarian import Veterinarian
from packages.shared_kernel import OrganizationId, TypedId


def test_veterinarian_creation_success() -> None:
    org_id = OrganizationId(uuid4())
    vet_id = TypedId.new("veterinarian")

    vet = Veterinarian(
        veterinarian_id=vet_id,
        organization_id=org_id,
        name="Dr. João Silva",
        cpf="12345678901",
        council_number="12345",
        council_state="SP",
        verification_status=VerificationStatus.DECLARADO,
    )

    assert vet.name == "Dr. João Silva"
    assert vet.cpf == "12345678901"
    assert vet.council_number == "12345"
    assert vet.council_state == "SP"
    assert vet.verification_status == VerificationStatus.DECLARADO


def test_veterinarian_cpf_validation() -> None:
    org_id = OrganizationId(uuid4())
    vet_id = TypedId.new("veterinarian")

    with pytest.raises(ValueError, match="CPF inválido"):
        Veterinarian(
            veterinarian_id=vet_id,
            organization_id=org_id,
            name="Dr. Erro CPF",
            cpf="12345",
            council_number="12345",
            council_state="SP",
        )
