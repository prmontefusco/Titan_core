"""Casos de uso para governanca de regras versionadas (ADR-0043)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain.rule_governance import (
    RuleIdentity,
    RuleSourceType,
    RuleTimelineEvent,
    RuleTimelineEventType,
)
from packages.shared_kernel import OrganizationId, UniversalReference


class RuleIdentityRepositoryPort(Protocol):
    def save(self, identity: RuleIdentity) -> None: ...

    def get_by_organization_and_code(
        self, organization_id: OrganizationId, code: str
    ) -> RuleIdentity | None: ...


class RuleTimelineRepositoryPort(Protocol):
    def append(self, event: RuleTimelineEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class RuleGovernanceService:
    """Coordena a identidade auditavel de uma regra e sua timeline inicial."""

    identities: RuleIdentityRepositoryPort
    timeline: RuleTimelineRepositoryPort

    def create_identity(
        self,
        organization_id: OrganizationId,
        code: str,
        purpose: str,
        scope: str,
        source_type: RuleSourceType,
        actor: UniversalReference,
        vertical: str = "",
        description: str = "",
        occurred_at: datetime | None = None,
    ) -> RuleIdentity:
        code_clean = code.strip().lower()
        existing = self.identities.get_by_organization_and_code(
            organization_id=organization_id,
            code=code_clean,
        )
        if existing is not None:
            raise ValueError(
                f"Ja existe uma identidade de regra com o codigo '{code_clean}' "
                "para esta Organization."
            )

        identity = RuleIdentity.create(
            organization_id=organization_id,
            code=code_clean,
            purpose=purpose,
            scope=scope,
            source_type=source_type,
            created_by=actor,
            vertical=vertical,
            description=description,
            created_at=occurred_at,
        )
        event = RuleTimelineEvent.record(
            organization_id=organization_id,
            rule_identity_id=identity.rule_identity_id,
            event_type=RuleTimelineEventType.RULE_IDENTITY_CREATED,
            actor=actor,
            occurred_at=occurred_at,
        )

        self.identities.save(identity)
        self.timeline.append(event)
        return identity
