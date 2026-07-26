"""Artefato recebido em transferencia de custodia (ADR-0042)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class TransferArtifactGapCode(StrEnum):
    COVERAGE_BEFORE_TRANSFER = "COVERAGE_BEFORE_TRANSFER"
    HISTORY_BEFORE_ACQUISITION_UNKNOWN = "HISTORY_BEFORE_ACQUISITION_UNKNOWN"


@dataclass(frozen=True, slots=True)
class TransferArtifactGap:
    code: TransferArtifactGapCode
    starts_at: datetime | None
    ends_at: datetime | None
    description: str

    def __post_init__(self) -> None:
        if self.starts_at is not None:
            require_utc(self.starts_at, field_name="starts_at")
        if self.ends_at is not None:
            require_utc(self.ends_at, field_name="ends_at")
        if not self.description.strip():
            raise ValueError("description nao pode ser vazio.")


@dataclass(frozen=True, slots=True)
class HistoryCoverage:
    known_from: datetime | None
    known_until: datetime | None
    gaps: tuple[TransferArtifactGap, ...] = ()

    def __post_init__(self) -> None:
        if self.known_from is not None:
            require_utc(self.known_from, field_name="known_from")
        if self.known_until is not None:
            require_utc(self.known_until, field_name="known_until")
        if (
            self.known_from is not None
            and self.known_until is not None
            and self.known_from > self.known_until
        ):
            raise ValueError("known_from nao pode ser posterior a known_until.")

    @classmethod
    def from_transfer(
        cls,
        *,
        known_from: datetime | None,
        known_until: datetime | None,
        transfer_effective_at: datetime,
    ) -> "HistoryCoverage":
        require_utc(transfer_effective_at, field_name="transfer_effective_at")
        gaps: list[TransferArtifactGap] = []
        if known_until is None:
            gaps.append(
                TransferArtifactGap(
                    code=TransferArtifactGapCode.HISTORY_BEFORE_ACQUISITION_UNKNOWN,
                    starts_at=None,
                    ends_at=transfer_effective_at,
                    description="Historico anterior a aquisicao nao foi recebido.",
                )
            )
        elif known_until < transfer_effective_at:
            gaps.append(
                TransferArtifactGap(
                    code=TransferArtifactGapCode.COVERAGE_BEFORE_TRANSFER,
                    starts_at=known_until,
                    ends_at=transfer_effective_at,
                    description="A cobertura recebida termina antes da transferencia efetiva.",
                )
            )
        return cls(known_from=known_from, known_until=known_until, gaps=tuple(gaps))


@dataclass(frozen=True, slots=True)
class ReceivedTransferArtifact:
    artifact_id: TypedId
    organization_id: OrganizationId
    animal_id: TypedId
    source_counterparty_id: TypedId
    bundle_digest: str
    bundle_issued_at: datetime
    transfer_effective_at: datetime
    coverage: HistoryCoverage
    issuer_name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.bundle_issued_at, field_name="bundle_issued_at")
        require_utc(self.transfer_effective_at, field_name="transfer_effective_at")
        require_utc(self.created_at, field_name="created_at")
        if self.artifact_id.entity_type != "received_transfer_artifact":
            raise ValueError("artifact_id deve ter entity_type 'received_transfer_artifact'.")
        if self.animal_id.entity_type != "animal":
            raise ValueError("animal_id deve ter entity_type 'animal'.")
        if self.source_counterparty_id.entity_type != "external_counterparty":
            raise ValueError("source_counterparty_id deve ter entity_type 'external_counterparty'.")
        if not self.bundle_digest.strip():
            raise ValueError("bundle_digest nao pode ser vazio.")
        if self.issuer_name is not None and not self.issuer_name.strip():
            raise ValueError("issuer_name, quando informado, nao pode ser vazio.")
