"""Serviço de aplicação VeterinarianService (Passo 8.5 - Titan Livestock)."""

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.veterinarian import Veterinarian
from packages.shared_kernel import OrganizationId, TypedId


class VeterinarianRepositoryPort(Protocol):
    def save(self, vet: Veterinarian) -> None: ...

    def update(self, vet: Veterinarian) -> None: ...

    def get_by_id(self, vet_id: TypedId) -> Veterinarian | None: ...

    def get_by_cpf(self, organization_id: OrganizationId, cpf: str) -> Veterinarian | None: ...

    def get_by_council(
        self, organization_id: OrganizationId, state: str, number: str
    ) -> Veterinarian | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Veterinarian]: ...


@dataclass(frozen=True, slots=True)
class VeterinarianService:
    repository: VeterinarianRepositoryPort

    def register_veterinarian(
        self,
        organization_id: OrganizationId,
        name: str,
        cpf: str,
        council_number: str,
        council_state: str,
    ) -> Veterinarian:
        clean_cpf = re.sub(r"\D", "", cpf)
        c_number = council_number.strip()
        c_state = council_state.strip().upper()

        existing_cpf = self.repository.get_by_cpf(organization_id, clean_cpf)
        if existing_cpf is not None:
            raise ValueError(
                f"Já existe um veterinário com o CPF '{clean_cpf}' cadastrado para a "
                f"organização {organization_id.value}."
            )

        existing_council = self.repository.get_by_council(organization_id, c_state, c_number)
        if existing_council is not None:
            raise ValueError(
                f"Já existe um veterinário com o CRMV '{c_state}-{c_number}' cadastrado para a "
                f"organização {organization_id.value}."
            )

        vet = Veterinarian(
            veterinarian_id=TypedId.new("veterinarian"),
            organization_id=organization_id,
            name=name,
            cpf=clean_cpf,
            council_number=c_number,
            council_state=c_state,
            verification_status=VerificationStatus.DECLARADO,
            created_at=datetime.now(UTC),
        )

        self.repository.save(vet)
        return vet

    def attach_evidence(
        self,
        veterinarian_id: TypedId,
        evidence_reference: str,
    ) -> Veterinarian:
        vet = self.repository.get_by_id(veterinarian_id)
        if vet is None:
            raise KeyError(f"Veterinário '{veterinarian_id.value}' não encontrado.")

        updated_vet = replace(
            vet,
            evidence_reference=evidence_reference,
            verification_status=VerificationStatus.DOCUMENTADO,
        )
        self.repository.update(updated_vet)
        return updated_vet

    def update_verification_status(
        self,
        veterinarian_id: TypedId,
        new_status: VerificationStatus,
        evidence_reference: str | None = None,
    ) -> Veterinarian:
        vet = self.repository.get_by_id(veterinarian_id)
        if vet is None:
            raise KeyError(f"Veterinário '{veterinarian_id.value}' não encontrado.")

        e_ref = evidence_reference if evidence_reference is not None else vet.evidence_reference
        updated_vet = replace(
            vet,
            verification_status=new_status,
            evidence_reference=e_ref,
        )
        self.repository.update(updated_vet)
        return updated_vet
