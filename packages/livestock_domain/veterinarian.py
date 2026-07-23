"""Entidade de domínio Veterinarian (Passo 8.5 - Titan Livestock)."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from packages.livestock_domain.animal import VerificationStatus
from packages.shared_kernel import OrganizationId, TypedId


@dataclass(frozen=True, slots=True)
class Veterinarian:
    veterinarian_id: TypedId
    organization_id: OrganizationId
    name: str
    cpf: str
    council_number: str
    council_state: str
    verification_status: VerificationStatus = VerificationStatus.DECLARADO
    evidence_reference: str | None = None
    created_at: datetime = datetime.now(UTC)

    def __post_init__(self) -> None:
        if self.veterinarian_id.entity_type != "veterinarian":
            raise ValueError(
                "veterinarian_id deve ter entity_type 'veterinarian', recebido "
                f"'{self.veterinarian_id.entity_type}'."
            )
        if not self.name or not self.name.strip():
            raise ValueError("name do veterinário não pode ser vazio.")

        # Validação simples de formato de CPF (apenas dígitos, 11 caracteres)
        clean_cpf = re.sub(r"\D", "", self.cpf)
        if len(clean_cpf) != 11:
            raise ValueError(f"CPF inválido '{self.cpf}'. Deve conter exatamente 11 dígitos.")

        if not self.council_number or not self.council_number.strip():
            raise ValueError("council_number não pode ser vazio.")

        c_state = self.council_state.upper()
        if len(c_state) != 2:
            raise ValueError(
                f"council_state inválido '{self.council_state}'. Deve ter 2 letras (ex: 'SP')."
            )
