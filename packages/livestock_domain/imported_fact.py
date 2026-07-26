"""Fato importado de artefato recebido (ADR-0042)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from packages.core_domain.evidence import ConfidenceTier
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class FactOrigin(StrEnum):
    LOCAL_OBSERVATION = "LOCAL_OBSERVATION"
    LOCAL_DECLARATION = "LOCAL_DECLARATION"
    IMPORTED_ASSERTION = "IMPORTED_ASSERTION"


@dataclass(frozen=True, slots=True)
class ImportedLivestockFact:
    imported_fact_id: TypedId
    organization_id: OrganizationId
    animal_id: TypedId
    source_artifact_id: TypedId
    fact_type: str
    occurred_at: datetime
    asserted_by: str
    received_by: TypedId
    confidence_tier: ConfidenceTier
    payload: MappingProxyType[str, Any]
    origin: FactOrigin = FactOrigin.IMPORTED_ASSERTION
    imported_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.occurred_at, field_name="occurred_at")
        require_utc(self.imported_at, field_name="imported_at")
        if self.imported_fact_id.entity_type != "imported_livestock_fact":
            raise ValueError("imported_fact_id deve ter entity_type 'imported_livestock_fact'.")
        if self.animal_id.entity_type != "animal":
            raise ValueError("animal_id deve ter entity_type 'animal'.")
        if self.source_artifact_id.entity_type != "received_transfer_artifact":
            raise ValueError(
                "source_artifact_id deve ter entity_type 'received_transfer_artifact'."
            )
        if not self.fact_type.strip():
            raise ValueError("fact_type nao pode ser vazio.")
        if not self.asserted_by.strip():
            raise ValueError("asserted_by nao pode ser vazio.")
        if self.received_by.entity_type not in {"actor", "user", "system"}:
            raise ValueError("received_by deve apontar para actor, user ou system.")
        if self.origin is not FactOrigin.IMPORTED_ASSERTION:
            raise ValueError("Fato importado deve preservar origin IMPORTED_ASSERTION.")
        if not isinstance(self.confidence_tier, ConfidenceTier):
            raise TypeError("confidence_tier deve ser ConfidenceTier.")

    @classmethod
    def create(
        cls,
        *,
        organization_id: OrganizationId,
        animal_id: TypedId,
        source_artifact_id: TypedId,
        fact_type: str,
        occurred_at: datetime,
        asserted_by: str,
        received_by: TypedId,
        confidence_tier: ConfidenceTier,
        payload: dict[str, Any],
    ) -> "ImportedLivestockFact":
        return cls(
            imported_fact_id=TypedId.new("imported_livestock_fact"),
            organization_id=organization_id,
            animal_id=animal_id,
            source_artifact_id=source_artifact_id,
            fact_type=fact_type,
            occurred_at=occurred_at,
            asserted_by=asserted_by,
            received_by=received_by,
            confidence_tier=confidence_tier,
            payload=MappingProxyType(dict(payload)),
        )
