"""Testes unitários do modelo de domínio para Regras Versionadas (Passo 6.2)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_domain.rule import Rule, SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId


def test_rule_creation_and_invariants() -> None:
    policy_id = TypedId.new("policy")
    org_id = OrganizationId.new()

    rule = Rule.create(
        policy_id=policy_id,
        organization_id=org_id,
        code="rule-vacina-aftosa",
        name="Exigência de Vacina Aftosa",
        description="Lote de bovinos deve ter atestado de vacinação.",
        severity=SeverityLevel.BLOCKING,
        normative_source="IN-MAPA 48/2020",
        required_evidence_types=("laudo_pdf", "assinatura_digital"),
        justification="Prevenção de epizootia",
        corrective_action="Anexar comprovante emitido pela ADAB",
    )

    assert rule.code == "rule-vacina-aftosa"
    assert rule.version == 1
    assert rule.severity == SeverityLevel.BLOCKING
    assert rule.required_evidence_types == ("laudo_pdf", "assinatura_digital")

    with pytest.raises(ValueError, match="code de Rule deve ser uma string não vazia"):
        Rule.create(
            policy_id=policy_id,
            organization_id=org_id,
            code="  ",
            name="Invalid Rule",
        )

    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="valid_to não pode ser anterior a valid_from"):
        Rule(
            rule_id=TypedId.new("rule"),
            policy_id=policy_id,
            organization_id=org_id,
            code="rule-invalid",
            name="Rule Invalid",
            description="",
            valid_from=now,
            valid_to=now - timedelta(days=1),
        )


def test_rule_next_version() -> None:
    policy_id = TypedId.new("policy")
    org_id = OrganizationId.new()

    r1 = Rule.create(
        policy_id=policy_id,
        organization_id=org_id,
        code="rule-lote-minimo",
        name="Tamanho Mínimo de Lote",
        severity=SeverityLevel.WARNING,
    )
    assert r1.version == 1

    r2 = r1.create_next_version(name="Tamanho Mínimo de Lote v2", severity=SeverityLevel.CRITICAL)
    assert r2.version == 2
    assert r2.code == "rule-lote-minimo"
    assert r2.severity == SeverityLevel.CRITICAL
