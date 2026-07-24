"""Serviço de aplicação VeterinarianService (Passo 8.5 - Titan Livestock)."""

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.events import (
    VETERINARIAN_REGISTERED,
    VETERINARIAN_STATUS_UPDATED,
    veterinarian_registered_payload,
    veterinarian_status_updated_payload,
)
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
    recorder: LivestockEventRecorder

    def register_veterinarian(
        self,
        context: LivestockOperationContext,
        name: str,
        cpf: str,
        council_number: str,
        council_state: str,
    ) -> Veterinarian:
        organization_id = context.organization_id
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

        created_at = datetime.now(UTC)
        vet = Veterinarian(
            veterinarian_id=TypedId.new("veterinarian"),
            organization_id=organization_id,
            name=name,
            cpf=clean_cpf,
            council_number=c_number,
            council_state=c_state,
            verification_status=VerificationStatus.DECLARADO,
            created_at=created_at,
        )

        self.repository.save(vet)
        self.recorder.record(
            context=context,
            aggregate_id=vet.veterinarian_id,
            event_type=VETERINARIAN_REGISTERED,
            payload=veterinarian_registered_payload(
                veterinarian_id=vet.veterinarian_id,
                name=vet.name,
                council_number=vet.council_number,
                council_state=vet.council_state,
                verification_status=vet.verification_status.value,
            ),
            occurred_at=created_at,
        )
        return vet

    def attach_evidence(
        self,
        context: LivestockOperationContext,
        veterinarian_id: TypedId,
        evidence_reference: str,
    ) -> Veterinarian:
        """Anexar evidência promove o status, e a promoção é o fato registrado."""
        vet = self._owned_veterinarian(context, veterinarian_id)

        updated_vet = replace(
            vet,
            evidence_reference=evidence_reference,
            verification_status=VerificationStatus.DOCUMENTADO,
        )
        self.repository.update(updated_vet)
        self._record_status_change(context, vet, updated_vet)
        return updated_vet

    def update_verification_status(
        self,
        context: LivestockOperationContext,
        veterinarian_id: TypedId,
        new_status: VerificationStatus,
        evidence_reference: str | None = None,
    ) -> Veterinarian:
        vet = self._owned_veterinarian(context, veterinarian_id)

        e_ref = evidence_reference if evidence_reference is not None else vet.evidence_reference
        updated_vet = replace(
            vet,
            verification_status=new_status,
            evidence_reference=e_ref,
        )
        self.repository.update(updated_vet)
        self._record_status_change(context, vet, updated_vet)
        return updated_vet

    def _owned_veterinarian(
        self, context: LivestockOperationContext, veterinarian_id: TypedId
    ) -> Veterinarian:
        vet = self.repository.get_by_id(veterinarian_id)
        if vet is None or vet.organization_id != context.organization_id:
            raise KeyError(f"Veterinário '{veterinarian_id.value}' não encontrado.")
        return vet

    def _record_status_change(
        self,
        context: LivestockOperationContext,
        before: Veterinarian,
        after: Veterinarian,
    ) -> None:
        """Só grava quando o status mudou de fato.

        Reafirmar o status vigente não é um acontecimento, e o log é append-only:
        um evento "DOCUMENTADO → DOCUMENTADO" fica lá para sempre e polui a linha
        do tempo de quem só quer saber quando a habilitação mudou.
        """
        if before.verification_status == after.verification_status:
            return
        self.recorder.record(
            context=context,
            aggregate_id=after.veterinarian_id,
            event_type=VETERINARIAN_STATUS_UPDATED,
            payload=veterinarian_status_updated_payload(
                veterinarian_id=after.veterinarian_id,
                old_status=before.verification_status.value,
                new_status=after.verification_status.value,
                evidence_reference=after.evidence_reference,
            ),
            occurred_at=datetime.now(UTC),
        )
