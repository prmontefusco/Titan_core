"""Testes do VerificationBundle e da verificação offline (Passo 7.6).

Percorre a validação do plano: verificar com ferramenta independente e sem Titan,
confirmar `INDETERMINADA` quando falta material e `INVALIDA` com o ponto exato da
falha quando o conteúdo é adulterado.
"""

import json
from datetime import UTC, datetime

import pytest

from packages.core_application.decision_service import DecisionService
from packages.core_application.dossier_service import DossierService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.verification_service import (
    DOSSIER_COMPONENT,
    TRUST_POLICY_COMPONENT,
    VerificationBundleService,
)
from packages.core_domain.dossier import Dossier
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.policy import Policy
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.core_domain.verification import (
    BundleVerifier,
    ComponentRequirement,
    SignatureMaterial,
    VerificationBundle,
    VerificationDimension,
    VerificationReasonCode,
    VerificationStatus,
)
from packages.shared_kernel import OrganizationId, TypedId

AGORA = datetime.now(UTC)


def _dossie() -> Dossier:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    policy = Policy.create_draft(
        organization_id=org_id, code="pol-sanitaria", name="Política Sanitária"
    ).publish()
    rule = Rule.create(
        policy_id=policy.policy_id,
        organization_id=org_id,
        code="rule-atestado",
        name="Atestado aprovado",
        severity=SeverityLevel.BLOCKING,
        conditions=(
            RuleCondition(
                fact_type="sanitary.attestation",
                payload_key="result",
                operator=ComparisonOperator.EQUALS,
                expected_value="approved",
            ),
        ),
        corrective_action="Reemitir o atestado.",
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
        policy=policy, rules=[rule], snapshot=snapshot, purpose="CONFORMIDADE_SANITARIA"
    )
    decision = DecisionService().decide(evaluation)
    return DossierService().build(
        decision=decision, evaluation=evaluation, policy=policy, rules=[rule]
    )


def _assinatura() -> SignatureMaterial:
    return SignatureMaterial(
        key_id="chave-institucional-1",
        algorithm="sha256",
        profile="INSTITUTIONAL_SIGNATURE",
        signed_digest="",  # preenchido pelo serviço com o digest do manifesto
        signature_value="assinatura-de-teste",
        signed_at=AGORA,
        certificate_chain=("cert-emissor",),
        revocation_material=("crl-instante-de-referencia",),
    )


def _pacote_completo() -> VerificationBundle:
    return VerificationBundleService().build_from_dossier(
        dossier=_dossie(),
        audience="auditoria externa",
        created_at=AGORA,
        signature=_assinatura(),
        verification_policy={"perfil_minimo": "INSTITUTIONAL_SIGNATURE"},
        profiles=("INSTITUTIONAL_SIGNATURE",),
    )


ANCORAS = {"chave-institucional-1": "assinatura-de-teste"}


def test_complete_bundle_verifies_as_valid_offline() -> None:
    bundle = _pacote_completo()
    relatorio = BundleVerifier().verify(bundle, verified_at=AGORA, trust_anchors=ANCORAS)

    assert relatorio.status is VerificationStatus.VALIDA
    assert relatorio.first_failure is None
    # Nunca um booleano: cada dimensão responde por si.
    assert len(relatorio.results) == 7
    assert relatorio.explain()


def test_bundle_travels_and_is_verified_without_titan() -> None:
    service = VerificationBundleService()
    bundle = _pacote_completo()

    # Sai do Titan como texto e volta em outra ponta, sem banco nem rede.
    transportado = json.loads(json.dumps(service.export(bundle)))
    recebido = VerificationBundleService.load(transportado)

    relatorio = BundleVerifier().verify(recebido, verified_at=AGORA, trust_anchors=ANCORAS)
    assert relatorio.status is VerificationStatus.VALIDA


def test_tampered_component_is_invalid_with_exact_failure_point() -> None:
    bundle = _pacote_completo()
    adulterado = dict(bundle.payloads)
    adulterado[DOSSIER_COMPONENT] = adulterado[DOSSIER_COMPONENT].replace(b"rejeitada", b"aprovada")

    relatorio = BundleVerifier().verify(
        type(bundle)(manifest=bundle.manifest, payloads=adulterado, signature=bundle.signature),
        verified_at=AGORA,
        trust_anchors=ANCORAS,
    )

    assert relatorio.status is VerificationStatus.INVALIDA
    falha = relatorio.first_failure
    assert falha is not None
    assert falha.dimension is VerificationDimension.INTEGRIDADE
    assert falha.reason_code is VerificationReasonCode.DIGEST_DIVERGENTE
    # O ponto exato da falha é nomeado.
    assert falha.failure_point == DOSSIER_COMPONENT


def test_missing_required_component_is_indeterminate_not_invalid() -> None:
    bundle = _pacote_completo()
    sem_dossie = {k: v for k, v in bundle.payloads.items() if k != DOSSIER_COMPONENT}

    relatorio = BundleVerifier().verify(
        type(bundle)(manifest=bundle.manifest, payloads=sem_dossie, signature=bundle.signature),
        verified_at=AGORA,
        trust_anchors=ANCORAS,
    )

    estrutura = relatorio.result_for(VerificationDimension.ESTRUTURA)
    assert estrutura is not None
    # Falta de material é indeterminação, jamais reprovação.
    assert estrutura.status is VerificationStatus.INDETERMINADA
    assert estrutura.reason_code is VerificationReasonCode.COMPONENTE_OBRIGATORIO_AUSENTE
    assert relatorio.status is VerificationStatus.INDETERMINADA


def test_undeclared_component_is_invalid() -> None:
    bundle = _pacote_completo()
    com_intruso = {**bundle.payloads, "extra.json": b"{}"}

    relatorio = BundleVerifier().verify(
        type(bundle)(manifest=bundle.manifest, payloads=com_intruso, signature=bundle.signature),
        verified_at=AGORA,
        trust_anchors=ANCORAS,
    )

    falha = relatorio.first_failure
    assert falha is not None
    assert falha.reason_code is VerificationReasonCode.COMPONENTE_NAO_DECLARADO
    assert falha.failure_point == "extra.json"


def test_tampered_manifest_is_detected() -> None:
    bundle = _pacote_completo()
    manifesto_alterado = type(bundle.manifest)(
        bundle_id=bundle.manifest.bundle_id,
        organization_id=bundle.manifest.organization_id,
        purpose="OUTRA_FINALIDADE",  # alterado sem recalcular o digest
        audience=bundle.manifest.audience,
        created_at=bundle.manifest.created_at,
        components=bundle.manifest.components,
        manifest_digest=bundle.manifest.manifest_digest,
        declared_scopes=bundle.manifest.declared_scopes,
        declared_gaps=bundle.manifest.declared_gaps,
        profiles=bundle.manifest.profiles,
    )

    relatorio = BundleVerifier().verify(
        type(bundle)(
            manifest=manifesto_alterado,
            payloads=bundle.payloads,
            signature=bundle.signature,
        ),
        verified_at=AGORA,
        trust_anchors=ANCORAS,
    )

    falha = relatorio.first_failure
    assert falha is not None
    assert falha.reason_code is VerificationReasonCode.MANIFESTO_ADULTERADO
    assert falha.failure_point == "manifest"


def test_without_trust_anchor_signature_is_indeterminate() -> None:
    bundle = _pacote_completo()

    relatorio = BundleVerifier().verify(bundle, verified_at=AGORA, trust_anchors=None)

    assinatura = relatorio.result_for(VerificationDimension.ASSINATURA)
    assert assinatura is not None
    # Âncora dentro do pacote não é confiável por estar no pacote.
    assert assinatura.status is VerificationStatus.INDETERMINADA
    assert assinatura.reason_code is VerificationReasonCode.MATERIAL_DE_CONFIANCA_AUSENTE
    assert relatorio.status is VerificationStatus.INDETERMINADA
    assert "nenhuma âncora" in relatorio.trust_anchor_origin


def test_bundle_without_signature_declares_the_gap() -> None:
    bundle = VerificationBundleService().build_from_dossier(
        dossier=_dossie(), audience="auditoria", created_at=AGORA
    )

    relatorio = BundleVerifier().verify(bundle, verified_at=AGORA)
    assert relatorio.status is VerificationStatus.INDETERMINADA

    # A ausência é declarada no manifesto, não silenciosa.
    assert any("Sem assinatura" in g for g in bundle.manifest.declared_gaps)
    politica = bundle.manifest.component(TRUST_POLICY_COMPONENT)
    assert politica is not None
    assert politica.requirement is ComponentRequirement.DELIBERADAMENTE_AUSENTE


def test_revocation_and_temporal_are_indeterminate_without_material() -> None:
    bundle = VerificationBundleService().build_from_dossier(
        dossier=_dossie(), audience="auditoria", created_at=AGORA
    )
    relatorio = BundleVerifier().verify(bundle, verified_at=AGORA)

    for dimensao in (VerificationDimension.TEMPORAL, VerificationDimension.REVOGACAO):
        resultado = relatorio.result_for(dimensao)
        assert resultado is not None
        assert resultado.status is VerificationStatus.INDETERMINADA
        assert resultado.reason_code is VerificationReasonCode.MATERIAL_AUSENTE


def test_forbidden_material_is_never_packaged() -> None:
    with pytest.raises(ValueError, match="Material proibido"):
        VerificationBundleService().build_from_dossier(
            dossier=_dossie(),
            audience="auditoria",
            created_at=AGORA,
            verification_policy={"private_key": "nunca deveria estar aqui"},
        )


def test_dossier_that_does_not_verify_cannot_be_packaged() -> None:
    original = _dossie()
    quebrado = type(original)(
        dossier_id=original.dossier_id,
        organization_id=original.organization_id,
        subject_reference=original.subject_reference,
        purpose=original.purpose,
        decision_id=original.decision_id,
        evaluation_id=original.evaluation_id,
        generated_at=original.generated_at,
        document=original.document,
        dossier_hash="hash-que-nao-confere",
    )

    with pytest.raises(ValueError, match="não confere com seu próprio hash"):
        VerificationBundleService().build_from_dossier(
            dossier=quebrado, audience="auditoria", created_at=AGORA
        )


def test_declared_gaps_make_coverage_indeterminate() -> None:
    bundle = VerificationBundleService().build_from_dossier(
        dossier=_dossie(),
        audience="auditoria",
        created_at=AGORA,
        signature=_assinatura(),
        verification_policy={"perfil_minimo": "INSTITUTIONAL_SIGNATURE"},
        declared_gaps=("Evidências brutas omitidas por autorização.",),
    )
    relatorio = BundleVerifier().verify(bundle, verified_at=AGORA, trust_anchors=ANCORAS)

    cobertura = relatorio.result_for(VerificationDimension.COBERTURA)
    assert cobertura is not None
    assert cobertura.status is VerificationStatus.INDETERMINADA
    assert relatorio.status is VerificationStatus.INDETERMINADA
