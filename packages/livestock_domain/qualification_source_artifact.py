"""Artefato de origem de uma importação de qualificações (ADR-0045).

Não é `ReceivedTransferArtifact` (ADR-0042): aquele caracteriza transferência
de custódia de um animal entre Organizations. Este artefato apenas registra
que uma fonte externa (MAPA, frigorífico, etc.) foi consultada em um instante,
com uma semântica de cobertura declarada, produzindo um conjunto de asserções.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class SourceCoverage(StrEnum):
    """O que a fonte declara representar, e portanto o que a ausência significa.

    COMPLETE_SNAPSHOT: a fonte representa integralmente o universo consultado.
    A ausência de um elemento é uma observação significativa de não-presença
    naquele snapshot — mas isso NÃO se converte automaticamente em
    NOT_QUALIFIED. Produz apenas uma Assertion com status UNKNOWN; o
    significado normativo da ausência pertence à Policy, nunca ao fato.

    DELTA: a fonte representa apenas mudanças desde a versão anterior.
    Ausência não informa nada sobre o estado anterior.

    PARTIAL: a fonte representa apenas um subconjunto (região, programa,
    página). Ausência não significa ausência no universo completo. Nenhuma
    Assertion derivada de ausência é criada.

    UNKNOWN: semântica da cobertura é desconhecida. Falha segura: nenhuma
    Assertion derivada de ausência é criada.
    """

    COMPLETE_SNAPSHOT = "COMPLETE_SNAPSHOT"
    DELTA = "DELTA"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class QualificationSourceArtifact:
    """Identidade de uma importação: fonte, versão, cobertura e hash.

    `source_version` e `content_hash` vivem aqui, e não replicados em cada
    Assertion, porque são propriedades da importação como um todo. A chave
    de idempotência é (organization_id, source, source_version): reimportar
    a mesma versão localiza este artefato e não cria um novo.
    """

    artifact_id: TypedId
    organization_id: OrganizationId
    source: str
    source_version: str
    content_hash: str
    snapshot_semantics: SourceCoverage
    observed_at: datetime
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.observed_at, field_name="observed_at")
        require_utc(self.recorded_at, field_name="recorded_at")
        if self.artifact_id.entity_type != "qualification_source_artifact":
            raise ValueError("artifact_id deve ter entity_type 'qualification_source_artifact'.")
        if not self.source.strip():
            raise ValueError("source nao pode ser vazio.")
        if not self.source_version.strip():
            raise ValueError("source_version nao pode ser vazio.")
        if not self.content_hash.strip():
            raise ValueError("content_hash nao pode ser vazio.")
        if not isinstance(self.snapshot_semantics, SourceCoverage):
            raise TypeError("snapshot_semantics deve ser SourceCoverage.")

    @classmethod
    def create(
        cls,
        *,
        organization_id: OrganizationId,
        source: str,
        source_version: str,
        content_hash: str,
        snapshot_semantics: SourceCoverage,
        observed_at: datetime,
    ) -> "QualificationSourceArtifact":
        return cls(
            artifact_id=TypedId.new("qualification_source_artifact"),
            organization_id=organization_id,
            source=source.strip(),
            source_version=source_version.strip(),
            content_hash=content_hash.strip(),
            snapshot_semantics=snapshot_semantics,
            observed_at=observed_at,
        )

    def allows_absence_inference(self) -> bool:
        """Só um snapshot completo autoriza inferir mudança a partir de ausência."""
        return self.snapshot_semantics == SourceCoverage.COMPLETE_SNAPSHOT
