"""Caso de uso para montagem do Dossier autocontido (Passo 7.5)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from packages.core_domain.crypto import KeyIdentifier
from packages.core_domain.decision import Decision
from packages.core_domain.dossier import (
    DOSSIER_DOCUMENT_VERSION,
    Dossier,
    compute_dossier_hash,
)
from packages.core_domain.dossier_pdf import DossierPdfRepresentation
from packages.core_domain.evaluation import Evaluation
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
    ) -> Dossier:
        self._guard_coherence(decision, evaluation, policy)

        instante = generated_at or datetime.now(UTC)
        documento = self._build_document(
            decision, evaluation, policy, rules, nonconformities, instante
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
                "affected_subjects": [
                    {
                        "entity_type": s.target_id.entity_type,
                        "id": str(s.target_id.value),
                    }
                    for s in decision.affected_subjects
                ],
            },
            "evidences": [
                {
                    "entity_type": e.target_id.entity_type,
                    "id": str(e.target_id.value),
                    "contract_version": e.contract_version,
                }
                for e in decision.evidence_references
            ],
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
