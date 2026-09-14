"""F1: Commercial Passport application contracts only."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_application.dossier_service import DossierService
from packages.core_application.verification_service import VerificationBundleService
from packages.core_domain.decision import (
    Decision,
    DecisionReason,
    DecisionReasonCode,
    DecisionResult,
    compute_decision_hash,
)
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.dossier import Dossier, compute_dossier_hash
from packages.core_domain.evaluation import (
    Evaluation,
    EvaluationOutcome,
    RuleResult,
    RuleResultStatus,
    compute_context_hash,
    compute_evaluation_hash,
)
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.normative import (
    NormativeBasisSnapshot,
    NormativeReferenceSnapshot,
    NormativeSourceClassification,
)
from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.rule import SeverityLevel
from packages.livestock_application.commercial_passport import (
    CommercialOpportunity,
    CommercialOpportunityKind,
    CommercialPassport,
    CommercialPassportContext,
    CommercialPassportDossierSectionBuilder,
    CommercialPassportFormalIssuanceService,
    CommercialPassportMarketReadinessSource,
    CommercialPassportOpportunityAssessment,
    CommercialPassportRequirementDimension,
    CommercialPassportRequirementStatus,
    CommercialReadinessBreakdown,
    CommercialReadinessInterpretation,
    CommercialRequirementAssessment,
    PopulationEligibilitySummary,
    PropertyCommercialPassportMarketReadinessPipeline,
    PropertyCommercialPassportOpportunityInput,
    PropertyCommercialPassportService,
    PropertyCommercialReadiness,
)
from packages.livestock_application.market_readiness import (
    MarketReadinessContext,
    MarketReadinessEntry,
    MarketReadinessGapSummary,
    MarketReadinessReport,
    MarketReadinessStatus,
)
from packages.livestock_application.verification_bundle_interpreter import (
    LivestockVerificationBundleInterpreter,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

NOW = datetime(2026, 9, 11, tzinfo=UTC)
PASSPORT_PURPOSE = "commercial-passport"


class _DossierRepository:
    def __init__(self) -> None:
        self.saved: list[Dossier] = []

    def save(self, dossier: Dossier) -> None:
        self.saved.append(dossier)

    def get_by_id(self, dossier_id: TypedId) -> Dossier | None:
        return next((item for item in self.saved if item.dossier_id == dossier_id), None)

    def list_by_subject(
        self,
        organization_id: OrganizationId,
        subject_id: TypedId,
    ) -> list[Dossier]:
        return [
            item
            for item in self.saved
            if item.organization_id == organization_id
            and item.subject_reference.target_id == subject_id
        ]


def _context() -> CommercialPassportContext:
    return CommercialPassportContext(
        organization_id=OrganizationId.new(),
        property_id=TypedId.new("rural_property"),
        reference_time=NOW,
        knowledge_cutoff=NOW,
        evaluated_at=NOW,
    )


def _opportunity(code: str = "synthetic-eu") -> CommercialOpportunity:
    return CommercialOpportunity(
        code=code,
        kind=CommercialOpportunityKind.MARKET,
        name="Synthetic EU",
        purpose="exportacao-uniao-europeia",
        policy_id=TypedId.new("policy"),
        policy_version=1,
    )


def _issuance_artifacts(
    context: CommercialPassportContext,
    *,
    subject_id: TypedId | None = None,
) -> tuple[Decision, Evaluation, Policy]:
    subject_id = subject_id or context.property_id
    policy = Policy(
        policy_id=TypedId.new("policy"),
        organization_id=context.organization_id,
        code="commercial-passport-anchor",
        name="Commercial Passport anchor policy",
        description="Policy anchor for Commercial Passport formal issuance.",
        version=1,
        status=PolicyStatus.PUBLISHED,
        published_at=NOW,
    )
    fact = Fact.create(
        fact_type="livestock.commercial_passport.anchor",
        payload={"property_id": str(context.property_id.value)},
        observed_at=NOW,
    )
    snapshot = FactSnapshot.create(
        organization_id=context.organization_id,
        target_id=subject_id,
        as_of=NOW,
        facts=(fact,),
        reference_time=context.reference_time,
        knowledge_cutoff=context.knowledge_cutoff,
    )
    rule_versions = (("commercial-passport-anchor", 1),)
    normative = NormativeBasisSnapshot(
        schema_version=1,
        normative_basis_id=TypedId.new("normative_basis"),
        normative_basis_code="COMMERCIAL_PASSPORT_ANCHOR",
        normative_basis_version=1,
        policy_id=policy.policy_id,
        policy_code=policy.code,
        policy_version=policy.version,
        rule_versions=rule_versions,
        purpose=PASSPORT_PURPOSE,
        jurisdiction="INTERNAL_TEST",
        intended_use="COMMERCIAL_PASSPORT_FORMAL_ISSUANCE",
        reference_time=context.reference_time,
        knowledge_cutoff=context.knowledge_cutoff,
        approved_by="SYSTEM:TEST",
        approval_authority="INTERNAL_TEST",
        approved_at=NOW,
        references=(
            NormativeReferenceSnapshot(
                instrument_code="COMMERCIAL-PASSPORT-ANCHOR",
                instrument_version="1",
                provision="formal-issuance",
                content_digest="c" * 64,
                digest_algorithm="sha256",
                source_classification=NormativeSourceClassification.INTERNAL_TEST,
            ),
        ),
    )
    context_hash = compute_context_hash(
        policy_id=policy.policy_id,
        policy_version=policy.version,
        purpose=PASSPORT_PURPOSE,
        engine_version=1,
        rule_versions=rule_versions,
        normative_basis_snapshot_digest=normative.snapshot_digest,
    )
    result = RuleResult(
        result_id=TypedId.new("rule_result"),
        rule_id=TypedId.new("rule"),
        rule_version=1,
        organization_id=context.organization_id,
        subject_id=subject_id,
        status=RuleResultStatus.ATENDIDA,
        severity=SeverityLevel.INFO,
        reason="Commercial Passport formal issuance anchor satisfied.",
        corrective_action="Nenhuma ação necessária.",
        missing_evidence_types=(),
        evaluated_at=NOW,
        snapshot_hash=snapshot.snapshot_hash,
        inputs_hash="d" * 64,
        rule_code=rule_versions[0][0],
    )
    evaluation_hash = compute_evaluation_hash(
        context_hash=context_hash,
        subject_id=subject_id,
        snapshot_hash=snapshot.snapshot_hash,
        rule_results=(result,),
        outcome=EvaluationOutcome.CONDICOES_SATISFEITAS,
    )
    evaluation = Evaluation(
        evaluation_id=TypedId.new("evaluation"),
        organization_id=context.organization_id,
        subject_id=subject_id,
        purpose=PASSPORT_PURPOSE,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        fact_snapshot=snapshot,
        rule_results=(result,),
        outcome=EvaluationOutcome.CONDICOES_SATISFEITAS,
        evaluated_at=NOW,
        engine_version=1,
        evaluation_hash=evaluation_hash,
        context_hash=context_hash,
        normative_basis_snapshot=normative,
        rule_versions=rule_versions,
    )
    reason = DecisionReason(
        code=DecisionReasonCode.REGRA_ATENDIDA,
        message="Commercial Passport formal issuance anchor approved.",
        rule_code=result.rule_code,
        rule_id=result.rule_id,
        rule_version=result.rule_version,
    )
    authority_profile_id = TypedId.new("authority_profile")
    decision = Decision(
        decision_id=TypedId.new("decision"),
        organization_id=context.organization_id,
        subject_id=subject_id,
        purpose=PASSPORT_PURPOSE,
        evaluation_id=evaluation.evaluation_id,
        evaluation_hash=evaluation.evaluation_hash,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        result=DecisionResult.APROVADA,
        reasons=(reason,),
        snapshot_hash=snapshot.snapshot_hash,
        issued_at=NOW,
        engine_version=1,
        decision_hash=compute_decision_hash(
            evaluation_hash=evaluation_hash,
            subject_id=subject_id,
            purpose=PASSPORT_PURPOSE,
            result=DecisionResult.APROVADA,
            reasons=(reason,),
            authority_profile_id=authority_profile_id,
            emission_method=DecisionEmissionMethod.AUTOMATED,
        ),
        authority_profile_id=authority_profile_id,
        authority_reference=UniversalReference(
            TypedId.new("service_identity"),
            context.organization_id,
            1,
        ),
        emission_method=DecisionEmissionMethod.AUTOMATED,
    )
    return decision, evaluation, policy


def _market_readiness_report(
    *,
    context: CommercialPassportContext,
    opportunity: CommercialOpportunity,
    ready: int = 1,
    not_ready: int = 0,
    indeterminate: int = 0,
) -> MarketReadinessReport:
    entries = (
        *(
            MarketReadinessEntry(
                subject_id=TypedId.new("animal"),
                status=MarketReadinessStatus.READY,
                decision_id=TypedId.new("decision"),
                evaluation_id=TypedId.new("evaluation"),
                reason_codes=("APPROVED",),
                limitations=(),
            )
            for _ in range(ready)
        ),
        *(
            MarketReadinessEntry(
                subject_id=TypedId.new("animal"),
                status=MarketReadinessStatus.NOT_READY,
                decision_id=TypedId.new("decision"),
                evaluation_id=TypedId.new("evaluation"),
                reason_codes=("BLOCKING_GAP",),
                limitations=(),
            )
            for _ in range(not_ready)
        ),
        *(
            MarketReadinessEntry(
                subject_id=TypedId.new("animal"),
                status=MarketReadinessStatus.INDETERMINATE,
                decision_id=None,
                evaluation_id=None,
                reason_codes=("UNKNOWN_EVIDENCE",),
                limitations=("knowledge limitation",),
            )
            for _ in range(indeterminate)
        ),
    )
    return MarketReadinessReport(
        context=MarketReadinessContext(
            organization_id=context.organization_id,
            purpose=opportunity.purpose,
            policy_id=opportunity.policy_id,
            policy_version=opportunity.policy_version,
            reference_time=context.reference_time,
            knowledge_cutoff=context.knowledge_cutoff,
        ),
        entries=entries,
        counts={
            status: sum(1 for entry in entries if entry.status is status)
            for status in MarketReadinessStatus
        },
        gap_summary=(
            MarketReadinessGapSummary(
                code="BLOCKING_GAP",
                count=not_ready,
                example_subject_ids=tuple(
                    entry.subject_id
                    for entry in entries
                    if entry.status is MarketReadinessStatus.NOT_READY
                )[:3],
            ),
        ),
    )


def _requirement(
    code: str,
    status: CommercialPassportRequirementStatus,
    dimension: CommercialPassportRequirementDimension = (
        CommercialPassportRequirementDimension.PROPERTY_READINESS
    ),
) -> CommercialRequirementAssessment:
    return CommercialRequirementAssessment(
        requirement_code=code,
        label=f"Requirement {code}",
        dimension=dimension,
        status=status,
        reason=f"Reason for {code}",
    )


def test_context_preserves_temporal_coordinates_without_current_state_shortcut() -> None:
    context = _context()

    assert context.reference_time == NOW
    assert context.knowledge_cutoff == NOW
    assert context.evaluated_at == NOW

    with pytest.raises(ValueError, match="knowledge_cutoff"):
        CommercialPassportContext(
            organization_id=OrganizationId.new(),
            property_id=TypedId.new("rural_property"),
            reference_time=NOW,
            knowledge_cutoff=NOW - timedelta(days=1),
            evaluated_at=NOW,
        )


def test_property_readiness_counts_are_derived_and_not_single_score() -> None:
    readiness = PropertyCommercialReadiness(
        requirements=(
            _requirement("traceability", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("document", CommercialPassportRequirementStatus.MISSING),
            _requirement("feed", CommercialPassportRequirementStatus.UNKNOWN),
            _requirement("reconciliation", CommercialPassportRequirementStatus.FAILED),
            _requirement("private-protocol", CommercialPassportRequirementStatus.NOT_APPLICABLE),
            _requirement("withdrawal", CommercialPassportRequirementStatus.BLOCKED),
        ),
    )

    assert readiness.breakdown == CommercialReadinessBreakdown(
        satisfied=1,
        missing=1,
        unknown=1,
        failed=1,
        not_applicable=1,
        blocked=1,
    )
    assert readiness.breakdown.applicable_count == 5
    assert readiness.breakdown.total_count == 6
    assert readiness.breakdown.derived_ratio == 1 / 5
    assert readiness.breakdown.has_blocker is True
    assert readiness.breakdown.interpretation is (
        CommercialReadinessInterpretation.UNAVAILABLE_BLOCKED
    )


def test_not_applicable_stays_out_of_readiness_denominator() -> None:
    readiness = PropertyCommercialReadiness(
        requirements=(
            _requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("not-applicable", CommercialPassportRequirementStatus.NOT_APPLICABLE),
        ),
    )

    assert readiness.breakdown.applicable_count == 1
    assert readiness.breakdown.derived_ratio == 1.0


def test_requirement_status_semantics_preserve_distinctions() -> None:
    missing = CommercialPassportRequirementStatus.MISSING
    unknown = CommercialPassportRequirementStatus.UNKNOWN
    failed = CommercialPassportRequirementStatus.FAILED
    blocked = CommercialPassportRequirementStatus.BLOCKED
    not_applicable = CommercialPassportRequirementStatus.NOT_APPLICABLE

    assert missing.is_missing_evidence is True
    assert missing.is_unknown is False
    assert unknown.is_unknown is True
    assert unknown.is_missing_evidence is False
    assert failed.is_failed is True
    assert failed.is_missing_evidence is False
    assert blocked.blocks_opportunity is True
    assert blocked.is_failed is False
    assert not_applicable.applies_to_readiness_denominator is False
    assert "not false" in unknown.semantic_description


def test_readiness_interpretation_is_derived_with_blocker_precedence() -> None:
    blocked = PropertyCommercialReadiness(
        requirements=(
            _requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("blocker", CommercialPassportRequirementStatus.BLOCKED),
        ),
    )
    failed = PropertyCommercialReadiness(
        requirements=(
            _requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("failed", CommercialPassportRequirementStatus.FAILED),
        ),
    )
    unknown = PropertyCommercialReadiness(
        requirements=(
            _requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("unknown", CommercialPassportRequirementStatus.UNKNOWN),
        ),
    )
    missing = PropertyCommercialReadiness(
        requirements=(
            _requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("missing", CommercialPassportRequirementStatus.MISSING),
        ),
    )
    available = PropertyCommercialReadiness(
        requirements=(_requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),),
    )
    not_assessed = PropertyCommercialReadiness(
        requirements=(
            _requirement("not-applicable", CommercialPassportRequirementStatus.NOT_APPLICABLE),
        ),
    )

    assert blocked.breakdown.derived_ratio == 0.5
    assert blocked.breakdown.interpretation is (
        CommercialReadinessInterpretation.UNAVAILABLE_BLOCKED
    )
    assert failed.breakdown.interpretation is (CommercialReadinessInterpretation.UNAVAILABLE_FAILED)
    assert unknown.breakdown.interpretation is CommercialReadinessInterpretation.UNKNOWN
    assert missing.breakdown.interpretation is CommercialReadinessInterpretation.PARTIALLY_READY
    assert available.breakdown.interpretation is CommercialReadinessInterpretation.AVAILABLE
    assert not_assessed.breakdown.interpretation is CommercialReadinessInterpretation.NOT_ASSESSED


def test_property_readiness_refuses_population_dimension() -> None:
    with pytest.raises(ValueError, match="propriedade"):
        PropertyCommercialReadiness(
            requirements=(
                _requirement(
                    "animal-readiness",
                    CommercialPassportRequirementStatus.SATISFIED,
                    CommercialPassportRequirementDimension.POPULATION_ELIGIBILITY,
                ),
            ),
        )


def test_population_eligibility_is_separate_from_property_readiness() -> None:
    property_readiness = PropertyCommercialReadiness(
        requirements=(
            _requirement("property-document", CommercialPassportRequirementStatus.SATISFIED),
        ),
    )
    population = PopulationEligibilitySummary(
        subject_type="animal",
        counts_by_status={
            "READY": 742,
            "INDETERMINATE": 103,
            "NOT_READY": 377,
            "BLOCKED": 28,
        },
        limitations=("derived from MarketReadiness; not a Decision",),
    )
    assessment = CommercialPassportOpportunityAssessment(
        opportunity=_opportunity(),
        property_readiness=property_readiness,
        population_eligibility=population,
    )

    assert assessment.property_readiness.breakdown.satisfied == 1
    assert assessment.population_eligibility is not None
    assert assessment.population_eligibility.total_count == 1250
    assert assessment.population_eligibility.ready_count == 742
    assert assessment.population_eligibility.not_ready_count == 377


def test_dynamic_passport_is_projection_not_issued_snapshot() -> None:
    passport = CommercialPassport(
        context=_context(),
        opportunities=(
            CommercialPassportOpportunityAssessment(
                opportunity=_opportunity(),
                property_readiness=PropertyCommercialReadiness(
                    requirements=(
                        _requirement(
                            "property-document",
                            CommercialPassportRequirementStatus.SATISFIED,
                        ),
                    ),
                ),
            ),
        ),
    )

    assert "COMMERCIAL_PASSPORT_IS_NOT_DECISION" in passport.limitations
    assert "COMMERCIAL_PASSPORT_IS_NOT_MARKET_ELIGIBILITY" in passport.limitations
    assert "FORMAL_DISCLOSURE_REQUIRES_ISSUED_SNAPSHOT" in passport.limitations


def test_passport_rejects_duplicate_opportunities() -> None:
    opportunity = _opportunity()
    readiness = PropertyCommercialReadiness(
        requirements=(
            _requirement("property-document", CommercialPassportRequirementStatus.SATISFIED),
        ),
    )

    with pytest.raises(ValueError, match="duplicada"):
        CommercialPassport(
            context=_context(),
            opportunities=(
                CommercialPassportOpportunityAssessment(opportunity, readiness),
                CommercialPassportOpportunityAssessment(opportunity, readiness),
            ),
        )


def test_property_passport_service_builds_dynamic_projection() -> None:
    context = _context()
    service = PropertyCommercialPassportService()

    passport = service.build(
        context=context,
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("synthetic-buyer"),
                requirements=(
                    _requirement(
                        "property-document",
                        CommercialPassportRequirementStatus.SATISFIED,
                    ),
                    _requirement(
                        "environmental-evidence",
                        CommercialPassportRequirementStatus.MISSING,
                    ),
                ),
                limitations=("buyer-specific requirement represented in Livestock",),
            ),
        ),
    )

    assert passport.context is context
    assert len(passport.opportunities) == 1
    assessment = passport.opportunities[0]
    assert assessment.opportunity.code == "synthetic-buyer"
    assert assessment.population_eligibility is None
    assert assessment.property_readiness.breakdown.satisfied == 1
    assert assessment.property_readiness.breakdown.missing == 1
    assert assessment.property_readiness.breakdown.interpretation is (
        CommercialReadinessInterpretation.PARTIALLY_READY
    )
    assert "PROPERTY_COMMERCIAL_PASSPORT_IS_DYNAMIC_PROJECTION" in passport.limitations
    assert "FORMAL_ISSUANCE_REQUIRES_DOSSIER_OR_VERIFICATION_BUNDLE" in passport.limitations


def test_property_passport_service_orders_opportunities_deterministically() -> None:
    service = PropertyCommercialPassportService()

    passport = service.build(
        context=_context(),
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("z-market"),
                requirements=(
                    _requirement("z-document", CommercialPassportRequirementStatus.SATISFIED),
                ),
            ),
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("a-market"),
                requirements=(
                    _requirement("a-document", CommercialPassportRequirementStatus.SATISFIED),
                ),
            ),
        ),
    )

    assert [item.opportunity.code for item in passport.opportunities] == [
        "a-market",
        "z-market",
    ]


def test_property_passport_service_rejects_population_requirements_in_property_readiness() -> None:
    service = PropertyCommercialPassportService()

    with pytest.raises(ValueError, match="propriedade"):
        service.build(
            context=_context(),
            opportunities=(
                PropertyCommercialPassportOpportunityInput(
                    opportunity=_opportunity(),
                    requirements=(
                        _requirement(
                            "animal-requirement",
                            CommercialPassportRequirementStatus.SATISFIED,
                            CommercialPassportRequirementDimension.POPULATION_ELIGIBILITY,
                        ),
                    ),
                ),
            ),
        )


def test_property_passport_service_includes_population_summary_separately() -> None:
    service = PropertyCommercialPassportService()
    population = PopulationEligibilitySummary(
        subject_type="animal",
        counts_by_status={
            MarketReadinessStatus.READY.value: 742,
            MarketReadinessStatus.INDETERMINATE.value: 103,
            MarketReadinessStatus.NOT_READY.value: 377,
            "BLOCKED": 28,
        },
        limitations=("derived from MarketReadiness; not a Decision",),
        source_report_reference="market-readiness-report:synthetic-eu:2026-09-11",
    )

    passport = service.build(
        context=_context(),
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("synthetic-eu"),
                requirements=(
                    _requirement(
                        "property-document",
                        CommercialPassportRequirementStatus.SATISFIED,
                    ),
                ),
                population_eligibility=population,
            ),
        ),
    )

    assessment = passport.opportunities[0]
    assert assessment.property_readiness.breakdown.interpretation is (
        CommercialReadinessInterpretation.AVAILABLE
    )
    assert assessment.population_eligibility is not None
    assert assessment.population_eligibility.ready_count == 742
    assert assessment.population_eligibility.indeterminate_count == 103
    assert assessment.population_eligibility.not_ready_count == 377
    assert assessment.population_eligibility.total_count == 1250
    assert "POPULATION_ELIGIBILITY_IS_SEPARATE_FROM_PROPERTY_READINESS" in passport.limitations


def test_population_summary_does_not_make_incomplete_property_ready() -> None:
    service = PropertyCommercialPassportService()
    population = PopulationEligibilitySummary(
        subject_type="animal",
        counts_by_status={MarketReadinessStatus.READY.value: 10},
    )

    passport = service.build(
        context=_context(),
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("property-gap-market"),
                requirements=(
                    _requirement("property-document", CommercialPassportRequirementStatus.MISSING),
                ),
                population_eligibility=population,
            ),
        ),
    )

    assessment = passport.opportunities[0]
    assert assessment.population_eligibility is not None
    assert assessment.population_eligibility.ready_count == 10
    assert assessment.property_readiness.breakdown.missing == 1
    assert assessment.property_readiness.breakdown.interpretation is (
        CommercialReadinessInterpretation.PARTIALLY_READY
    )


def test_property_passport_service_rejects_duplicate_opportunity_codes() -> None:
    service = PropertyCommercialPassportService()

    with pytest.raises(ValueError, match="duplicada"):
        service.build(
            context=_context(),
            opportunities=(
                PropertyCommercialPassportOpportunityInput(
                    opportunity=_opportunity("same-market"),
                    requirements=(
                        _requirement("first", CommercialPassportRequirementStatus.SATISFIED),
                    ),
                ),
                PropertyCommercialPassportOpportunityInput(
                    opportunity=_opportunity("same-market"),
                    requirements=(
                        _requirement("second", CommercialPassportRequirementStatus.SATISFIED),
                    ),
                ),
            ),
        )


def test_commercial_passport_dossier_section_freezes_dynamic_projection() -> None:
    passport = PropertyCommercialPassportService().build(
        context=_context(),
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("synthetic-eu"),
                requirements=(
                    _requirement("traceability", CommercialPassportRequirementStatus.SATISFIED),
                    _requirement("environment", CommercialPassportRequirementStatus.MISSING),
                ),
                population_eligibility=PopulationEligibilitySummary(
                    subject_type="animal",
                    counts_by_status={MarketReadinessStatus.READY.value: 10},
                ),
            ),
        ),
    )

    section = CommercialPassportDossierSectionBuilder().build(
        passport=passport,
        issued_at=NOW,
    )

    snapshot = section.content["commercial_passport"]
    assert section.namespace == "livestock"
    assert snapshot["status"] == "FORMAL_ISSUED_SNAPSHOT"
    assert snapshot["subject_scope"] == "property"
    assert snapshot["temporal_context"] == {
        "reference_time": NOW.isoformat(),
        "knowledge_cutoff": NOW.isoformat(),
        "evaluated_at": NOW.isoformat(),
        "issued_at": NOW.isoformat(),
    }
    assert snapshot["opportunities"][0]["opportunity"]["code"] == "synthetic-eu"
    assert snapshot["opportunities"][0]["property_readiness"]["breakdown"]["satisfied"] == 1
    assert snapshot["opportunities"][0]["property_readiness"]["breakdown"]["missing"] == 1
    assert snapshot["opportunities"][0]["population_eligibility"]["total_count"] == 10
    assert "not a Decision" in snapshot["non_goals"]


def test_commercial_passport_section_refuses_issuance_before_evaluation() -> None:
    passport = PropertyCommercialPassportService().build(
        context=_context(),
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity(),
                requirements=(
                    _requirement("traceability", CommercialPassportRequirementStatus.SATISFIED),
                ),
            ),
        ),
    )

    with pytest.raises(ValueError, match="issued_at"):
        CommercialPassportDossierSectionBuilder().build(
            passport=passport,
            issued_at=NOW - timedelta(seconds=1),
        )


def test_commercial_passport_section_travels_inside_existing_verification_bundle() -> None:
    passport = PropertyCommercialPassportService().build(
        context=_context(),
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("synthetic-eu"),
                requirements=(
                    _requirement("traceability", CommercialPassportRequirementStatus.SATISFIED),
                ),
            ),
        ),
    )
    section = CommercialPassportDossierSectionBuilder().build(
        passport=passport,
        issued_at=NOW,
    )
    document = {
        "document_version": 5,
        "serialization": "titan-json-v1",
        "generated_at": NOW.isoformat(),
        "organization_id": str(passport.context.organization_id.value),
        "subject": {
            "entity_type": passport.context.property_id.entity_type,
            "id": str(passport.context.property_id.value),
        },
        "purpose": "commercial-passport",
        "vertical": section.to_dict(),
    }
    dossier = Dossier(
        dossier_id=TypedId.new("dossier"),
        organization_id=passport.context.organization_id,
        subject_reference=UniversalReference(
            passport.context.property_id, passport.context.organization_id, 1
        ),
        purpose="commercial-passport",
        decision_id=TypedId.new("decision"),
        evaluation_id=TypedId.new("evaluation"),
        generated_at=NOW,
        document=document,
        dossier_hash=compute_dossier_hash(document),
    )

    bundle = VerificationBundleService(
        dossier_interpreters=(LivestockVerificationBundleInterpreter(),),
    ).build_from_dossier(
        dossier=dossier,
        audience="commercial-audit",
        created_at=NOW,
    )

    assert dossier.verify()
    assert "commercial_passport_snapshot" in bundle.manifest.declared_scopes
    assert (
        "commercial_passport_boundary:MARKET_ELIGIBILITY_ASSESSMENT_NOT_EXPORT_AUTHORIZATION"
        in bundle.manifest.declared_scopes
    )
    assert any(
        "does not authorize public disclosure" in gap for gap in bundle.manifest.declared_gaps
    )


def test_market_readiness_pipeline_builds_property_passport_from_existing_report() -> None:
    context = _context()
    opportunity = _opportunity("eu")
    report = _market_readiness_report(
        context=context,
        opportunity=opportunity,
        ready=2,
        not_ready=1,
        indeterminate=1,
    )

    passport = PropertyCommercialPassportMarketReadinessPipeline(
        sources=(
            CommercialPassportMarketReadinessSource(
                opportunity=opportunity,
                report=report,
            ),
        ),
    ).build_property_passport(context=context)

    assessment = passport.opportunities[0]
    assert assessment.property_readiness.breakdown.satisfied == 1
    assert assessment.property_readiness.breakdown.interpretation is (
        CommercialReadinessInterpretation.AVAILABLE
    )
    requirement = assessment.property_readiness.requirements[0]
    assert requirement.status is CommercialPassportRequirementStatus.SATISFIED
    assert requirement.reason_codes == ("MARKET_READINESS_REPORT_AVAILABLE",)
    assert assessment.population_eligibility is not None
    assert assessment.population_eligibility.ready_count == 2
    assert assessment.population_eligibility.not_ready_count == 1
    assert assessment.population_eligibility.indeterminate_count == 1
    assert "derived from MarketReadiness; not a Decision" in (
        assessment.population_eligibility.limitations
    )


def test_market_readiness_pipeline_keeps_missing_report_as_property_gap() -> None:
    context = _context()
    opportunity = _opportunity("buyer-x")

    passport = PropertyCommercialPassportMarketReadinessPipeline(
        sources=(
            CommercialPassportMarketReadinessSource(
                opportunity=opportunity,
                report=None,
            ),
        ),
    ).build_property_passport(context=context)

    assessment = passport.opportunities[0]
    assert assessment.population_eligibility is None
    assert assessment.property_readiness.breakdown.missing == 1
    assert assessment.property_readiness.requirements[0].status is (
        CommercialPassportRequirementStatus.MISSING
    )
    assert "market readiness report unavailable" in assessment.limitations


def test_market_readiness_pipeline_rejects_temporal_context_mismatch() -> None:
    context = _context()
    opportunity = _opportunity("eu")
    divergent_context = CommercialPassportContext(
        organization_id=context.organization_id,
        property_id=context.property_id,
        reference_time=context.reference_time - timedelta(days=1),
        knowledge_cutoff=context.knowledge_cutoff,
        evaluated_at=context.evaluated_at,
    )
    report = _market_readiness_report(context=divergent_context, opportunity=opportunity)

    with pytest.raises(ValueError, match="reference_time"):
        PropertyCommercialPassportMarketReadinessPipeline(
            sources=(
                CommercialPassportMarketReadinessSource(
                    opportunity=opportunity,
                    report=report,
                ),
            ),
        ).build_property_passport(context=context)


def test_formal_issuance_uses_dossier_service_and_verification_bundle_service() -> None:
    context = _context()
    passport = PropertyCommercialPassportService().build(
        context=context,
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("formal-eu"),
                requirements=(
                    _requirement("traceability", CommercialPassportRequirementStatus.SATISFIED),
                ),
            ),
        ),
    )
    decision, evaluation, policy = _issuance_artifacts(context)
    repository = _DossierRepository()

    issued = CommercialPassportFormalIssuanceService(
        dossier_service=DossierService(repository=repository),
        verification_bundle_service=VerificationBundleService(
            dossier_interpreters=(LivestockVerificationBundleInterpreter(),),
        ),
    ).issue(
        passport=passport,
        decision=decision,
        evaluation=evaluation,
        policy=policy,
        audience="commercial-audit",
        issued_at=NOW,
    )

    assert repository.saved == [issued.dossier]
    assert issued.dossier.verify()
    assert issued.dossier.subject_reference.target_id == context.property_id
    snapshot = issued.dossier.document["vertical"]["content"]["commercial_passport"]
    assert snapshot["status"] == "FORMAL_ISSUED_SNAPSHOT"
    assert snapshot["opportunities"][0]["opportunity"]["code"] == "formal-eu"
    assert issued.verification_bundle.manifest.audience == "commercial-audit"
    assert "commercial_passport_snapshot" in (issued.verification_bundle.manifest.declared_scopes)
    assert issued.verification_bundle.payloads["dossier.json"]


def test_formal_issuance_requires_property_anchor_decision() -> None:
    context = _context()
    passport = PropertyCommercialPassportService().build(
        context=context,
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("formal-eu"),
                requirements=(
                    _requirement("traceability", CommercialPassportRequirementStatus.SATISFIED),
                ),
            ),
        ),
    )
    decision, evaluation, policy = _issuance_artifacts(
        context,
        subject_id=TypedId.new("animal"),
    )

    with pytest.raises(ValueError, match="propriedade"):
        CommercialPassportFormalIssuanceService(
            dossier_service=DossierService(repository=_DossierRepository()),
            verification_bundle_service=VerificationBundleService(),
        ).issue(
            passport=passport,
            decision=decision,
            evaluation=evaluation,
            policy=policy,
            audience="commercial-audit",
            issued_at=NOW,
        )


def test_formal_issuance_requires_non_empty_audience() -> None:
    context = _context()
    passport = PropertyCommercialPassportService().build(
        context=context,
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("formal-eu"),
                requirements=(
                    _requirement("traceability", CommercialPassportRequirementStatus.SATISFIED),
                ),
            ),
        ),
    )
    decision, evaluation, policy = _issuance_artifacts(context)

    with pytest.raises(ValueError, match="audience"):
        CommercialPassportFormalIssuanceService(
            dossier_service=DossierService(repository=_DossierRepository()),
            verification_bundle_service=VerificationBundleService(),
        ).issue(
            passport=passport,
            decision=decision,
            evaluation=evaluation,
            policy=policy,
            audience=" ",
            issued_at=NOW,
        )
