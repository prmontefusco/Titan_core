from datetime import UTC, datetime, timedelta

import pytest

from packages.livestock_domain.entity_type_request import (
    EntityKind,
    EntityTypeRequest,
    EntityTypeRequestJaDecidido,
    EntityTypeRequestStatus,
)
from packages.shared_kernel import OrganizationId, TypedId


def _submit() -> EntityTypeRequest:
    return EntityTypeRequest.submit(
        organization_id=OrganizationId.new(),
        requested_kind=EntityKind.PRODUTOR,
        requested_by_user_id=TypedId.new("user"),
        requested_at=datetime.now(UTC),
    )


def test_submit_cria_pedido_pendente_sem_decisao() -> None:
    pedido = _submit()

    assert pedido.status is EntityTypeRequestStatus.PENDENTE
    assert pedido.decided_at is None
    assert pedido.decided_by_actor_id is None
    assert pedido.decision_reason is None


def test_approve_transiciona_para_aprovada() -> None:
    pedido = _submit()
    decidido_em = pedido.requested_at + timedelta(minutes=5)

    aprovado = pedido.approve(decided_at=decidido_em, decided_by_actor_id=TypedId.new("actor"))

    assert aprovado.status is EntityTypeRequestStatus.APROVADA
    assert aprovado.decided_at == decidido_em
    assert aprovado.decision_reason is None
    assert pedido.status is EntityTypeRequestStatus.PENDENTE  # imutavel


def test_deny_exige_motivo_nao_vazio() -> None:
    pedido = _submit()

    with pytest.raises(ValueError, match="reason"):
        pedido.deny(
            decided_at=pedido.requested_at,
            decided_by_actor_id=TypedId.new("actor"),
            reason="   ",
        )


def test_deny_transiciona_para_negada_com_motivo() -> None:
    pedido = _submit()

    negado = pedido.deny(
        decided_at=pedido.requested_at,
        decided_by_actor_id=TypedId.new("actor"),
        reason="  Sem vinculo comprovado com a Organization.  ",
    )

    assert negado.status is EntityTypeRequestStatus.NEGADA
    assert negado.decision_reason == "Sem vinculo comprovado com a Organization."


def test_nao_pode_decidir_pedido_ja_decidido() -> None:
    pedido = _submit()
    aprovado = pedido.approve(
        decided_at=pedido.requested_at, decided_by_actor_id=TypedId.new("actor")
    )

    with pytest.raises(EntityTypeRequestJaDecidido):
        aprovado.approve(decided_at=pedido.requested_at, decided_by_actor_id=TypedId.new("actor"))

    with pytest.raises(EntityTypeRequestJaDecidido):
        aprovado.deny(
            decided_at=pedido.requested_at,
            decided_by_actor_id=TypedId.new("actor"),
            reason="motivo",
        )


def test_decided_at_nao_pode_ser_anterior_a_requested_at() -> None:
    pedido = _submit()

    with pytest.raises(ValueError, match="decided_at"):
        EntityTypeRequest(
            request_id=pedido.request_id,
            organization_id=pedido.organization_id,
            requested_kind=pedido.requested_kind,
            requested_by_user_id=pedido.requested_by_user_id,
            status=EntityTypeRequestStatus.APROVADA,
            requested_at=pedido.requested_at,
            decided_at=pedido.requested_at - timedelta(seconds=1),
            decided_by_actor_id=TypedId.new("actor"),
        )


def test_pendente_nao_pode_carregar_decisao() -> None:
    pedido = _submit()

    with pytest.raises(ValueError, match="PENDENTE"):
        EntityTypeRequest(
            request_id=pedido.request_id,
            organization_id=pedido.organization_id,
            requested_kind=pedido.requested_kind,
            requested_by_user_id=pedido.requested_by_user_id,
            status=EntityTypeRequestStatus.PENDENTE,
            requested_at=pedido.requested_at,
            decided_at=pedido.requested_at,
            decided_by_actor_id=TypedId.new("actor"),
        )
