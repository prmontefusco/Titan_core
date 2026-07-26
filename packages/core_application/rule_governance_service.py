"""Casos de uso para governanca de regras versionadas (ADR-0043)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain.rule import Rule, RuleCondition, SeverityLevel
from packages.core_domain.rule_governance import (
    RuleIdentity,
    RuleSourceType,
    RuleTimelineEvent,
    RuleTimelineEventType,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class RuleIdentityRepositoryPort(Protocol):
    def save(self, identity: RuleIdentity) -> None: ...

    def get_by_id(self, rule_identity_id: TypedId) -> RuleIdentity | None: ...

    def get_by_organization_and_code(
        self, organization_id: OrganizationId, code: str
    ) -> RuleIdentity | None: ...


class RuleTimelineRepositoryPort(Protocol):
    def append(self, event: RuleTimelineEvent) -> None: ...


class RuleVersionRepositoryPort(Protocol):
    def save(self, rule: Rule) -> None: ...

    def get_by_policy_code_and_version(
        self,
        organization_id: OrganizationId,
        policy_id: TypedId,
        code: str,
        version: int,
    ) -> Rule | None: ...


@dataclass(frozen=True, slots=True)
class RuleGovernanceService:
    """Coordena a identidade auditavel de uma regra e sua timeline inicial."""

    identities: RuleIdentityRepositoryPort
    timeline: RuleTimelineRepositoryPort
    rules: RuleVersionRepositoryPort | None = None

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

    def publish_rule_version(
        self,
        organization_id: OrganizationId,
        rule_identity_id: TypedId,
        policy_id: TypedId,
        name: str,
        actor: UniversalReference,
        description: str = "",
        severity: SeverityLevel = SeverityLevel.BLOCKING,
        normative_source: str = "",
        required_evidence_types: tuple[str, ...] = (),
        conditions: tuple[RuleCondition, ...] = (),
        justification: str = "",
        corrective_action: str = "",
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        occurred_at: datetime | None = None,
    ) -> Rule:
        if self.rules is None:
            raise RuntimeError(
                "RuleGovernanceService exige repositorio de regras para publicar versao."
            )

        identity = self.identities.get_by_id(rule_identity_id)
        if identity is None or identity.organization_id != organization_id:
            raise KeyError(f"Identidade de regra {rule_identity_id.value} nao encontrada.")

        existing_v1 = self.rules.get_by_policy_code_and_version(
            organization_id=organization_id,
            policy_id=policy_id,
            code=identity.code,
            version=1,
        )
        if existing_v1 is not None:
            raise ValueError(
                f"Ja existe uma versao publicada para a regra '{identity.code}' nesta Policy."
            )

        rule = Rule.create(
            policy_id=policy_id,
            organization_id=organization_id,
            code=identity.code,
            name=name,
            description=description,
            severity=severity,
            normative_source=normative_source,
            required_evidence_types=required_evidence_types,
            conditions=conditions,
            justification=justification,
            corrective_action=corrective_action,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        self.rules.save(rule)
        self.timeline.append(
            RuleTimelineEvent.record(
                organization_id=organization_id,
                rule_identity_id=identity.rule_identity_id,
                event_type=RuleTimelineEventType.RULE_VERSION_DRAFTED,
                actor=actor,
                rule_version_id=rule.rule_id,
                occurred_at=occurred_at,
            )
        )
        self.timeline.append(
            RuleTimelineEvent.record(
                organization_id=organization_id,
                rule_identity_id=identity.rule_identity_id,
                event_type=RuleTimelineEventType.RULE_VERSION_PUBLISHED,
                actor=actor,
                rule_version_id=rule.rule_id,
                occurred_at=occurred_at,
            )
        )
        return rule
