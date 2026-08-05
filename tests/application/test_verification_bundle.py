"""Testes do VerificationBundle e da verificacao offline (Passo 7.6)."""

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
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.decision_governance import DecisionAuthorityProfile
from packages.core_domain.dossier import Dossier, VerticalSection, compute_dossier_hash
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.policy import Policy
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.core_domain.verification import (
    NORMATIVE_DIMENSION_ORDER,
    BundleVerifier,
    ComponentRequirement,
    DimensionResult,
    SignatureMaterial,
    SignaturePurpose,
    SignatureTarget,
    ValidationReport,
    VerificationBundle,
    VerificationDimension,
    VerificationReasonCode,
    VerificationStatus,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

AGORA = datetime.now(UTC)


def _authority(org_id: OrganizationId, purpose: str) -> DecisionAuthorityProfile:
    return DecisionAuthorityProfile(
        authority_id=TypedId.new("authority_profile"),
        organization_id=org_id,
        principal_reference=UniversalReference(
            target_id=TypedId.new("service_identity"),
            organization_id=org_id,
            contract_version=1,
        ),
        role_name="AUTOMATED_BUNDLE_DECISION_ENGINE",
        purpose=purpose,
        emission_method=DecisionEmissionMethod.AUTOMATED,
        approvals_required=0,
    )


def _dossie() -> Dossier:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    policy = Policy.create_draft(
        organization_id=org_id, code="pol-sanitaria", name="Politica Sanitaria"
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
    decision = DecisionService().decide(evaluation, _authority(org_id, evaluation.purpose))
    return DossierService().build(
        decision=decision, evaluation=evaluation, policy=policy, rules=[rule]
    )


def _alvo_pendente() -> SignatureTarget:
    """Alvo provisório: `build_from_dossier` rebinda `target_identifier` para o
    digest do manifesto real, que só existe depois que o manifesto é montado."""
    return SignatureTarget(
        target_type="bundle_manifest",
        target_identifier="pendente",
        domain="titan.verification_bundle",
        contract_version=1,
        purpose=SignaturePurpose.EMISSAO,
    )


def _assinatura() -> SignatureMaterial:
    return SignatureMaterial(
        key_id="chave-institucional-1",
        algorithm="sha256",
        profile="INSTITUTIONAL_SIGNATURE",
        signature_target=_alvo_pendente(),
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
    assert relatorio.failures == ()
    assert len(relatorio.results) == len(NORMATIVE_DIMENSION_ORDER)
    assert relatorio.explain()

    atual = relatorio.result_for(VerificationDimension.REVOGACAO_ATUAL)
    assert atual is not None
    assert atual.status is VerificationStatus.NAO_EXECUTADA


def test_unsupported_algorithm_never_yields_a_valid_aggregate() -> None:
    bundle = VerificationBundleService().build_from_dossier(
        dossier=_dossie(),
        audience="auditoria",
        created_at=AGORA,
        signature=SignatureMaterial(
            key_id="chave-institucional-1",
            algorithm="ALGORITMO-EXOTICO-2048",
            profile="INSTITUTIONAL_SIGNATURE",
            signature_target=_alvo_pendente(),
            signature_value="assinatura-de-teste",
            signed_at=AGORA,
            revocation_material=("crl",),
        ),
        verification_policy={"perfil_minimo": "INSTITUTIONAL_SIGNATURE"},
    )
    relatorio = BundleVerifier().verify(bundle, verified_at=AGORA, trust_anchors=ANCORAS)

    assinatura = relatorio.result_for(VerificationDimension.ASSINATURA)
    assert assinatura is not None
    assert assinatura.status is VerificationStatus.INDETERMINADA
    assert assinatura.reason_code is VerificationReasonCode.ALGORITMO_NAO_SUPORTADO_PELO_VERIFICADOR
    assert relatorio.status is VerificationStatus.INDETERMINADA


def test_mandatory_dimension_not_executed_forces_indeterminate_aggregate() -> None:
    bundle = _pacote_completo()
    base = BundleVerifier().verify(bundle, verified_at=AGORA, trust_anchors=ANCORAS)
    assert base.status is VerificationStatus.VALIDA

    forjado = ValidationReport(
        bundle_id=base.bundle_id,
        verified_at=base.verified_at,
        results=tuple(
            DimensionResult(
                dimension=r.dimension,
                status=(
                    VerificationStatus.NAO_EXECUTADA
                    if r.dimension is VerificationDimension.ASSINATURA
                    else r.status
                ),
                reason_code=r.reason_code,
                detail=r.detail,
                failure_point=r.failure_point,
            )
            for r in base.results
        ),
    )
    assert forjado.status is VerificationStatus.INDETERMINADA


def test_failures_only_lists_invalid_dimensions() -> None:
    bundle = _pacote_completo()
    sem_dossie = {k: v for k, v in bundle.payloads.items() if k != DOSSIER_COMPONENT}
    relatorio = BundleVerifier().verify(
        VerificationBundle(
            manifest=bundle.manifest, payloads=sem_dossie, signature=bundle.signature
        ),
        verified_at=AGORA,
        trust_anchors=ANCORAS,
    )

    assert relatorio.status is VerificationStatus.INDETERMINADA
    assert relatorio.failures == ()
    assert relatorio.first_failure is None


def test_bundle_travels_and_is_verified_without_titan() -> None:
    service = VerificationBundleService()
    bundle = _pacote_completo()

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
        purpose="OUTRA_FINALIDADE",
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


def test_signature_targeting_a_different_object_type_is_invalid() -> None:
    """ADR-0055 invariante 28: assinatura de objeto não se estende implicitamente
    a objeto relacionado -- uma assinatura sobre `dossier`, por exemplo, não
    comprova o `bundle_manifest` ainda que o resto do pacote esteja íntegro."""
    bundle = _pacote_completo()
    assert bundle.signature is not None
    alvo_errado = SignatureTarget(
        target_type="dossier",
        target_identifier=bundle.manifest.manifest_digest,
        domain="titan.dossier",
        contract_version=4,
        purpose=SignaturePurpose.EMISSAO,
    )
    assinatura_com_alvo_errado = SignatureMaterial(
        key_id=bundle.signature.key_id,
        algorithm=bundle.signature.algorithm,
        profile=bundle.signature.profile,
        signature_target=alvo_errado,
        signature_value=bundle.signature.signature_value,
        signed_at=bundle.signature.signed_at,
        certificate_chain=bundle.signature.certificate_chain,
        revocation_material=bundle.signature.revocation_material,
    )

    relatorio = BundleVerifier().verify(
        VerificationBundle(
            manifest=bundle.manifest,
            payloads=bundle.payloads,
            signature=assinatura_com_alvo_errado,
        ),
        verified_at=AGORA,
        trust_anchors=ANCORAS,
    )

    assinatura = relatorio.result_for(VerificationDimension.ASSINATURA)
    assert assinatura is not None
    assert assinatura.status is VerificationStatus.INVALIDA
    assert assinatura.reason_code is VerificationReasonCode.ASSINATURA_NAO_CONFERE
    assert assinatura.failure_point == "signature.signature_target.target_type"
    assert relatorio.status is VerificationStatus.INVALIDA


def test_without_trust_anchor_signature_is_indeterminate() -> None:
    bundle = _pacote_completo()

    relatorio = BundleVerifier().verify(bundle, verified_at=AGORA, trust_anchors=None)

    assinatura = relatorio.result_for(VerificationDimension.ASSINATURA)
    assert assinatura is not None
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
        declared_gaps=("Evidencias brutas omitidas por autorizacao.",),
    )
    relatorio = BundleVerifier().verify(bundle, verified_at=AGORA, trust_anchors=ANCORAS)

    cobertura = relatorio.result_for(VerificationDimension.COBERTURA)
    assert cobertura is not None
    assert cobertura.status is VerificationStatus.INDETERMINADA
    assert relatorio.status is VerificationStatus.INDETERMINADA


def test_livestock_bundle_derives_scopes_and_gaps_from_the_canonical_dossier() -> None:
    dossier = _dossie()
    document = {
        **dossier.document,
        "vertical": VerticalSection(
            namespace="livestock",
            section_version=2,
            content={
                "coverage": {
                    "status": "PARTIAL_DECLARED",
                    "declared_scope": "TRANSFER_DECLARED_PARTIAL",
                    "has_declared_gaps": True,
                    "gaps": [{"code": "COVERAGE_BEFORE_TRANSFER"}],
                },
                "imported_material": {
                    "has_imported_facts": True,
                    "declared_scope": "IMPORTED_AND_LOCAL",
                },
                "declared_limitations": [
                    "Cobertura sanitaria parcial declarada; lacunas permanecem abertas."
                ],
            },
        ).to_dict(),
    }
    enriquecido = type(dossier)(
        dossier_id=dossier.dossier_id,
        organization_id=dossier.organization_id,
        subject_reference=dossier.subject_reference,
        purpose=dossier.purpose,
        decision_id=dossier.decision_id,
        evaluation_id=dossier.evaluation_id,
        generated_at=dossier.generated_at,
        dossier_hash=compute_dossier_hash(document),
        document_version=dossier.document_version,
        serialization_version=dossier.serialization_version,
        document=document,
    )
    bundle = VerificationBundleService().build_from_dossier(
        dossier=enriquecido,
        audience="auditoria",
        created_at=AGORA,
        signature=_assinatura(),
        verification_policy={"perfil_minimo": "INSTITUTIONAL_SIGNATURE"},
    )

    assert "prova_sanitaria_vitalicia" in bundle.manifest.declared_scopes
    assert "coverage:TRANSFER_DECLARED_PARTIAL" in bundle.manifest.declared_scopes
    assert "material:IMPORTED_AND_LOCAL" in bundle.manifest.declared_scopes
    assert "historico_importado_declarado" in bundle.manifest.declared_scopes
    assert any(
        "Cobertura sanitaria parcial declarada" in gap for gap in bundle.manifest.declared_gaps
    )
    assert any(
        "Material importado acompanha o pacote" in gap for gap in bundle.manifest.declared_gaps
    )
