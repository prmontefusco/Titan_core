"""Invariantes de SharedDecision e da trilha de acesso (BuyerPolicy Fase 3)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.core_domain.policy_sharing import SharedDecision, SharedPolicyAccessLogEntry
from packages.shared_kernel import OrganizationId, TypedId


def _shared_decision(**overrides: object) -> SharedDecision:
    data = {
        "decision_id": TypedId.new("shared_decision"),
        "grant_id": uuid4(),
        "evaluation_id": TypedId.new("evaluation"),
        "policy_id": TypedId.new("policy"),
        "proposer_organization_id": OrganizationId.new(),
        "proposal_content": "Solicito revisao com base na referencia controlada.",
        "proposal_evidence_references": ("doc-123",),
        "proposed_at": datetime.now(UTC),
        "reviewer_organization_id": OrganizationId.new(),
        "status": "PROPOSTA",
        "created_by": str(uuid4()),
        "record_owner_organization_id": OrganizationId.new(),
    }
    data.update(overrides)
    return SharedDecision(**data)  # type: ignore[arg-type]


def test_shared_decision_proposta_valida_nao_tem_revisao() -> None:
    decision = _shared_decision()

    assert decision.status == "PROPOSTA"
    assert decision.review_decision is None


def test_shared_decision_revisada_exige_decisao_conhecida() -> None:
    with pytest.raises(ValueError, match="review_decision"):
        _shared_decision(
            status="REVISADA",
            review_decision="TALVEZ",
            review_content="texto",
            reviewed_at=datetime.now(UTC),
            reviewed_by=str(uuid4()),
        )


def test_shared_decision_revisada_exige_conteudo_e_instante() -> None:
    with pytest.raises(ValueError, match="review_content"):
        _shared_decision(
            status="REVISADA",
            review_decision="APROVADA",
            review_content="",
            reviewed_at=datetime.now(UTC),
            reviewed_by=str(uuid4()),
        )


def test_shared_decision_nao_aceita_evidence_reference_vazia() -> None:
    with pytest.raises(ValueError, match="proposal_evidence_references"):
        _shared_decision(proposal_evidence_references=("doc-1", " "))


def _access_entry(**overrides: object) -> SharedPolicyAccessLogEntry:
    data = {
        "access_id": TypedId.new("shared_policy_access"),
        "grant_id": uuid4(),
        "policy_id": TypedId.new("policy"),
        "organization_id": OrganizationId.new(),
        "action": "EVALUATE",
        "http_status_code": 201,
        "accessed_at": datetime.now(UTC),
        "record_owner_organization_id": OrganizationId.new(),
    }
    data.update(overrides)
    return SharedPolicyAccessLogEntry(**data)  # type: ignore[arg-type]


def test_access_log_registra_acesso_concedido_e_recusado() -> None:
    concedido = _access_entry()
    recusado = _access_entry(action="READ", http_status_code=429)

    assert concedido.http_status_code == 201
    assert recusado.action == "READ"
    assert recusado.http_status_code == 429


def test_access_log_recusa_acao_desconhecida() -> None:
    with pytest.raises(ValueError, match="action"):
        _access_entry(action="EXPORTAR")


def test_access_log_recusa_status_fora_da_faixa_http() -> None:
    with pytest.raises(ValueError, match="http_status_code"):
        _access_entry(http_status_code=42)


def test_access_log_exige_instante_em_utc() -> None:
    with pytest.raises(ValueError, match="accessed_at"):
        _access_entry(accessed_at=datetime.now())
