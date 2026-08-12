"""Contrato source-neutral e composição de coverage dimensional do NEXT-01."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from packages.livestock_domain.transfer_artifact import ReceivedTransferArtifact
from packages.shared_kernel import UniversalReference
from packages.shared_kernel.temporal import require_utc


class CoverageContributionValidation(StrEnum):
    VALIDATED = "VALIDATED"
    NOT_VALIDATED = "NOT_VALIDATED"


class CoverageContributionAdmissibility(StrEnum):
    ADMISSIBLE = "ADMISSIBLE"
    INSUFFICIENT = "INSUFFICIENT"


class DimensionalCoverageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    ABSENT = "ABSENT"
    INACCESSIBLE = "INACCESSIBLE"
    CONFLICTING = "CONFLICTING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class CoverageContribution:
    dimension: str
    covered_from: datetime
    covered_until: datetime
    validation: CoverageContributionValidation
    admissibility: CoverageContributionAdmissibility
    source_reference: UniversalReference | None = None
    accessible: bool = True
    conflicting: bool = False

    def __post_init__(self) -> None:
        require_utc(self.covered_from, field_name="covered_from")
        require_utc(self.covered_until, field_name="covered_until")
        if not self.dimension.strip():
            raise ValueError("dimension nao pode ser vazia.")
        if self.covered_from > self.covered_until:
            raise ValueError("covered_from nao pode ser posterior a covered_until.")


@dataclass(frozen=True, slots=True)
class DimensionalCoverageAssessment:
    dimension: str
    required_from: datetime
    required_until: datetime
    status: DimensionalCoverageStatus
    accepted_intervals: tuple[tuple[datetime, datetime], ...]
    source_references: tuple[UniversalReference, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DimensionalCoverageService:
    def assess(
        self,
        *,
        dimension: str,
        required_from: datetime,
        required_until: datetime,
        contributions: tuple[CoverageContribution, ...],
    ) -> DimensionalCoverageAssessment:
        require_utc(required_from, field_name="required_from")
        require_utc(required_until, field_name="required_until")
        if required_from > required_until:
            raise ValueError("required_from nao pode ser posterior a required_until.")

        matching = tuple(item for item in contributions if item.dimension == dimension)
        status, accepted, limitations = self._resolve(matching, required_from, required_until)
        references = tuple(
            dict.fromkeys(
                item.source_reference
                for item in matching
                if item.source_reference is not None
                and item.validation is CoverageContributionValidation.VALIDATED
                and item.admissibility is CoverageContributionAdmissibility.ADMISSIBLE
            )
        )
        return DimensionalCoverageAssessment(
            dimension=dimension,
            required_from=required_from,
            required_until=required_until,
            status=status,
            accepted_intervals=accepted,
            source_references=references,
            limitations=limitations,
        )

    @staticmethod
    def _resolve(
        contributions: tuple[CoverageContribution, ...],
        required_from: datetime,
        required_until: datetime,
    ) -> tuple[
        DimensionalCoverageStatus,
        tuple[tuple[datetime, datetime], ...],
        tuple[str, ...],
    ]:
        if not contributions:
            return DimensionalCoverageStatus.ABSENT, (), ("COVERAGE_CONTRIBUTION_ABSENT",)
        if any(item.conflicting for item in contributions):
            return DimensionalCoverageStatus.CONFLICTING, (), ("COVERAGE_CONFLICTING",)

        eligible = tuple(
            item
            for item in contributions
            if item.accessible
            and item.validation is CoverageContributionValidation.VALIDATED
            and item.admissibility is CoverageContributionAdmissibility.ADMISSIBLE
        )
        if not eligible:
            if all(not item.accessible for item in contributions):
                return DimensionalCoverageStatus.INACCESSIBLE, (), ("COVERAGE_INACCESSIBLE",)
            return DimensionalCoverageStatus.UNKNOWN, (), ("COVERAGE_NOT_ADMISSIBLE",)

        intervals = sorted(
            (
                (max(item.covered_from, required_from), min(item.covered_until, required_until))
                for item in eligible
                if item.covered_until >= required_from and item.covered_from <= required_until
            ),
            key=lambda interval: interval[0],
        )
        if not intervals:
            return DimensionalCoverageStatus.PARTIAL, (), ("COVERAGE_INTERVAL_GAP",)

        merged: list[tuple[datetime, datetime]] = []
        for start, end in intervals:
            if not merged or start > merged[-1][1]:
                merged.append((start, end))
            else:
                previous_start, previous_end = merged[-1]
                merged[-1] = (previous_start, max(previous_end, end))

        accepted = tuple(merged)
        if (
            len(accepted) == 1
            and accepted[0][0] <= required_from
            and accepted[0][1] >= required_until
        ):
            return DimensionalCoverageStatus.COMPLETE, accepted, ()
        return DimensionalCoverageStatus.PARTIAL, accepted, ("COVERAGE_INTERVAL_GAP",)


@dataclass(frozen=True, slots=True)
class ReceivedTransferCoverageDeclaration:
    dimension: str
    covered_from: datetime
    covered_until: datetime
    validation: CoverageContributionValidation
    admissibility: CoverageContributionAdmissibility


@dataclass(frozen=True, slots=True)
class ReceivedTransferArtifactCoverageAdapter:
    """Adapta declaração explícita; o artefato sozinho não gera coverage."""

    def adapt(
        self,
        artifact: ReceivedTransferArtifact,
        declarations: tuple[ReceivedTransferCoverageDeclaration, ...] = (),
    ) -> tuple[CoverageContribution, ...]:
        coverage = artifact.coverage
        contributions: list[CoverageContribution] = []
        for declaration in declarations:
            require_utc(declaration.covered_from, field_name="covered_from")
            require_utc(declaration.covered_until, field_name="covered_until")
            if coverage.known_from is None or coverage.known_until is None:
                raise ValueError("Artefato sem intervalo declarado nao sustenta contribuicao.")
            if (
                declaration.covered_from < coverage.known_from
                or declaration.covered_until > coverage.known_until
            ):
                raise ValueError("Contribuicao dimensional excede o intervalo do artefato.")
            contributions.append(
                CoverageContribution(
                    dimension=declaration.dimension,
                    covered_from=declaration.covered_from,
                    covered_until=declaration.covered_until,
                    validation=declaration.validation,
                    admissibility=declaration.admissibility,
                    source_reference=UniversalReference(
                        target_id=artifact.artifact_id,
                        organization_id=artifact.organization_id,
                        contract_version=1,
                    ),
                )
            )
        return tuple(contributions)
