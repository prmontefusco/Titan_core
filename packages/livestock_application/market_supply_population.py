"""Candidate population criteria, resolver and snapshot for Market Supply.

The resolver is intentionally in-memory. It receives candidate subjects already
available to the caller and never reads herd data, databases or other tenants.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime

from packages.shared_kernel import (
    CanonicalSerializer,
    OrganizationId,
    TypedId,
    canonicalize_for_hash,
)
from packages.shared_kernel.temporal import require_utc

_SERIALIZER = CanonicalSerializer()


@dataclass(frozen=True, slots=True)
class CandidatePopulationCriteria:
    organization_id: OrganizationId
    purpose: str
    policy_id: TypedId
    policy_version: int
    reference_time: datetime
    knowledge_cutoff: datetime
    commercial_window_start: datetime | None = None
    commercial_window_end: datetime | None = None
    subject_type: str = "animal"
    required_tags: tuple[str, ...] = ()
    excluded_subject_ids: tuple[TypedId, ...] = ()

    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise ValueError("purpose deve ser texto nao vazio.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ter entity_type 'policy'.")
        if self.policy_version < 1:
            raise ValueError("policy_version deve ser inteiro >= 1.")
        if not self.subject_type.strip():
            raise ValueError("subject_type deve ser texto nao vazio.")
        require_utc(self.reference_time, field_name="reference_time")
        require_utc(self.knowledge_cutoff, field_name="knowledge_cutoff")
        if self.commercial_window_start is not None:
            require_utc(self.commercial_window_start, field_name="commercial_window_start")
        if self.commercial_window_end is not None:
            require_utc(self.commercial_window_end, field_name="commercial_window_end")
        if (
            self.commercial_window_start is not None
            and self.commercial_window_end is not None
            and self.commercial_window_start >= self.commercial_window_end
        ):
            raise ValueError("commercial_window_start deve preceder commercial_window_end.")
        for subject_id in self.excluded_subject_ids:
            if subject_id.entity_type != self.subject_type:
                raise ValueError("excluded_subject_ids devem ter o subject_type informado.")

    def digest(self) -> str:
        return _hash(
            {
                "schema": "titan.market_supply.candidate_population_criteria",
                "version": 1,
                "organization_id": str(self.organization_id.value),
                "purpose": self.purpose,
                "policy_id": str(self.policy_id.value),
                "policy_version": self.policy_version,
                "reference_time": self.reference_time,
                "knowledge_cutoff": self.knowledge_cutoff,
                "commercial_window_start": self.commercial_window_start,
                "commercial_window_end": self.commercial_window_end,
                "subject_type": self.subject_type,
                "required_tags": sorted(self.required_tags),
                "excluded_subject_ids": sorted(
                    str(item.value) for item in self.excluded_subject_ids
                ),
            },
        )

    def policy_context_digest(self) -> str:
        """Stable semantic context used to relate aggregate disclosure queries.

        This intentionally excludes per-query filters, explicit subject
        exclusions, resolved_at and population membership. Those details remain
        in criteria/snapshot/population digests, while this digest groups queries
        that share the same authority, purpose and temporal coordinates for
        differencing and repeated-query assessment.
        """

        return _hash(
            {
                "schema": "titan.market_supply.policy_context",
                "version": 1,
                "organization_id": str(self.organization_id.value),
                "purpose": self.purpose,
                "policy_id": str(self.policy_id.value),
                "policy_version": self.policy_version,
                "reference_time": self.reference_time,
                "knowledge_cutoff": self.knowledge_cutoff,
                "commercial_window_start": self.commercial_window_start,
                "commercial_window_end": self.commercial_window_end,
                "subject_type": self.subject_type,
            },
        )


@dataclass(frozen=True, slots=True)
class CandidatePopulationSubject:
    subject_id: TypedId
    organization_id: OrganizationId
    property_id: TypedId | None = None
    tags: tuple[str, ...] = ()
    accessible: bool = True
    known_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.property_id is not None and self.property_id.entity_type != "property":
            raise ValueError("property_id deve ter entity_type 'property'.")
        if self.known_at is not None:
            require_utc(self.known_at, field_name="known_at")


@dataclass(frozen=True, slots=True)
class CandidatePopulationExclusion:
    reason: str
    count: int

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("reason deve ser texto nao vazio.")
        if self.count < 1:
            raise ValueError("count deve ser inteiro >= 1.")


@dataclass(frozen=True, slots=True)
class CandidatePopulationInternalUniverseSummary:
    authorized_sources_digest: str
    selection_criteria_digest: str
    population_digest: str
    population_size: int
    organization_count: int
    property_count: int | None
    subject_count: int

    def __post_init__(self) -> None:
        for field_name in (
            "authorized_sources_digest",
            "selection_criteria_digest",
            "population_digest",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} deve ser texto nao vazio.")
        for field_name in ("population_size", "organization_count", "subject_count"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} nao pode ser negativo.")
        if self.property_count is not None and self.property_count < 0:
            raise ValueError("property_count nao pode ser negativo.")


@dataclass(frozen=True, slots=True)
class CandidatePopulationSnapshot:
    criteria: CandidatePopulationCriteria
    resolved_at: datetime
    included_subject_ids: tuple[TypedId, ...]
    included_organization_ids: tuple[OrganizationId, ...]
    included_property_ids: tuple[TypedId, ...] | None
    excluded_summary: tuple[CandidatePopulationExclusion, ...]
    criteria_digest: str
    snapshot_digest: str

    def __post_init__(self) -> None:
        require_utc(self.resolved_at, field_name="resolved_at")
        expected_criteria_digest = self.criteria.digest()
        if self.criteria_digest != expected_criteria_digest:
            raise ValueError("criteria_digest nao corresponde aos criterios.")
        expected_snapshot_digest = _snapshot_digest(
            criteria=self.criteria,
            resolved_at=self.resolved_at,
            included_subject_ids=self.included_subject_ids,
            included_organization_ids=self.included_organization_ids,
            included_property_ids=self.included_property_ids,
            excluded_summary=self.excluded_summary,
            criteria_digest=self.criteria_digest,
        )
        if self.snapshot_digest != expected_snapshot_digest:
            raise ValueError("snapshot_digest nao corresponde ao snapshot.")

    @property
    def included_count(self) -> int:
        return len(self.included_subject_ids)

    @property
    def excluded_count(self) -> int:
        return sum(item.count for item in self.excluded_summary)

    def public_summary(self) -> dict[str, object]:
        return {
            "criteria_digest": self.criteria_digest,
            "snapshot_digest": self.snapshot_digest,
            "resolved_at": self.resolved_at.isoformat(),
            "included_count": self.included_count,
            "excluded_count": self.excluded_count,
            "excluded_summary": [
                {"reason": item.reason, "count": item.count} for item in self.excluded_summary
            ],
        }

    def internal_universe_summary(self) -> CandidatePopulationInternalUniverseSummary:
        return CandidatePopulationInternalUniverseSummary(
            authorized_sources_digest=_authorized_sources_digest(self.criteria),
            selection_criteria_digest=self.criteria_digest,
            population_digest=_population_digest(self.included_subject_ids),
            population_size=self.included_count + self.excluded_count,
            organization_count=len(frozenset(self.included_organization_ids)),
            property_count=(
                None
                if self.included_property_ids is None
                else len(frozenset(self.included_property_ids))
            ),
            subject_count=self.included_count,
        )


class CandidatePopulationResolver:
    """Resolves a deterministic snapshot from caller-supplied candidate subjects."""

    def resolve(
        self,
        *,
        criteria: CandidatePopulationCriteria,
        subjects: tuple[CandidatePopulationSubject, ...],
        resolved_at: datetime,
    ) -> CandidatePopulationSnapshot:
        require_utc(resolved_at, field_name="resolved_at")
        included: list[TypedId] = []
        included_organizations: list[OrganizationId] = []
        included_properties: list[TypedId] = []
        property_count_known = True
        exclusions: dict[str, int] = {}
        excluded_ids = frozenset(criteria.excluded_subject_ids)
        required_tags = frozenset(criteria.required_tags)

        for subject in subjects:
            reason = _exclusion_reason(criteria, subject, excluded_ids, required_tags)
            if reason is None:
                included.append(subject.subject_id)
                included_organizations.append(subject.organization_id)
                if subject.property_id is None:
                    property_count_known = False
                else:
                    included_properties.append(subject.property_id)
            else:
                exclusions[reason] = exclusions.get(reason, 0) + 1

        included_ids = tuple(sorted(included, key=lambda item: str(item.value)))
        included_organization_ids = tuple(
            sorted(frozenset(included_organizations), key=lambda item: str(item.value))
        )
        included_property_ids = (
            None
            if not property_count_known
            else tuple(sorted(frozenset(included_properties), key=lambda item: str(item.value)))
        )
        excluded_summary = tuple(
            CandidatePopulationExclusion(reason=reason, count=count)
            for reason, count in sorted(exclusions.items())
        )
        criteria_digest = criteria.digest()
        snapshot_digest = _snapshot_digest(
            criteria=criteria,
            resolved_at=resolved_at,
            included_subject_ids=included_ids,
            included_organization_ids=included_organization_ids,
            included_property_ids=included_property_ids,
            excluded_summary=excluded_summary,
            criteria_digest=criteria_digest,
        )
        return CandidatePopulationSnapshot(
            criteria=criteria,
            resolved_at=resolved_at,
            included_subject_ids=included_ids,
            included_organization_ids=included_organization_ids,
            included_property_ids=included_property_ids,
            excluded_summary=excluded_summary,
            criteria_digest=criteria_digest,
            snapshot_digest=snapshot_digest,
        )


def _exclusion_reason(
    criteria: CandidatePopulationCriteria,
    subject: CandidatePopulationSubject,
    excluded_ids: frozenset[TypedId],
    required_tags: frozenset[str],
) -> str | None:
    if subject.subject_id.entity_type != criteria.subject_type:
        return "SUBJECT_TYPE_MISMATCH"
    if subject.organization_id != criteria.organization_id:
        return "ORGANIZATION_MISMATCH"
    if subject.subject_id in excluded_ids:
        return "EXPLICITLY_EXCLUDED"
    if not subject.accessible:
        return "NOT_AUTHORIZED_OR_INACCESSIBLE"
    if subject.known_at is not None and subject.known_at > criteria.knowledge_cutoff:
        return "NOT_KNOWN_AT_CUTOFF"
    if not required_tags.issubset(frozenset(subject.tags)):
        return "REQUIRED_TAG_MISSING"
    return None


def _snapshot_digest(
    *,
    criteria: CandidatePopulationCriteria,
    resolved_at: datetime,
    included_subject_ids: tuple[TypedId, ...],
    included_organization_ids: tuple[OrganizationId, ...],
    included_property_ids: tuple[TypedId, ...] | None,
    excluded_summary: tuple[CandidatePopulationExclusion, ...],
    criteria_digest: str,
) -> str:
    return _hash(
        {
            "schema": "titan.market_supply.candidate_population_snapshot",
            "version": 1,
            "organization_id": str(criteria.organization_id.value),
            "criteria_digest": criteria_digest,
            "resolved_at": resolved_at,
            "included_subject_ids": [str(item.value) for item in included_subject_ids],
            "included_organization_ids": [str(item.value) for item in included_organization_ids],
            "included_property_ids": (
                None
                if included_property_ids is None
                else [str(item.value) for item in included_property_ids]
            ),
            "excluded_summary": [
                {"reason": item.reason, "count": item.count} for item in excluded_summary
            ],
        },
    )


def _authorized_sources_digest(criteria: CandidatePopulationCriteria) -> str:
    return _hash(
        {
            "schema": "titan.market_supply.authorized_sources",
            "version": 1,
            "organization_id": str(criteria.organization_id.value),
            "purpose": criteria.purpose,
            "policy_id": str(criteria.policy_id.value),
            "policy_version": criteria.policy_version,
            "reference_time": criteria.reference_time,
            "knowledge_cutoff": criteria.knowledge_cutoff,
        },
    )


def _population_digest(included_subject_ids: tuple[TypedId, ...]) -> str:
    return _hash(
        {
            "schema": "titan.market_supply.population",
            "version": 1,
            "included_subject_ids": [str(item.value) for item in included_subject_ids],
        },
    )


def _hash(value: dict[str, object]) -> str:
    return hashlib.sha256(_SERIALIZER.serialize(canonicalize_for_hash(value))).hexdigest()
