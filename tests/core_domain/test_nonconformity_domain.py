"""Testes unitários do ciclo de vida de NonConformity (Passo 7.3)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_domain.nonconformity import (
    NonConformity,
    NonConformityOrigin,
    NonConformityStatus,
)
from packages.core_domain.rule import SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _ref(org_id: OrganizationId | None, entity_type: str = "batch") -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new(entity_type), organization_id=org_id, contract_version=1
    )


def _detect(org_id: OrganizationId, at: datetime) -> NonConformity:
    return NonConformity.detect(
        organization_id=org_id,
        subject_reference=_ref(org_id),
        origin=NonConformityOrigin.REGRA_NAO_ATENDIDA,
        severity=SeverityLevel.BLOCKING,
        description="Regra 'rule-atestado' não atendida.",
        detected_at=at,
        corrective_action="Reemitir o atestado.",
    )


def _ate_reavaliacao(org_id: OrganizationId, t0: datetime) -> NonConformity:
    nc = _detect(org_id, t0)
    nc = nc.classify(t0 + timedelta(hours=1))
    nc = nc.assign(_ref(org_id, "user"), t0 + timedelta(days=7), t0 + timedelta(hours=2))
    nc = nc.start_correction(t0 + timedelta(hours=3))
    return nc.submit_for_reevaluation([_ref(org_id, "evidence")], t0 + timedelta(days=1))


def test_detection_starts_history() -> None:
    org_id = OrganizationId.new()
    nc = _detect(org_id, datetime.now(UTC))

    assert nc.status is NonConformityStatus.DETECTADA
    assert len(nc.history()) == 1
    assert nc.history()[0].from_status is None


def test_full_lifecycle_preserves_every_transition() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    nc = _ate_reavaliacao(org_id, t0)
    nc = nc.close(TypedId.new("evaluation"), t0 + timedelta(days=2))

    assert nc.status is NonConformityStatus.ENCERRADA
    assert nc.is_closed
    assert nc.closed_at is not None

    # Encerramento nunca remove histórico: as seis etapas seguem registradas.
    percurso = [t.to_status for t in nc.history()]
    assert percurso == [
        NonConformityStatus.DETECTADA,
        NonConformityStatus.CLASSIFICADA,
        NonConformityStatus.ATRIBUIDA,
        NonConformityStatus.EM_CORRECAO,
        NonConformityStatus.PRONTA_PARA_REAVALIACAO,
        NonConformityStatus.ENCERRADA,
    ]


def test_transitions_cannot_skip_steps() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    nc = _detect(org_id, t0)

    with pytest.raises(ValueError, match="Transição inválida"):
        nc.start_correction(t0)

    with pytest.raises(ValueError, match="Transição inválida"):
        nc.close(TypedId.new("evaluation"), t0)


def test_closed_nonconformity_is_terminal() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    nc = _ate_reavaliacao(org_id, t0).close(TypedId.new("evaluation"), t0 + timedelta(days=2))

    with pytest.raises(ValueError, match="Transição inválida"):
        nc.start_correction(t0 + timedelta(days=3))


def test_reevaluation_can_send_the_case_back_to_correction() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    nc = _ate_reavaliacao(org_id, t0)

    devolvida = nc.reject_reevaluation(
        t0 + timedelta(days=2), note="Atestado reenviado continua reprovado."
    )
    assert devolvida.status is NonConformityStatus.EM_CORRECAO
    # A ida à reavaliação permanece no histórico, mesmo tendo sido rejeitada.
    assert NonConformityStatus.PRONTA_PARA_REAVALIACAO in [t.to_status for t in devolvida.history()]
    assert len(devolvida.history()) == len(nc.history()) + 1


def test_rejecting_reevaluation_requires_justification() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    nc = _ate_reavaliacao(org_id, t0)

    with pytest.raises(ValueError, match="exige justificativa"):
        nc.reject_reevaluation(t0 + timedelta(days=2), note="   ")


def test_reevaluation_requires_correction_evidence() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    nc = _detect(org_id, t0).classify(t0)
    nc = nc.assign(_ref(org_id, "user"), t0 + timedelta(days=7), t0)
    nc = nc.start_correction(t0)

    with pytest.raises(ValueError, match="ao menos uma evidência de correção"):
        nc.submit_for_reevaluation([], t0 + timedelta(days=1))


def test_closure_requires_an_evaluation_reference() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    nc = _ate_reavaliacao(org_id, t0)

    with pytest.raises(ValueError, match="exige a Evaluation"):
        nc.close(TypedId.new("batch"), t0 + timedelta(days=2))


def test_subject_and_responsible_must_belong_to_the_organization() -> None:
    org_id = OrganizationId.new()
    outra_org = OrganizationId.new()
    t0 = datetime.now(UTC)

    with pytest.raises(ValueError, match="pertence a outra Organization"):
        NonConformity.detect(
            organization_id=org_id,
            subject_reference=_ref(outra_org),
            origin=NonConformityOrigin.REGRA_NAO_ATENDIDA,
            severity=SeverityLevel.BLOCKING,
            description="x",
            detected_at=t0,
        )

    nc = _detect(org_id, t0).classify(t0)
    with pytest.raises(ValueError, match="responsável pertence a outra Organization"):
        nc.assign(_ref(outra_org, "user"), t0 + timedelta(days=7), t0)


def test_roundtrips_through_dict_with_full_history() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    nc = _ate_reavaliacao(org_id, t0).close(TypedId.new("evaluation"), t0 + timedelta(days=2))

    restaurada = NonConformity.from_dict(nc.to_dict())
    assert restaurada == nc
    assert len(restaurada.history()) == 6


def test_nonconformity_is_immutable() -> None:
    nc = _detect(OrganizationId.new(), datetime.now(UTC))
    with pytest.raises(AttributeError):
        nc.status = NonConformityStatus.ENCERRADA  # type: ignore[misc]
