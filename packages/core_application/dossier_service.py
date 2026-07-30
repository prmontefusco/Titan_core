"""Caso de uso para montagem do Dossier autocontido (Passo 7.5)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from packages.core_domain.crypto import KeyIdentifier
from packages.core_domain.decision import Decision
from packages.core_domain.decision_governance import (
    ContestationRecord,
    DecisionOverride,
    DecisionProposal,
    DecisionReview,
)
from packages.core_domain.dossier import (
    DOSSIER_DOCUMENT_VERSION,
    Dossier,
    VerticalSection,
    compute_dossier_hash,
)
from packages.core_domain.dossier_pdf import DossierPdfRepresentation
from packages.core_domain.evaluation import Evaluation
from packages.core_domain.evidence import Evidence
from packages.core_domain.nonconformity import NonConformity
from packages.core_domain.policy import Policy
from packages.core_domain.rule import Rule
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.serialization import CanonicalSerializer


class DossierRepositoryPort(Protocol):
    def save(self, dossier: Dossier) -> None: ...

    def get_by_id(self, dossier_id: TypedId) -> Dossier | None: ...

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[Dossier]: ...


class DossierPdfPort(Protocol):
    def generate_pdf(
        self,
        dossier: Dossier,
        signing_provider: Any | None = None,
        key_id: KeyIdentifier | None = None,
    ) -> DossierPdfRepresentation: ...


@dataclass(frozen=True, slots=True)
class DossierService:
    """Monta o dossiê copiando o conteúdo, nunca apenas referenciando.

    Um dossiê que só guardasse identificadores exigiria o banco do Titan para ser
    compreendido, e é exatamente isso que ele existe para evitar.
    """

    repository: DossierRepositoryPort | None = None
    pdf_port: DossierPdfPort | None = None

    def generate_pdf(
        self,
        dossier: Dossier,
        signing_provider: Any | None = None,
        key_id: KeyIdentifier | None = None,
    ) -> DossierPdfRepresentation:
        if self.pdf_port is None:
            raise RuntimeError("Geração de PDF exige porta de PDF (pdf_port) configurada.")
        return self.pdf_port.generate_pdf(dossier, signing_provider=signing_provider, key_id=key_id)

    def build(
        self,
        decision: Decision,
        evaluation: Evaluation,
        policy: Policy,
        rules: Sequence[Rule] = (),
        nonconformities: Sequence[NonConformity] = (),
        generated_at: datetime | None = None,
        evidences: Sequence[Evidence] = (),
        vertical_section: VerticalSection | None = None,
        proposal: DecisionProposal | None = None,
        reviews: Sequence[DecisionReview] = (),
        override: DecisionOverride | None = None,
        contestations: Sequence[ContestationRecord] = (),
    ) -> Dossier:
        """`evidences` são as evidências citadas pela decisão, para terem o conteúdo copiado.

        Quem não as fornece obtém o mesmo documento de antes: as entradas trazem o
        identificador e declaram que o conteúdo não acompanha. Omitir em silêncio
        seria pior — quem lê precisa distinguir "não havia evidência" de "havia e
        não veio junto".
        """
        self._guard_coherence(decision, evaluation, policy)

        instante = generated_at or datetime.now(UTC)
        documento = self._build_document(
            decision,
            evaluation,
            policy,
            rules,
            nonconformities,
            instante,
            evidences,
            vertical_section,
            proposal,
            reviews,
            override,
            contestations,
        )

        return Dossier(
            dossier_id=TypedId.new("dossier"),
            organization_id=decision.organization_id,
            subject_reference=UniversalReference(
                target_id=decision.subject_id,
                organization_id=decision.organization_id,
                contract_version=1,
            ),
            purpose=decision.purpose,
            decision_id=decision.decision_id,
            evaluation_id=evaluation.evaluation_id,
            generated_at=instante,
            document=documento,
            dossier_hash=compute_dossier_hash(documento),
        )

    def build_and_store(self, *args: Any, **kwargs: Any) -> Dossier:
        if self.repository is None:
            raise RuntimeError("Persistir o dossiê exige repositório configurado.")
        dossier = self.build(*args, **kwargs)
        self.repository.save(dossier)
        return dossier

    # -- Coerência ---------------------------------------------------------

    def _guard_coherence(self, decision: Decision, evaluation: Evaluation, policy: Policy) -> None:
        if decision.evaluation_id != evaluation.evaluation_id:
            raise ValueError("A decisão não pertence à avaliação informada.")
        if decision.policy_id != policy.policy_id:
            raise ValueError("A decisão não pertence à política informada.")
        # Dossiê é prova: montar sobre material adulterado produziria prova falsa.
        if not evaluation.is_reproducible():
            raise ValueError("Evaluation não reproduzível: não pode compor dossiê.")
        if not decision.is_reproducible():
            raise ValueError("Decision não reproduzível: não pode compor dossiê.")

    # -- Documento ---------------------------------------------------------

    def _build_document(
        self,
        decision: Decision,
        evaluation: Evaluation,
        policy: Policy,
        rules: Sequence[Rule],
        nonconformities: Sequence[NonConformity],
        generated_at: datetime,
        evidences: Sequence[Evidence] = (),
        vertical_section: VerticalSection | None = None,
        proposal: DecisionProposal | None = None,
        reviews: Sequence[DecisionReview] = (),
        override: DecisionOverride | None = None,
        contestations: Sequence[ContestationRecord] = (),
    ) -> dict[str, Any]:
        return {
            "document_version": DOSSIER_DOCUMENT_VERSION,
            "serialization": CanonicalSerializer.version,
            "generated_at": generated_at.isoformat(),
            "organization_id": str(decision.organization_id.value),
            "subject": {
                "entity_type": decision.subject_id.entity_type,
                "id": str(decision.subject_id.value),
            },
            "purpose": decision.purpose,
            "policy": {
                "policy_id": str(policy.policy_id.value),
                "code": policy.code,
                "name": policy.name,
                "description": policy.description,
                "version": policy.version,
                "status": policy.status.value,
                "valid_from": policy.valid_from.isoformat() if policy.valid_from else None,
                "valid_to": policy.valid_to.isoformat() if policy.valid_to else None,
            },
            # As regras entram com suas condições declarativas: sem elas ninguém
            # conseguiria refazer a avaliação apenas com o dossiê.
            "rules": [
                {
                    "rule_id": str(r.rule_id.value),
                    "code": r.code,
                    "name": r.name,
                    "description": r.description,
                    "version": r.version,
                    "severity": r.severity.value,
                    "normative_source": r.normative_source,
                    "required_evidence_types": list(r.required_evidence_types),
                    "conditions": [c.to_dict() for c in r.conditions],
                    "justification": r.justification,
                    "corrective_action": r.corrective_action,
                    "valid_from": r.valid_from.isoformat() if r.valid_from else None,
                    "valid_to": r.valid_to.isoformat() if r.valid_to else None,
                }
                for r in rules
            ],
            # O snapshot completo dos fatos, e não apenas seu hash.
            "facts": evaluation.fact_snapshot.to_dict(),
            "evaluation": {
                "evaluation_id": str(evaluation.evaluation_id.value),
                "policy_version": evaluation.policy_version,
                "outcome": evaluation.outcome.value,
                "engine_version": evaluation.engine_version,
                "evaluated_at": evaluation.evaluated_at.isoformat(),
                "snapshot_hash": evaluation.fact_snapshot.snapshot_hash,
                "evaluation_hash": evaluation.evaluation_hash,
                "rule_versions": [
                    {"code": code, "version": version} for code, version in evaluation.rule_versions
                ],
                "rule_results": [r.to_dict() for r in evaluation.rule_results],
            },
            "decision": {
                "decision_id": str(decision.decision_id.value),
                "result": decision.result.value,
                "issued_at": decision.issued_at.isoformat(),
                "engine_version": decision.engine_version,
                "decision_hash": decision.decision_hash,
                "reasons": [r.to_dict() for r in decision.reasons],
                "corrective_actions": list(decision.corrective_actions),
                # ADR-0055 §6: o Dossier preserva a cadeia de autoridade e
                # emissão -- quem decidiu, sob qual perfil e por qual método --
                # e não apenas o resultado.
                "authority_profile_id": str(decision.authority_profile_id.value),
                "authority_reference": {
                    "entity_type": decision.authority_reference.target_id.entity_type,
                    "id": str(decision.authority_reference.target_id.value),
                },
                "emission_method": decision.emission_method.value,
                "affected_subjects": [
                    {
                        "entity_type": s.target_id.entity_type,
                        "id": str(s.target_id.value),
                    }
                    for s in decision.affected_subjects
                ],
            },
            "governance": {
                "proposal": None if proposal is None else self._proposal_entry(proposal),
                "reviews": [self._review_entry(review) for review in reviews],
                "override": None if override is None else self._override_entry(override),
                "contestations": [
                    self._contestation_entry(contestation) for contestation in contestations
                ],
            },
            "evidences": [
                self._evidence_entry(reference, evidences)
                for reference in decision.evidence_references
            ],
            # O Core entrega o envelope e não olha o conteúdo: conhecer vertical
            # lhe é proibido. Ausente, o campo é nulo em vez de sumir.
            "vertical": None if vertical_section is None else vertical_section.to_dict(),
            "nonconformities": [
                {
                    "nonconformity_id": str(n.nonconformity_id.value),
                    "origin": n.origin.value,
                    "severity": n.severity.value,
                    "status": n.status.value,
                    "description": n.description,
                    "detected_at": n.detected_at.isoformat(),
                    "corrective_action": n.corrective_action,
                    "closed_at": n.closed_at.isoformat() if n.closed_at else None,
                    "transitions": [t.to_dict() for t in n.transitions],
                }
                for n in nonconformities
            ],
        }

    # -- Evidências --------------------------------------------------------

    @staticmethod
    def _evidence_entry(
        reference: UniversalReference, evidences: Sequence[Evidence]
    ) -> dict[str, Any]:
        """Copia o conteúdo da evidência, e não apenas o identificador.

        Um dossiê que dissesse apenas `evidence: <uuid>` exigiria o banco do Titan
        para ser compreendido — exatamente o que ele existe para evitar. Com o hash
        do conteúdo, quem tem o arquivo original confere se é o mesmo, sem nos
        consultar.

        Quando a evidência não acompanha, `content` é nulo e `content_status` diz
        por quê. Ausência declarada é honesta; ausência silenciosa não.
        """
        entry: dict[str, Any] = {
            "entity_type": reference.target_id.entity_type,
            "id": str(reference.target_id.value),
            "contract_version": reference.contract_version,
        }

        found = next(
            (e for e in evidences if e.evidence_id == reference.target_id),
            None,
        )
        if found is None:
            entry["content"] = None
            entry["content_status"] = "NAO_ACOMPANHA"
            return entry

        entry["content_status"] = "COPIADO"
        entry["content"] = evidence_content(found)
        return entry

    @staticmethod
    def _proposal_entry(proposal: DecisionProposal) -> dict[str, Any]:
        return {
            "proposal_id": str(proposal.proposal_id.value),
            "evaluation_id": str(proposal.evaluation_id.value),
            "evaluation_hash": proposal.evaluation_hash,
            "proposed_result": proposal.proposed_result.value,
            "proposed_reasons": [reason.to_dict() for reason in proposal.proposed_reasons],
            "purpose": proposal.purpose,
            "justification_required": proposal.justification_required,
            "created_at": proposal.created_at.isoformat(),
        }

    @staticmethod
    def _review_entry(review: DecisionReview) -> dict[str, Any]:
        return {
            "review_id": str(review.review_id.value),
            "proposal_id": str(review.proposal_id.value),
            "reviewer_reference": {
                "entity_type": review.reviewer_reference.target_id.entity_type,
                "id": str(review.reviewer_reference.target_id.value),
            },
            "reviewer_authority_id": str(review.reviewer_authority_id.value),
            "conclusion": review.conclusion.value,
            "reasoning": review.reasoning,
            "reviewed_at": review.reviewed_at.isoformat(),
        }

    @staticmethod
    def _override_entry(override: DecisionOverride) -> dict[str, Any]:
        return {
            "override_id": str(override.override_id.value),
            "original_decision_id": str(override.original_decision_id.value),
            "authority_profile_id": str(override.authority_profile.authority_id.value),
            "new_result": override.new_result.value,
            "mandatory_reason": override.mandatory_reason,
            "applied_at": override.applied_at.isoformat(),
        }

    @staticmethod
    def _contestation_entry(contestation: ContestationRecord) -> dict[str, Any]:
        return {
            "contestation_id": str(contestation.contestation_id.value),
            "decision_id": str(contestation.decision_id.value),
            "contested_by": {
                "entity_type": contestation.contested_by.target_id.entity_type,
                "id": str(contestation.contested_by.target_id.value),
            },
            "grounds_description": contestation.grounds_description,
            "status": contestation.status.value,
            "filed_at": contestation.filed_at.isoformat(),
            "resolved_at": (
                None if contestation.resolved_at is None else contestation.resolved_at.isoformat()
            ),
            "resolution_notes": contestation.resolution_notes,
        }


def evidence_content(found: Evidence) -> dict[str, Any]:
    """Forma canônica do conteúdo de uma evidência dentro de um dossiê.

    Pública porque a seção de vertical também precisa dela: uma vertical que
    montasse o próprio formato faria o mesmo dado aparecer de duas maneiras no
    mesmo documento, e quem lê teria de aprender as duas.
    """
    return {
        "content_hash": found.content_hash.hex(),
        "hash_algorithm": "SHA-256",
        "registered_at": found.registered_at.isoformat(),
        "version": found.version,
        "author": {
            "entity_type": found.author_reference.target_id.entity_type,
            "id": str(found.author_reference.target_id.value),
        },
        "source": {
            "source_id": str(found.source.source_id.value),
            "source_type": found.source.source_type.value,
            "identifier_uri": found.source.identifier_uri,
        },
        "confidence": {
            "tier": found.confidence_level.tier.value,
            "reason": found.confidence_level.reason,
        },
        "validity": (
            None
            if found.validity_period is None
            else {
                "valid_from": (
                    found.validity_period.valid_from.isoformat()
                    if found.validity_period.valid_from is not None
                    else None
                ),
                "valid_until": (
                    found.validity_period.valid_until.isoformat()
                    if found.validity_period.valid_until is not None
                    else None
                ),
            }
        ),
        # Revogação viaja junto: apresentar evidência revogada como se valesse
        # transformaria o dossiê em prova falsa.
        "revocation": (
            None
            if found.revocation is None
            else {
                "revoked_at": found.revocation.revoked_at.isoformat(),
                "reason": found.revocation.reason,
                "revoking_actor": {
                    "entity_type": found.revocation.revoking_actor.target_id.entity_type,
                    "id": str(found.revocation.revoking_actor.target_id.value),
                },
            }
        ),
        "verifications": [
            {
                "verification_id": str(v.verification_id.value),
                "verified_at": v.verified_at.isoformat(),
                "outcome": v.outcome.value,
                "notes": v.notes,
                "verifier": {
                    "entity_type": v.verifier_reference.target_id.entity_type,
                    "id": str(v.verifier_reference.target_id.value),
                },
            }
            for v in found.verifications
        ],
    }
