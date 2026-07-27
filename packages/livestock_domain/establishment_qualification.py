"""Qualificacao auditavel de estabelecimento por mercado (continuidade ADR-0042/0041)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc


class EstablishmentQualificationStatus(StrEnum):
    HABILITADO = "HABILITADO"
    NAO_HABILITADO = "NAO_HABILITADO"


@dataclass(frozen=True, slots=True)
class EstablishmentQualification:
    qualification_id: TypedId
    organization_id: OrganizationId
    counterparty_id: TypedId
    market_purpose: str
    status: EstablishmentQualificationStatus
    source_name: str
    source_version: str | None = None
    assessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    evidence_references: tuple[UniversalReference, ...] = ()
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.assessed_at, field_name="assessed_at")
        require_utc(self.recorded_at, field_name="recorded_at")
        if self.qualification_id.entity_type != "establishment_qualification":
            raise ValueError("qualification_id deve ter entity_type 'establishment_qualification'.")
        if self.counterparty_id.entity_type != "external_counterparty":
            raise ValueError("counterparty_id deve ter entity_type 'external_counterparty'.")
        if not self.market_purpose.strip():
            raise ValueError("market_purpose nao pode ser vazio.")
        if not isinstance(self.status, EstablishmentQualificationStatus):
            raise TypeError("status deve ser EstablishmentQualificationStatus.")
        if not self.source_name.strip():
            raise ValueError("source_name nao pode ser vazio.")
        if self.source_version is not None and not self.source_version.strip():
            raise ValueError("source_version, quando informada, nao pode ser vazia.")
        for reference in self.evidence_references:
            if not isinstance(reference, UniversalReference):
                raise TypeError("evidence_references deve conter UniversalReference.")
            if reference.target_id.entity_type != "evidence":
                raise ValueError("evidence_references deve apontar para 'evidence'.")
            if reference.organization_id != self.organization_id:
                raise ValueError("A evidencia citada pertence a outra Organization.")

    @classmethod
    def create(
        cls,
        *,
        organization_id: OrganizationId,
        counterparty_id: TypedId,
        market_purpose: str,
        status: EstablishmentQualificationStatus,
        source_name: str,
        source_version: str | None,
        assessed_at: datetime,
        evidence_references: tuple[UniversalReference, ...] = (),
    ) -> "EstablishmentQualification":
        return cls(
            qualification_id=TypedId.new("establishment_qualification"),
            organization_id=organization_id,
            counterparty_id=counterparty_id,
            market_purpose=market_purpose.strip(),
            status=status,
            source_name=source_name.strip(),
            source_version=None if source_version is None else source_version.strip(),
            assessed_at=assessed_at,
            evidence_references=evidence_references,
        )
