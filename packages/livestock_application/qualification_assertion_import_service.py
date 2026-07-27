"""Importação e reconciliação de asserções de qualificação (ADR-0045).

Este serviço NUNCA aceita `confidence` do chamador: a confiança é computada
pelo Titan a partir do caminho de proveniência da importação (quem
autenticou a chamada, se é integração automatizada verificada, se há
assinatura validada). Um cliente HTTP que pudesse declarar
`CRYPTOGRAPHICALLY_ATTESTED` estaria escolhendo o próprio grau de confiança,
o que a ADR-0042 já proíbe ao tratar confiança como resultado da qualidade
da fonte, não como afirmação livre.

Ausência de um estabelecimento em uma nova importação só produz uma
Assertion derivada (`UNKNOWN`) quando o snapshot anterior mais recente e o
atual são ambos `COMPLETE_SNAPSHOT` — nunca a partir de `PARTIAL`, `DELTA`
ou `UNKNOWN`. E mesmo nesse caso, a Assertion derivada nunca é
`NOT_QUALIFIED`: o fato apenas registra que a mudança ocorreu em algum
ponto do intervalo, sem inventar quando. Decidir o que essa ausência
significa para uma finalidade de mercado é responsabilidade da Policy,
não deste serviço.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_application.external_counterparty_service import (
    ExternalCounterpartyRepositoryPort,
)
from packages.livestock_domain.establishment_qualification_assertion import (
    AssertionStatus,
    EstablishmentQualificationAssertion,
)
from packages.livestock_domain.qualification_source_artifact import (
    QualificationSourceArtifact,
    SourceCoverage,
)
from packages.shared_kernel import OrganizationId, TypedId


class QualificationSourceArtifactRepositoryPort(Protocol):
    def save(self, artifact: QualificationSourceArtifact) -> None: ...

    def find_by_identity(
        self, organization_id: OrganizationId, source: str, source_version: str
    ) -> QualificationSourceArtifact | None: ...

    def find_latest_complete_snapshot(
        self, organization_id: OrganizationId, source: str
    ) -> QualificationSourceArtifact | None: ...


class EstablishmentQualificationAssertionRepositoryPort(Protocol):
    def save(self, assertion: EstablishmentQualificationAssertion) -> None: ...

    def list_by_establishment(
        self, organization_id: OrganizationId, establishment_id: TypedId
    ) -> list[EstablishmentQualificationAssertion]: ...

    def list_by_source_artifact(
        self, organization_id: OrganizationId, source_artifact_id: TypedId
    ) -> list[EstablishmentQualificationAssertion]: ...


@dataclass(frozen=True, slots=True)
class QualificationAssertionInput:
    """Um item declarado pela fonte, sem confiança — o Titan a computa."""

    establishment_id: TypedId
    qualification_type: str
    asserted_status: AssertionStatus
    effective_from: datetime | None = None
    effective_until: datetime | None = None


@dataclass(frozen=True, slots=True)
class QualificationAssertionImportResult:
    source_artifact_id: TypedId
    already_imported: bool
    created_assertions: int
    inferred_absence_assertions: int


def compute_confidence(
    *, context: LivestockOperationContext, has_verified_signature: bool = False
) -> ConfidenceTier:
    """Confiança nasce da proveniência da chamada, nunca de um campo do payload.

    Regra mínima atual, enquanto não existir integração automatizada
    verificada com fonte externa (ver ADR-0046, futura): assinatura validada
    produz o nível mais alto; ausência de assinatura, mas com ator do tipo
    `system` (integração automatizada já autenticada), produz confiança
    verificada; caso contrário, é uma submissão documentada por um operador
    autenticado.
    """
    if has_verified_signature:
        return ConfidenceTier.CRYPTOGRAPHICALLY_ATTESTED
    if context.actor_reference.target_id.entity_type == "system":
        return ConfidenceTier.VERIFIED_SOURCE
    return ConfidenceTier.DOCUMENTED


@dataclass(frozen=True, slots=True)
class QualificationAssertionImportService:
    artifact_repository: QualificationSourceArtifactRepositoryPort
    assertion_repository: EstablishmentQualificationAssertionRepositoryPort
    counterparty_repository: ExternalCounterpartyRepositoryPort

    def import_assertions(
        self,
        *,
        context: LivestockOperationContext,
        source: str,
        source_version: str,
        content_hash: str,
        snapshot_semantics: SourceCoverage,
        observed_at: datetime,
        assertions: list[QualificationAssertionInput],
        has_verified_signature: bool = False,
    ) -> QualificationAssertionImportResult:
        if not assertions:
            raise ValueError("A importacao precisa declarar ao menos uma asserção.")

        for item in assertions:
            counterparty = self.counterparty_repository.get_by_id(item.establishment_id)
            if counterparty is None or counterparty.organization_id != context.organization_id:
                raise KeyError(f"Estabelecimento '{item.establishment_id.value}' nao encontrado.")

        existing = self.artifact_repository.find_by_identity(
            context.organization_id, source, source_version
        )
        if existing is not None:
            return QualificationAssertionImportResult(
                source_artifact_id=existing.artifact_id,
                already_imported=True,
                created_assertions=0,
                inferred_absence_assertions=0,
            )

        confidence = compute_confidence(
            context=context, has_verified_signature=has_verified_signature
        )

        # Precisa ser lido ANTES de gravar o novo artefato: uma vez salvo, o
        # próprio artefato novo (se COMPLETE_SNAPSHOT) passaria a ser
        # candidato a "última snapshot completa", mascarando a comparação
        # contra a versão anterior de verdade.
        previous_complete_snapshot = (
            self.artifact_repository.find_latest_complete_snapshot(context.organization_id, source)
            if snapshot_semantics == SourceCoverage.COMPLETE_SNAPSHOT
            else None
        )

        artifact = QualificationSourceArtifact.create(
            organization_id=context.organization_id,
            source=source,
            source_version=source_version,
            content_hash=content_hash,
            snapshot_semantics=snapshot_semantics,
            observed_at=observed_at,
        )
        self.artifact_repository.save(artifact)

        created = 0
        for item in assertions:
            assertion = EstablishmentQualificationAssertion.create(
                organization_id=context.organization_id,
                establishment_id=item.establishment_id,
                qualification_type=item.qualification_type,
                asserted_status=item.asserted_status,
                effective_from=item.effective_from,
                effective_until=item.effective_until,
                observed_at=observed_at,
                source_artifact_id=artifact.artifact_id,
                confidence_tier=confidence,
            )
            self.assertion_repository.save(assertion)
            created += 1

        inferred = self._reconcile_absences(
            context=context,
            new_artifact=artifact,
            previous_complete_snapshot=previous_complete_snapshot,
            new_assertions=assertions,
            confidence=confidence,
        )

        return QualificationAssertionImportResult(
            source_artifact_id=artifact.artifact_id,
            already_imported=False,
            created_assertions=created,
            inferred_absence_assertions=inferred,
        )

    def _reconcile_absences(
        self,
        *,
        context: LivestockOperationContext,
        new_artifact: QualificationSourceArtifact,
        previous_complete_snapshot: QualificationSourceArtifact | None,
        new_assertions: list[QualificationAssertionInput],
        confidence: ConfidenceTier,
    ) -> int:
        """Ausência só é interpretada quando ambos os snapshots são completos.

        `DELTA`, `PARTIAL` e `UNKNOWN` não autorizam nenhuma inferência: a
        falta de um item ali não informa nada sobre o universo completo.
        """
        if previous_complete_snapshot is None:
            return 0

        previous_assertions = self.assertion_repository.list_by_source_artifact(
            context.organization_id, previous_complete_snapshot.artifact_id
        )
        previously_qualified = {
            (assertion.establishment_id, assertion.qualification_type)
            for assertion in previous_assertions
            if assertion.asserted_status == AssertionStatus.QUALIFIED
        }

        currently_present = {
            (item.establishment_id, item.qualification_type) for item in new_assertions
        }

        missing = previously_qualified - currently_present

        inferred = 0
        for establishment_id, qualification_type in missing:
            derived = EstablishmentQualificationAssertion.create(
                organization_id=context.organization_id,
                establishment_id=establishment_id,
                qualification_type=qualification_type,
                asserted_status=AssertionStatus.UNKNOWN,
                effective_from=None,
                effective_until=None,
                observed_at=new_artifact.observed_at,
                source_artifact_id=new_artifact.artifact_id,
                confidence_tier=confidence,
            )
            self.assertion_repository.save(derived)
            inferred += 1

        return inferred
