"""Testes de aplicação para o RuleEvaluationEngine determinístico (Passo 6.4)."""

from datetime import UTC, datetime, timedelta

from packages.core_application.evaluation_service import RuleEvaluationEngine
from packages.core_domain.evaluation import RuleResultStatus
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId


def _snapshot(
    org_id: OrganizationId,
    subject_id: TypedId,
    as_of: datetime,
    fact_types: tuple[str, ...],
    payloads: dict[str, dict[str, object]] | None = None,
) -> FactSnapshot:
    payloads = payloads or {}
    facts = [
        Fact.create(fact_type=ft, payload=payloads.get(ft, {"n": i}), observed_at=as_of)
        for i, ft in enumerate(fact_types)
    ]
    return FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=as_of,
        facts=facts,
    )


def _rule(
    org_id: OrganizationId,
    required: tuple[str, ...] = (),
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    conditions: tuple[RuleCondition, ...] = (),
) -> Rule:
    return Rule.create(
        policy_id=TypedId.new("policy"),
        organization_id=org_id,
        code="rule-exame-brucelose",
        name="Exame de Brucelose",
        description="Exige atestado sanitário",
        severity=SeverityLevel.BLOCKING,
        required_evidence_types=required,
        conditions=conditions,
        corrective_action="Coletar e anexar o atestado sanitário do lote.",
        valid_from=valid_from,
        valid_to=valid_to,
    )


def test_rule_satisfied_when_required_evidence_present() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(org_id, required=("sanitary.attestation",))
    snapshot = _snapshot(org_id, subject_id, now, ("sanitary.attestation", "transport.gta"))

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.ATENDIDA
    assert result.missing_evidence_types == ()
    assert result.corrective_action == ""
    assert result.reason.strip() != ""
    assert result.snapshot_hash == snapshot.snapshot_hash


def test_rule_pending_when_required_evidence_missing() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(org_id, required=("sanitary.attestation", "transport.gta"))
    snapshot = _snapshot(org_id, subject_id, now, ("transport.gta",))

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.PENDENTE
    assert result.missing_evidence_types == ("sanitary.attestation",)
    # Regra não atendida propaga a ação corretiva declarada.
    assert result.corrective_action == "Coletar e anexar o atestado sanitário do lote."


def test_rule_not_applicable_before_valid_from() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(org_id, required=("sanitary.attestation",), valid_from=now + timedelta(days=10))
    snapshot = _snapshot(org_id, subject_id, now, ())

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.NAO_APLICAVEL
    assert result.missing_evidence_types == ()


def test_rule_not_applicable_after_valid_to() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(org_id, required=("sanitary.attestation",), valid_to=now - timedelta(days=1))
    snapshot = _snapshot(org_id, subject_id, now, ("sanitary.attestation",))

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.NAO_APLICAVEL


def test_evaluation_is_deterministic_same_inputs_same_hash() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(org_id, required=("sanitary.attestation",))
    snapshot = _snapshot(org_id, subject_id, now, ("sanitary.attestation",))

    engine = RuleEvaluationEngine()
    r1 = engine.evaluate(rule, snapshot)
    r2 = engine.evaluate(rule, snapshot)

    assert r1.inputs_hash == r2.inputs_hash
    assert r1.status == r2.status
    # A identidade do resultado muda a cada execução, mas o hash das entradas é estável.
    assert r1.result_id != r2.result_id


def _attestation_condition(expected: str = "approved") -> RuleCondition:
    return RuleCondition(
        fact_type="sanitary.attestation",
        payload_key="result",
        operator=ComparisonOperator.EQUALS,
        expected_value=expected,
        description="Atestado sanitário deve estar aprovado",
    )


def test_rule_failed_when_declared_condition_is_violated() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(
        org_id,
        required=("sanitary.attestation",),
        conditions=(_attestation_condition(),),
    )
    snapshot = _snapshot(
        org_id,
        subject_id,
        now,
        ("sanitary.attestation",),
        payloads={"sanitary.attestation": {"result": "rejected"}},
    )

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.NAO_ATENDIDA
    assert "Atestado sanitário deve estar aprovado" in result.reason
    assert result.corrective_action == "Coletar e anexar o atestado sanitário do lote."


def test_rule_satisfied_when_declared_condition_holds() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(
        org_id,
        required=("sanitary.attestation",),
        conditions=(_attestation_condition(),),
    )
    snapshot = _snapshot(
        org_id,
        subject_id,
        now,
        ("sanitary.attestation",),
        payloads={"sanitary.attestation": {"result": "approved"}},
    )

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.ATENDIDA
    assert result.corrective_action == ""


def test_condition_over_absent_fact_is_pending_not_failure() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(org_id, conditions=(_attestation_condition(),))
    snapshot = _snapshot(org_id, subject_id, now, ("transport.gta",))

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.PENDENTE
    assert result.missing_evidence_types == ("sanitary.attestation",)


def test_condition_over_missing_payload_key_is_indeterminate() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(org_id, conditions=(_attestation_condition(),))
    snapshot = _snapshot(
        org_id,
        subject_id,
        now,
        ("sanitary.attestation",),
        payloads={"sanitary.attestation": {"emitido_por": "vet-123"}},
    )

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.INDETERMINADA
    assert "key_missing" in result.reason


def test_condition_with_incomparable_type_is_indeterminate() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(
        org_id,
        conditions=(
            RuleCondition(
                fact_type="livestock.weight_record",
                payload_key="average_weight_kg",
                operator=ComparisonOperator.GREATER_OR_EQUAL,
                expected_value=450,
            ),
        ),
    )
    snapshot = _snapshot(
        org_id,
        subject_id,
        now,
        ("livestock.weight_record",),
        payloads={"livestock.weight_record": {"average_weight_kg": "indisponível"}},
    )

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.INDETERMINADA
    assert "incomparable" in result.reason


def test_definitive_violation_takes_precedence_over_gaps() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(
        org_id,
        conditions=(
            _attestation_condition(),
            RuleCondition(
                fact_type="transport.gta",
                payload_key="numero",
                operator=ComparisonOperator.EQUALS,
                expected_value="123",
            ),
        ),
    )
    # Condição 1 viola; condição 2 nem tem fato disponível.
    snapshot = _snapshot(
        org_id,
        subject_id,
        now,
        ("sanitary.attestation",),
        payloads={"sanitary.attestation": {"result": "rejected"}},
    )

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.NAO_ATENDIDA


def test_condition_uses_latest_fact_of_its_type() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(org_id, conditions=(_attestation_condition(),))
    antigo = Fact.create(
        fact_type="sanitary.attestation",
        payload={"result": "rejected"},
        observed_at=now - timedelta(days=30),
    )
    recente = Fact.create(
        fact_type="sanitary.attestation",
        payload={"result": "approved"},
        observed_at=now,
    )
    snapshot = FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=now,
        facts=[antigo, recente],
    )

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.ATENDIDA


def test_not_applicable_rule_does_not_demand_corrective_action() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(org_id, valid_to=now - timedelta(days=1))
    snapshot = _snapshot(org_id, subject_id, now, ())

    result = RuleEvaluationEngine().evaluate(rule, snapshot)

    assert result.status == RuleResultStatus.NAO_APLICAVEL
    assert result.corrective_action == ""


def test_inputs_hash_changes_when_conditions_change() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    snapshot = _snapshot(
        org_id,
        subject_id,
        now,
        ("sanitary.attestation",),
        payloads={"sanitary.attestation": {"result": "approved"}},
    )

    engine = RuleEvaluationEngine()
    sem_condicao = engine.evaluate(_rule(org_id), snapshot)
    com_condicao = engine.evaluate(_rule(org_id, conditions=(_attestation_condition(),)), snapshot)

    assert sem_condicao.inputs_hash != com_condicao.inputs_hash


def test_condition_evaluation_is_deterministic() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)

    rule = _rule(org_id, conditions=(_attestation_condition(),))
    snapshot = _snapshot(
        org_id,
        subject_id,
        now,
        ("sanitary.attestation",),
        payloads={"sanitary.attestation": {"result": "rejected"}},
    )

    engine = RuleEvaluationEngine()
    r1 = engine.evaluate(rule, snapshot)
    r2 = engine.evaluate(rule, snapshot)

    assert r1.status == r2.status == RuleResultStatus.NAO_ATENDIDA
    assert r1.inputs_hash == r2.inputs_hash
    assert r1.reason == r2.reason


def test_evaluation_hash_reflects_snapshot_content() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    rule = _rule(org_id, required=("sanitary.attestation",))

    snap_with = _snapshot(org_id, subject_id, now, ("sanitary.attestation",))
    snap_without = _snapshot(org_id, subject_id, now, ("transport.gta",))

    engine = RuleEvaluationEngine()
    assert (
        engine.evaluate(rule, snap_with).inputs_hash
        != engine.evaluate(rule, snap_without).inputs_hash
    )
