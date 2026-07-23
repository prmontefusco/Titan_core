"""Testes unitarios para governanca de quarentena e servico de replay (ADR-0038/Passo 4.9C)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from packages.core_application.inbox import (
    InboxQuarantineRepositoryPort,
    InboxQuarantineService,
    ReplayRequest,
    ReplayResult,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def test_replay_request_requires_non_empty_reason() -> None:
    org_id = OrganizationId.new()
    operator_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )

    with pytest.raises(ValueError, match="Justificativa e obrigatoria"):
        ReplayRequest(
            quarantine_id=TypedId.new("quarantine"),
            operator_actor_reference=operator_ref,
            reason="",
        )


def test_inbox_quarantine_service_delegates_list_and_replay() -> None:
    repo = MagicMock(spec=InboxQuarantineRepositoryPort)
    service = InboxQuarantineService(repository=repo)

    org_id = OrganizationId.new()
    operator_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )

    request = ReplayRequest(
        quarantine_id=TypedId.new("quarantine"),
        operator_actor_reference=operator_ref,
        reason="Correcao de contrato concluida",
    )

    expected_result = ReplayResult(
        quarantine_id=request.quarantine_id,
        status="REQUEUED",
        processed_at=datetime.now(UTC),
        reason="Replay autorizado pelo operador",
    )
    repo.replay_message.return_value = expected_result

    result = service.replay(request)

    assert result.status == "REQUEUED"
    repo.replay_message.assert_called_once_with(request)
