"""Testes unitários para VeterinarianService (Passo 8.5 - Titan Livestock)."""

import pytest

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.veterinarian_service import (
    VeterinarianRepositoryPort,
    VeterinarianService,
)
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_domain.events import (
    VETERINARIAN_REGISTERED,
    VETERINARIAN_STATUS_UPDATED,
)
from packages.livestock_domain.veterinarian import Veterinarian
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog


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


def test_veterinarian_registration_and_evidence_attachment(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    service = VeterinarianService(repository=InMemoryVeterinarianRepo(), recorder=recorder)

    # 1. Cadastra veterinário (inicia como DECLARADO)
    vet = service.register_veterinarian(
        context=context,
        name="Dra. Maria Souza",
        cpf="123.456.789-01",
        council_number="98765",
        council_state="SP",
    )

    assert vet.cpf == "12345678901"
    assert vet.verification_status == VerificationStatus.DECLARADO

    # 2. Anexa evidência (promove para DOCUMENTADO)
    updated = service.attach_evidence(
        context=context,
        veterinarian_id=vet.veterinarian_id,
        evidence_reference="evidence:crmv-card-pdf-123",
    )

    assert updated.evidence_reference == "evidence:crmv-card-pdf-123"
    assert updated.verification_status == VerificationStatus.DOCUMENTADO

    # 3. Promove para VERIFICADO_EM_FONTE
    verified = service.update_verification_status(
        context=context,
        veterinarian_id=vet.veterinarian_id,
        new_status=VerificationStatus.VERIFICADO_EM_FONTE,
    )
    assert verified.verification_status == VerificationStatus.VERIFICADO_EM_FONTE

    # 4. Testar recusa de CRMV duplicado na mesma organização
    with pytest.raises(ValueError, match="Já existe um veterinário com o CRMV"):
        service.register_veterinarian(
            context=context,
            name="Outro Dr. Silva",
            cpf="999.888.777-66",
            council_number="98765",
            council_state="SP",
        )


def test_each_promotion_is_recorded_with_the_status_it_left_behind(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """Guardar o status anterior é o que permite ler a promoção sem o estado atual."""
    service = VeterinarianService(repository=InMemoryVeterinarianRepo(), recorder=recorder)
    vet = service.register_veterinarian(
        context=context,
        name="Dra. Maria Souza",
        cpf="123.456.789-01",
        council_number="98765",
        council_state="SP",
    )

    service.attach_evidence(
        context=context,
        veterinarian_id=vet.veterinarian_id,
        evidence_reference="evidence:crmv-card-pdf-123",
    )
    service.update_verification_status(
        context=context,
        veterinarian_id=vet.veterinarian_id,
        new_status=VerificationStatus.VERIFICADO_EM_FONTE,
    )

    assert event_log.types() == [
        VETERINARIAN_REGISTERED,
        VETERINARIAN_STATUS_UPDATED,
        VETERINARIAN_STATUS_UPDATED,
    ]
    assert [event.aggregate_version for event in event_log.events] == [1, 2, 3]
    promotions = event_log.of_type(VETERINARIAN_STATUS_UPDATED)
    assert b"DECLARADO" in promotions[0].payload.canonical_bytes
    assert b"VERIFICADO_EM_FONTE" in promotions[1].payload.canonical_bytes


def test_cpf_stays_out_of_the_event_payload(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """O log é append-only: dado de pessoa natural que entra nele não sai mais."""
    service = VeterinarianService(repository=InMemoryVeterinarianRepo(), recorder=recorder)

    service.register_veterinarian(
        context=context,
        name="Dra. Maria Souza",
        cpf="123.456.789-01",
        council_number="98765",
        council_state="SP",
    )

    assert b"12345678901" not in event_log.only(VETERINARIAN_REGISTERED).payload.canonical_bytes


def test_refuses_veterinarian_of_another_organization(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service = VeterinarianService(repository=InMemoryVeterinarianRepo(), recorder=recorder)
    vet = service.register_veterinarian(
        context=context,
        name="Dra. Maria Souza",
        cpf="123.456.789-01",
        council_number="98765",
        council_state="SP",
    )
    intruder = LivestockOperationContext.create(
        organization_id=OrganizationId.new(),
        actor_id=TypedId.new("actor"),
        source_id=TypedId.new("system"),
    )

    with pytest.raises(KeyError, match="não encontrado"):
        service.update_verification_status(
            context=intruder,
            veterinarian_id=vet.veterinarian_id,
            new_status=VerificationStatus.VERIFICADO_EM_FONTE,
        )

    assert event_log.types() == [VETERINARIAN_REGISTERED]


def test_reasserting_the_current_status_records_nothing(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    """O log é append-only: 'DOCUMENTADO → DOCUMENTADO' ficaria lá para sempre."""
    service = VeterinarianService(repository=InMemoryVeterinarianRepo(), recorder=recorder)
    vet = service.register_veterinarian(
        context=context,
        name="Dra. Maria Souza",
        cpf="123.456.789-01",
        council_number="98765",
        council_state="SP",
    )
    service.update_verification_status(
        context=context,
        veterinarian_id=vet.veterinarian_id,
        new_status=VerificationStatus.DOCUMENTADO,
    )

    service.update_verification_status(
        context=context,
        veterinarian_id=vet.veterinarian_id,
        new_status=VerificationStatus.DOCUMENTADO,
    )

    assert event_log.types() == [VETERINARIAN_REGISTERED, VETERINARIAN_STATUS_UPDATED]
