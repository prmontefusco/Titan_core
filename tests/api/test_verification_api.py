"""Testes do contrato público da API de verificação externa (ADR-0039/Passo 7.7)."""

import json
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.verification import MAX_BODY_BYTES
from packages.core_application.decision_service import DecisionService
from packages.core_application.dossier_service import DossierService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.verification_service import (
    DOSSIER_COMPONENT,
    VerificationBundleService,
)
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.policy import Policy
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.core_domain.verification import SignatureMaterial
from packages.shared_kernel import OrganizationId, TypedId

client = TestClient(app)
ENDPOINT = "/v1/verification/bundles"
AGORA = datetime.now(UTC)

ANCORA = {
    "anchor_id": "chave-institucional-1",
    "anchor_type": "PUBLIC_KEY",
    "algorithm": "ED25519",
    "encoding": "BASE64URL",
    "value": "assinatura-de-teste",
    "purpose": "BUNDLE_SIGNATURE",
}


def _pacote_exportado(algorithm: str = "ED25519") -> dict[str, Any]:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    policy = Policy.create_draft(
        organization_id=org_id, code="pol-sanitaria", name="Política"
    ).publish()
    rule = Rule.create(
        policy_id=policy.policy_id,
        organization_id=org_id,
        code="rule-atestado",
        name="Atestado",
        severity=SeverityLevel.BLOCKING,
        conditions=(
            RuleCondition(
                fact_type="sanitary.attestation",
                payload_key="result",
                operator=ComparisonOperator.EQUALS,
                expected_value="approved",
            ),
        ),
    )
    snapshot = FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=AGORA,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": "rejected"},
                observed_at=AGORA,
            )
        ],
    )
    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="CONFORMIDADE"
    )
    decision = DecisionService().decide(evaluation)
    dossier = DossierService().build(
        decision=decision, evaluation=evaluation, policy=policy, rules=[rule]
    )
    service = VerificationBundleService()
    bundle = service.build_from_dossier(
        dossier=dossier,
        audience="auditoria",
        created_at=AGORA,
        signature=SignatureMaterial(
            key_id="chave-institucional-1",
            algorithm=algorithm,
            profile="INSTITUTIONAL_SIGNATURE",
            signed_digest="",
            signature_value="assinatura-de-teste",
            signed_at=AGORA,
            revocation_material=("crl",),
        ),
        verification_policy={"perfil_minimo": "INSTITUTIONAL_SIGNATURE"},
    )
    return service.export(bundle)


def test_intact_bundle_returns_dimensional_report() -> None:
    resposta = client.post(
        ENDPOINT, json={"bundle": _pacote_exportado(), "trust_anchors": [ANCORA]}
    )

    assert resposta.status_code == 200
    corpo = resposta.json()

    # Nunca um booleano: não existe campo `valid`.
    assert "valid" not in corpo
    assert corpo["aggregate_status"] == "VALIDA"
    assert len(corpo["dimensions"]) == 8
    assert corpo["contract_version"] == "1.0"
    assert corpo["verification_profile"] == "titan-bundle-verification-v1"
    assert corpo["engine"]["name"] == "titan-bundle-verifier"


def test_response_declares_what_was_not_done() -> None:
    corpo = client.post(
        ENDPOINT, json={"bundle": _pacote_exportado(), "trust_anchors": [ANCORA]}
    ).json()

    atual = next(d for d in corpo["dimensions"] if d["dimension"] == "REVOGACAO_ATUAL")
    assert atual["status"] == "NAO_EXECUTADA"
    assert atual["mandatory"] is False

    codigos = {limite["code"] for limite in corpo["limitations"]}
    assert "CONTENT_TRUTH_NOT_ASSERTED" in codigos
    assert "CURRENT_REVOCATION_NOT_CHECKED" in codigos
    assert "RESULT_DEPENDS_ON_VERIFIER_INSTANCE" in codigos
    # Assinatura válida só vale contra a âncora que o próprio chamador escolheu.
    assert "SIGNATURE_VALID_ONLY_AGAINST_CALLER_SUPPLIED_ANCHOR" in codigos


def test_tampered_bundle_is_a_successful_response_with_invalid_result() -> None:
    pacote = _pacote_exportado()
    pacote["payloads"][DOSSIER_COMPONENT] = pacote["payloads"][DOSSIER_COMPONENT].replace(
        "rejeitada", "aprovada"
    )

    resposta = client.post(ENDPOINT, json={"bundle": pacote, "trust_anchors": [ANCORA]})

    # 200 mesmo para INVALIDA: erro de protocolo não se confunde com resultado.
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["aggregate_status"] == "INVALIDA"
    assert corpo["first_failure"]["dimension"] == "INTEGRIDADE"
    assert corpo["first_failure"]["failure_point"] == DOSSIER_COMPONENT
    assert len(corpo["failures"]) >= 1


def test_without_anchor_signature_is_indeterminate() -> None:
    corpo = client.post(ENDPOINT, json={"bundle": _pacote_exportado()}).json()

    assinatura = next(d for d in corpo["dimensions"] if d["dimension"] == "ASSINATURA")
    assert assinatura["status"] == "INDETERMINADA"
    assert corpo["aggregate_status"] == "INDETERMINADA"
    assert corpo["trust_anchors_used"] == []


def test_unsupported_algorithm_is_indeterminate_not_an_error() -> None:
    resposta = client.post(
        ENDPOINT,
        json={"bundle": _pacote_exportado(algorithm="EXOTICO-9000"), "trust_anchors": [ANCORA]},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assinatura = next(d for d in corpo["dimensions"] if d["dimension"] == "ASSINATURA")
    assert assinatura["status"] == "INDETERMINADA"
    assert assinatura["reason_code"] == "ALGORITMO_NAO_SUPORTADO_PELO_VERIFICADOR"
    # Dimensão obrigatória não avaliada nunca produz agregado válido.
    assert corpo["aggregate_status"] != "VALIDA"


def test_anchors_used_never_echo_the_value() -> None:
    corpo = client.post(
        ENDPOINT, json={"bundle": _pacote_exportado(), "trust_anchors": [ANCORA]}
    ).json()

    ancora = corpo["trust_anchors_used"][0]
    assert ancora["origin"] == "CALLER_SUPPLIED"
    assert ancora["fingerprint"].startswith("sha256:")
    assert "value" not in ancora
    assert ANCORA["value"] not in json.dumps(corpo)


def test_bundle_digest_ignores_the_anchors_used() -> None:
    pacote = _pacote_exportado()
    sem = client.post(ENDPOINT, json={"bundle": pacote}).json()
    com = client.post(ENDPOINT, json={"bundle": pacote, "trust_anchors": [ANCORA]}).json()

    assert sem["bundle_reference"]["bundle_digest"] == com["bundle_reference"]["bundle_digest"]


def test_malformed_json_is_400() -> None:
    resposta = client.post(
        ENDPOINT, content=b"{nao e json", headers={"Content-Type": "application/json"}
    )

    assert resposta.status_code == 400
    assert resposta.headers["content-type"] == "application/problem+json"
    assert resposta.json()["reason_code"] == "MALFORMED_JSON"


def test_duplicate_json_keys_are_rejected() -> None:
    resposta = client.post(
        ENDPOINT,
        content=b'{"bundle": {}, "bundle": {}}',
        headers={"Content-Type": "application/json"},
    )

    assert resposta.status_code == 400
    assert resposta.json()["reason_code"] == "MALFORMED_JSON"


def test_schema_violation_is_422() -> None:
    resposta = client.post(ENDPOINT, json={"nao_e_bundle": 1})

    assert resposta.status_code == 422
    assert resposta.json()["reason_code"] == "MALFORMED_REQUEST"


def test_unrepresentable_bundle_is_422() -> None:
    resposta = client.post(ENDPOINT, json={"bundle": {"manifest": {"errado": True}}})

    assert resposta.status_code == 422
    assert resposta.json()["reason_code"] == "MALFORMED_BUNDLE"


def test_duplicate_anchor_id_is_rejected() -> None:
    resposta = client.post(
        ENDPOINT,
        json={
            "bundle": _pacote_exportado(),
            "trust_anchors": [ANCORA, {**ANCORA, "value": "outro"}],
        },
    )

    assert resposta.status_code == 422
    assert resposta.json()["reason_code"] == "DUPLICATE_ANCHOR_ID"


def test_oversized_body_is_413() -> None:
    resposta = client.post(
        ENDPOINT,
        content=b'{"bundle":{"x":"' + b"a" * (MAX_BODY_BYTES + 10) + b'"}}',
        headers={"Content-Type": "application/json"},
    )

    assert resposta.status_code == 413
    assert resposta.json()["reason_code"] == "PAYLOAD_TOO_LARGE"


def test_excessive_depth_is_rejected() -> None:
    profundo: Any = "fundo"
    for _ in range(40):
        profundo = {"n": profundo}

    resposta = client.post(ENDPOINT, json={"bundle": profundo})

    assert resposta.status_code == 422
    assert resposta.json()["reason_code"] == "MALFORMED_REQUEST"


def test_responses_are_never_cached() -> None:
    for resposta in (
        client.post(ENDPOINT, json={"bundle": _pacote_exportado()}),
        client.post(ENDPOINT, json={"nao_e_bundle": 1}),
    ):
        assert resposta.headers["cache-control"] == "no-store"
        assert resposta.headers["pragma"] == "no-cache"


def test_detail_never_leaks_paths_or_stack_traces() -> None:
    corpo = client.post(ENDPOINT, json={"bundle": {"manifest": {"errado": True}}}).json()

    detalhe = corpo["detail"]
    assert "Traceback" not in detalhe
    assert "\\" not in detalhe
    assert "packages" not in detalhe


def test_identical_bundles_produce_identical_reports() -> None:
    pacote = _pacote_exportado()
    um = client.post(ENDPOINT, json={"bundle": pacote, "trust_anchors": [ANCORA]}).json()
    outro = client.post(ENDPOINT, json={"bundle": pacote, "trust_anchors": [ANCORA]}).json()

    um.pop("verified_at")
    outro.pop("verified_at")
    assert um == outro


def test_endpoint_is_documented_as_public_verification() -> None:
    esquema = client.get("/openapi.json").json()
    operacao = esquema["paths"][ENDPOINT]["post"]

    assert operacao["tags"] == ["verificação"]
    # Verificação externa não exige identidade Titan.
    assert "security" not in operacao
