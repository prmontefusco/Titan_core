"""Template Livestock do dossiê da decisão farmacológica (Passo 10.2).

Monta a seção de vertical que acompanha o documento do Core. O Core prova a
decisão — política, regras, fatos, avaliação, razões. A seção da vertical
acrescenta o que só a pecuária sabe dizer:

1. **Identidade que um fiscal usa.** Um auditor não confere UUID contra um boi;
   confere brinco e SISBOV. Os identificadores vêm do fato `livestock.animal`
   dentro do snapshot, e não do cadastro atual — o snapshot está congelado no
   instante da avaliação, o cadastro não.
2. **A conta da carência**, com o prazo congelado de cada aplicação.
3. **A cadeia até a evidência**: contribuição → aplicação → evidências, com hash
   de conteúdo e proveniência copiados.
4. **A linha do tempo do animal**, cortada em `known_until` no instante da
   decisão. É o eixo de auditoria: um lançamento posterior não pode aparecer numa
   prova emitida antes, senão o dossiê deixa de ser reproduzível.

**Por que o bloco `evidences` do Core fica vazio aqui.** Aquele bloco é
alimentado por `Fact.source_reference`, que é singular — serve ao fato que veio
de um documento. A carência não vem de um documento: vem de um cálculo sobre N
aplicações, cada uma com suas evidências. Declarar uma única fonte seria escolher
arbitrariamente uma delas. `source_reference` fica nulo, que é a resposta honesta,
e a cadeia completa viaja aqui, onde cabe.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from packages.core_application.dossier_service import DossierService, evidence_content
from packages.core_domain.decision import Decision
from packages.core_domain.dossier import Dossier, VerticalSection
from packages.core_domain.evaluation import Evaluation
from packages.core_domain.evidence import Evidence
from packages.core_domain.policy import Policy
from packages.core_domain.rule import Rule
from packages.livestock_application.eligibility import GovernedRuleReference
from packages.livestock_application.fact_provider import WITHDRAWAL_FACT_TYPE
from packages.livestock_application.timeline_service import (
    LivestockTimelineService,
    TimelineCutoff,
    TimelineEntry,
)
from packages.livestock_application.treatment_service import (
    EvidenceLookupPort,
    TreatmentApplicationRepositoryPort,
)
from packages.shared_kernel import OrganizationId, TypedId

LIVESTOCK_NAMESPACE = "livestock"
SECTION_VERSION = 1
ANIMAL_FACT_TYPE = "livestock.animal"


@dataclass(frozen=True, slots=True)
class LivestockDossierTemplate:
    """Produz o dossiê da decisão farmacológica, com a seção da vertical."""

    timeline_service: LivestockTimelineService
    application_repository: TreatmentApplicationRepositoryPort
    evidence_lookup: EvidenceLookupPort
    dossier_service: DossierService = DossierService()

    def build(
        self,
        decision: Decision,
        evaluation: Evaluation,
        policy: Policy,
        rules: Sequence[Rule] = (),
        generated_at: datetime | None = None,
        governed_rule: GovernedRuleReference | None = None,
    ) -> Dossier:
        if decision.subject_id.entity_type != "animal":
            raise ValueError(
                "O template farmacológico monta dossiê de animal; recebido "
                f"'{decision.subject_id.entity_type}'."
            )
        return self.dossier_service.build(
            decision=decision,
            evaluation=evaluation,
            policy=policy,
            rules=rules,
            generated_at=generated_at,
            vertical_section=self.build_section(
                decision,
                evaluation,
                governed_rule=governed_rule,
            ),
        )

    def build_section(
        self,
        decision: Decision,
        evaluation: Evaluation,
        governed_rule: GovernedRuleReference | None = None,
    ) -> VerticalSection:
        organization_id = decision.organization_id
        animal_id = decision.subject_id
        withdrawal = _fact_payload(evaluation, WITHDRAWAL_FACT_TYPE)

        return VerticalSection(
            namespace=LIVESTOCK_NAMESPACE,
            section_version=SECTION_VERSION,
            content={
                "subject": self._subject(animal_id, evaluation),
                "withdrawal": withdrawal,
                "evidence_chain": self._evidence_chain(organization_id, withdrawal),
                "timeline": self._timeline(organization_id, animal_id, decision.issued_at),
                "governed_rule": None if governed_rule is None else governed_rule.to_dict(),
            },
        )

    def _subject(self, animal_id: TypedId, evaluation: Evaluation) -> dict[str, Any]:
        """Identidade lida do snapshot, que está congelado; não do cadastro atual."""
        animal = _fact_payload(evaluation, ANIMAL_FACT_TYPE)
        return {
            "animal_id": str(animal_id.value),
            "identifiers": animal.get("identifiers", []),
            "sex": animal.get("sex"),
            "breed": animal.get("breed"),
            "identity_source": "fact_snapshot",
        }

    def _evidence_chain(
        self, organization_id: OrganizationId, withdrawal: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Uma entrada por contribuição, ligando o cálculo às provas que o sustentam."""
        chain: list[dict[str, Any]] = []
        for contribution in withdrawal.get("contributions", []):
            if contribution.get("origin") == "IMPORTED_ASSERTION":
                chain.append(
                    {
                        "imported_fact_id": contribution["imported_fact_id"],
                        "source_artifact_id": contribution["source_artifact_id"],
                        "status": "AFIRMACAO_IMPORTADA",
                        "asserted_by": contribution.get("asserted_by"),
                        "confidence_tier": contribution.get("confidence_tier"),
                        "evidences": [],
                        "notes": [],
                    }
                )
                continue

            application_id = TypedId.parse(
                "treatment_application", _uuid_text(contribution["application_id"])
            )
            application = self.application_repository.get_by_id(application_id)
            if application is None or application.organization_id != organization_id:
                chain.append(
                    {
                        "application_id": str(application_id.value),
                        "status": "APLICACAO_NAO_ENCONTRADA",
                        "evidences": [],
                        "notes": [],
                    }
                )
                continue

            chain.append(
                {
                    "application_id": str(application_id.value),
                    "status": "RESOLVIDA",
                    "applied_at": application.applied_at.isoformat(),
                    "dose": application.dose,
                    "prescription_id": (
                        str(application.prescription_id.value)
                        if application.prescription_id is not None
                        else None
                    ),
                    # Anotação de operador viaja identificada como tal: é informação
                    # útil e não é prova, e o dossiê não pode confundir as duas.
                    "notes": list(application.evidence_notes),
                    "evidences": self._evidences_of(application.evidence_references),
                }
            )
        return chain

    def _evidences_of(self, references: Sequence[Any]) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []
        for reference in references:
            evidence: Evidence | None = self.evidence_lookup.get_by_id(reference.target_id)
            entry: dict[str, Any] = {"id": str(reference.target_id.value)}
            if evidence is None:
                entry["content_status"] = "NAO_ACOMPANHA"
                entry["content"] = None
            else:
                entry["content_status"] = "COPIADO"
                entry["content"] = evidence_content(evidence)
            resolved.append(entry)
        return resolved

    def _timeline(
        self, organization_id: OrganizationId, animal_id: TypedId, issued_at: datetime
    ) -> dict[str, Any]:
        entries = self.timeline_service.animal_timeline(
            organization_id, animal_id, TimelineCutoff(known_until=issued_at)
        )
        return {
            "known_until": issued_at.isoformat(),
            "cutoff_axis": "recorded_at",
            "entry_count": len(entries),
            "entries": [_timeline_entry(entry) for entry in entries],
        }


def _fact_payload(evaluation: Evaluation, fact_type: str) -> dict[str, Any]:
    fact = evaluation.fact_snapshot.get_latest_fact_by_type(fact_type)
    return {} if fact is None else dict(fact.payload)


def _uuid_text(value: str) -> str:
    """O snapshot guarda UUID em hexadecimal sem hífen; `TypedId.parse` aceita ambos."""
    return value


def _timeline_entry(entry: TimelineEntry) -> dict[str, Any]:
    return {
        "occurred_at": entry.occurred_at.isoformat(),
        "recorded_at": entry.recorded_at.isoformat(),
        "entry_type": entry.entry_type,
        "source_kind": entry.source_kind.value,
        "source_id": str(entry.source_id.value),
        "aggregate_type": entry.aggregate_id.entity_type,
        "aggregate_id": str(entry.aggregate_id.value),
        "sequence": entry.sequence,
        "actor_id": (
            None if entry.actor_reference is None else str(entry.actor_reference.target_id.value)
        ),
        "correlation_id": (
            None if entry.correlation_id is None else str(entry.correlation_id.value)
        ),
        "payload_schema": entry.payload_schema,
        "superseded_by": (None if entry.superseded_by is None else str(entry.superseded_by.value)),
    }
