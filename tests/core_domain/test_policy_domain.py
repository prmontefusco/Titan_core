"""Testes unitários do modelo de domínio para Políticas Versionadas (Passo 6.1)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_domain.policy import Policy, PolicyStatus
from packages.shared_kernel import OrganizationId, TypedId


def test_policy_creation_and_post_init_invariants() -> None:
    org_id = OrganizationId.new()
    policy = Policy.create_draft(
        organization_id=org_id,
        code="pol-vacinacao-2026",
        name="Política de Vacinação Sanitária",
        description="Regras de imunização obrigatória de rebanhos bovinos.",
    )

    assert policy.code == "pol-vacinacao-2026"
    assert policy.version == 1
    assert policy.status == PolicyStatus.DRAFT
    assert policy.published_at is None

    with pytest.raises(ValueError, match="code de Policy deve ser uma string não vazia"):
        Policy.create_draft(organization_id=org_id, code="   ", name="Test")

    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="valid_to não pode ser anterior a valid_from"):
        Policy(
            policy_id=TypedId.new("policy"),
            organization_id=org_id,
            code="pol-invalid",
            name="Invalid Policy",
            description="Test",
            valid_from=now,
            valid_to=now - timedelta(days=1),
        )


def test_policy_lifecycle_transitions() -> None:
    org_id = OrganizationId.new()
    draft = Policy.create_draft(
        organization_id=org_id,
        code="pol-rastreabilidade",
        name="Política de Rastreabilidade",
    )

    # 1. Publicação
    published = draft.publish()
    assert published.status == PolicyStatus.PUBLISHED
    assert published.published_at is not None

    with pytest.raises(ValueError, match="Apenas políticas em RASCUNHO podem ser publicadas"):
        published.publish()

    # 2. Nova versão a partir da publicada
    v2_draft = published.create_next_version(name="Política de Rastreabilidade v2")
    assert v2_draft.version == 2
    assert v2_draft.status == PolicyStatus.DRAFT
    assert v2_draft.published_at is None

    # 3. Substituição (Supersede)
    superseded = published.supersede()
    assert superseded.status == PolicyStatus.SUPERSEDED

    # 4. Revogação
    revoked = superseded.revoke()
    assert revoked.status == PolicyStatus.REVOKED

    with pytest.raises(ValueError, match="já foi revogada"):
        revoked.revoke()
