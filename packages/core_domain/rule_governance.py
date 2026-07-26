"""Governanca imutavel de regras versionadas (ADR-0043)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class RuleSourceType(Enum):
    LAW = "lei"
    REGULATION = "regulamento"
    CONTRACT = "contrato"
    INTERNAL_POLICY = "politica_interna"
    CERTIFICATION = "certificacao"
    TITAN_TEMPLATE = "template_titan"
    OTHER = "outra"


class RuleTimelineEventType(Enum):
    RULE_IDENTITY_CREATED = "rule_identity_created"
    RULE_VERSION_DRAFTED = "rule_version_drafted"
    RULE_VERSION_SUBMITTED_FOR_REVIEW = "rule_version_submitted_for_review"
    RULE_VERSION_APPROVED = "rule_version_approved"
    RULE_VERSION_REJECTED = "rule_version_rejected"
    RULE_VERSION_PUBLISHED = "rule_version_published"
    RULE_VERSION_SUPERSEDED = "rule_version_superseded"
    RULE_VERSION_SUSPENDED = "rule_version_suspended"
    RULE_VERSION_REVOKED = "rule_version_revoked"
    RULE_ADOPTED = "rule_adopted"
    RULE_ADOPTION_CHANGED = "rule_adoption_changed"
    RULE_IMPACT_ASSESSMENT_REQUESTED = "rule_impact_assessment_requested"
    RULE_IMPACT_ASSESSMENT_COMPLETED = "rule_impact_assessment_completed"


class RuleImpactAssessmentResult(Enum):
    NO_IMPACT = "sem_impacto"
    POTENTIALLY_AFFECTED = "potencialmente_afetado"
    CONFIRMED_AFFECTED = "afetado_confirmado"
    INDETERMINATE = "indeterminado"
    HUMAN_REVIEW_REQUIRED = "revisao_humana_necessaria"


@dataclass(frozen=True, slots=True)
class RuleAdoption:
    """Adoção de uma versão de regra por uma Organization."""

    adoption_id: TypedId
    organization_id: OrganizationId
    rule_identity_id: TypedId
    rule_version_id: TypedId
    purpose: str
    scope: str
    adopted_by: UniversalReference
    adopted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""
    status: str = "active"

    def __post_init__(self) -> None:
        if self.adoption_id.entity_type != "rule_adoption":
            raise ValueError("adoption_id deve ser do tipo 'rule_adoption'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if self.rule_identity_id.entity_type != "rule_identity":
            raise ValueError("rule_identity_id deve ser do tipo 'rule_identity'.")
        if self.rule_version_id.entity_type != "rule":
            raise ValueError("rule_version_id deve ser do tipo 'rule'.")
        if not isinstance(self.adopted_by, UniversalReference):
            raise TypeError("adopted_by deve ser UniversalReference.")

        object.__setattr__(self, "purpose", _required_text(self.purpose, "purpose"))
        object.__setattr__(self, "scope", _required_text(self.scope, "scope"))
        object.__setattr__(self, "reason", self.reason.strip())
        object.__setattr__(self, "status", self.status.strip().lower())

        if self.status != "active":
            raise ValueError("status inicial de RuleAdoption deve ser 'active'.")

    @classmethod
    def adopt(
        cls,
        organization_id: OrganizationId,
        rule_identity_id: TypedId,
        rule_version_id: TypedId,
        purpose: str,
        scope: str,
        adopted_by: UniversalReference,
        reason: str = "",
        adopted_at: datetime | None = None,
    ) -> "RuleAdoption":
        return cls(
            adoption_id=TypedId.new("rule_adoption"),
            organization_id=organization_id,
            rule_identity_id=rule_identity_id,
            rule_version_id=rule_version_id,
            purpose=purpose,
            scope=scope,
            adopted_by=adopted_by,
            adopted_at=adopted_at or datetime.now(UTC),
            reason=reason,
        )


@dataclass(frozen=True, slots=True)
class RuleIdentity:
    """Identidade estavel de uma regra ao longo das suas versoes."""

    rule_identity_id: TypedId
    organization_id: OrganizationId
    code: str
    purpose: str
    scope: str
    source_type: RuleSourceType
    created_by: UniversalReference
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    vertical: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if self.rule_identity_id.entity_type != "rule_identity":
            raise ValueError("rule_identity_id deve ser do tipo 'rule_identity'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.created_by, UniversalReference):
            raise TypeError("created_by deve ser UniversalReference.")
        if not isinstance(self.source_type, RuleSourceType):
            raise TypeError("source_type deve ser RuleSourceType.")

        object.__setattr__(self, "code", self._required_text(self.code, "code").lower())
        object.__setattr__(self, "purpose", self._required_text(self.purpose, "purpose"))
        object.__setattr__(self, "scope", self._required_text(self.scope, "scope"))
        object.__setattr__(self, "vertical", self.vertical.strip().lower())
        object.__setattr__(self, "description", self.description.strip())

    @classmethod
    def create(
        cls,
        organization_id: OrganizationId,
        code: str,
        purpose: str,
        scope: str,
        source_type: RuleSourceType,
        created_by: UniversalReference,
        vertical: str = "",
        description: str = "",
        created_at: datetime | None = None,
    ) -> "RuleIdentity":
        return cls(
            rule_identity_id=TypedId.new("rule_identity"),
            organization_id=organization_id,
            code=code,
            purpose=purpose,
            scope=scope,
            source_type=source_type,
            created_by=created_by,
            created_at=created_at or datetime.now(UTC),
            vertical=vertical,
            description=description,
        )

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        return _required_text(value, field_name)


@dataclass(frozen=True, slots=True)
class RuleTimelineEvent:
    """Evento imutavel do ciclo de vida de uma regra."""

    event_id: TypedId
    organization_id: OrganizationId
    rule_identity_id: TypedId
    event_type: RuleTimelineEventType
    actor: UniversalReference
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    rule_version_id: TypedId | None = None
    reason: str = ""
    evidence_references: tuple[UniversalReference, ...] = field(default_factory=tuple)
    correlation_id: TypedId | None = None

    def __post_init__(self) -> None:
        if self.event_id.entity_type != "rule_timeline_event":
            raise ValueError("event_id deve ser do tipo 'rule_timeline_event'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if self.rule_identity_id.entity_type != "rule_identity":
            raise ValueError("rule_identity_id deve ser do tipo 'rule_identity'.")
        if self.rule_version_id is not None and self.rule_version_id.entity_type != "rule":
            raise ValueError("rule_version_id deve ser do tipo 'rule'.")
        if not isinstance(self.event_type, RuleTimelineEventType):
            raise TypeError("event_type deve ser RuleTimelineEventType.")
        if not isinstance(self.actor, UniversalReference):
            raise TypeError("actor deve ser UniversalReference.")
        if not isinstance(self.evidence_references, tuple):
            raise TypeError("evidence_references deve ser uma tupla.")
        if any(not isinstance(ref, UniversalReference) for ref in self.evidence_references):
            raise TypeError("evidence_references deve conter apenas UniversalReference.")

        object.__setattr__(self, "reason", self.reason.strip())

        if self.event_type in _EVENTS_REQUIRING_REASON and not self.reason:
            raise ValueError(f"{self.event_type.value} exige reason explicita.")
        if self.event_type in _VERSION_EVENTS and self.rule_version_id is None:
            raise ValueError(f"{self.event_type.value} exige rule_version_id.")

    @classmethod
    def record(
        cls,
        organization_id: OrganizationId,
        rule_identity_id: TypedId,
        event_type: RuleTimelineEventType,
        actor: UniversalReference,
        rule_version_id: TypedId | None = None,
        reason: str = "",
        evidence_references: tuple[UniversalReference, ...] = (),
        correlation_id: TypedId | None = None,
        occurred_at: datetime | None = None,
    ) -> "RuleTimelineEvent":
        return cls(
            event_id=TypedId.new("rule_timeline_event"),
            organization_id=organization_id,
            rule_identity_id=rule_identity_id,
            event_type=event_type,
            actor=actor,
            occurred_at=occurred_at or datetime.now(UTC),
            rule_version_id=rule_version_id,
            reason=reason,
            evidence_references=evidence_references,
            correlation_id=correlation_id,
        )


_VERSION_EVENTS = frozenset(
    {
        RuleTimelineEventType.RULE_VERSION_DRAFTED,
        RuleTimelineEventType.RULE_VERSION_SUBMITTED_FOR_REVIEW,
        RuleTimelineEventType.RULE_VERSION_APPROVED,
        RuleTimelineEventType.RULE_VERSION_REJECTED,
        RuleTimelineEventType.RULE_VERSION_PUBLISHED,
        RuleTimelineEventType.RULE_VERSION_SUPERSEDED,
        RuleTimelineEventType.RULE_VERSION_SUSPENDED,
        RuleTimelineEventType.RULE_VERSION_REVOKED,
    }
)

_EVENTS_REQUIRING_REASON = frozenset(
    {
        RuleTimelineEventType.RULE_VERSION_REJECTED,
        RuleTimelineEventType.RULE_VERSION_SUPERSEDED,
        RuleTimelineEventType.RULE_VERSION_SUSPENDED,
        RuleTimelineEventType.RULE_VERSION_REVOKED,
        RuleTimelineEventType.RULE_ADOPTION_CHANGED,
        RuleTimelineEventType.RULE_IMPACT_ASSESSMENT_REQUESTED,
        RuleTimelineEventType.RULE_IMPACT_ASSESSMENT_COMPLETED,
    }
)


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} deve ser uma string nao vazia.")
    return value.strip()
