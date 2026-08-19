"""Casos de uso para governanca de regras versionadas (ADR-0043)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_application.policy_origin import resolve_policy_origin
from packages.core_domain.rule import Rule, RuleCondition, SeverityLevel
from packages.core_domain.rule_governance import (
    RuleAdoption,
    RuleAdoptionStatus,
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


class RuleAdoptionRepositoryPort(Protocol):
    def save(self, adoption: RuleAdoption) -> None: ...

    def update(self, adoption: RuleAdoption) -> None: ...

    def get_by_id(self, adoption_id: TypedId) -> RuleAdoption | None: ...

    def get_active_by_identity_and_scope(
        self,
        organization_id: OrganizationId,
        rule_identity_id: TypedId,
        purpose: str,
        scope: str,
    ) -> RuleAdoption | None: ...


class RuleVersionRepositoryPort(Protocol):
    def save(self, rule: Rule) -> None: ...

    def get_by_policy_code_and_version(
        self,
        organization_id: OrganizationId,
        policy_id: TypedId,
        code: str,
        version: int,
    ) -> Rule | None: ...

    def get_by_id(self, rule_id: TypedId) -> Rule | None: ...

    def list_by_policy(
        self,
        organization_id: OrganizationId,
        policy_id: TypedId,
    ) -> list[Rule]: ...


@dataclass(frozen=True, slots=True)
class RuleGovernanceService:
    """Coordena a identidade auditavel de uma regra e sua timeline inicial."""

    identities: RuleIdentityRepositoryPort
    timeline: RuleTimelineRepositoryPort
    rules: RuleVersionRepositoryPort | None = None
    adoptions: RuleAdoptionRepositoryPort | None = None

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

        # ADR-0064 Invariante 3 (BuyerPolicy): a origem de uma Policy e derivada das
        # RuleIdentity de suas Rules, nunca um campo proprio. O invariante protege
        # especificamente o reconhecimento como BuyerPolicy -- nao introduz
        # restricao nova para Policies puramente regulatorias/contratuais que
        # nunca pretenderam ser BuyerPolicy (ex.: LAW + REGULATION na mesma
        # Policy continua permitido, exatamente como antes desta ADR). O gate so
        # dispara quando INTERNAL_POLICY esta envolvido de algum dos lados -- ou
        # a Policy ja e (potencialmente) uma BuyerPolicy homogenea, ou a nova
        # Rule tentaria torna-la uma. Defesa em profundidade, junto da
        # verificacao repetida na avaliacao (packages/core_application/policy_origin.py).
        existing_rules = self.rules.list_by_policy(
            organization_id=organization_id, policy_id=policy_id
        )
        if existing_rules:
            existing_origin = resolve_policy_origin(
                organization_id, existing_rules, self.identities
            )
            buyer_policy_involved = (
                identity.source_type is RuleSourceType.INTERNAL_POLICY
                or existing_origin.source_type is RuleSourceType.INTERNAL_POLICY
            )
            homogeneous_with_new_rule = (
                existing_origin.homogeneous and existing_origin.source_type == identity.source_type
            )
            if buyer_policy_involved and not homogeneous_with_new_rule:
                raise ValueError(
                    f"A Policy {policy_id.value} ja possui Rules de origem diferente; "
                    "RuleSourceType deve permanecer homogeneo quando INTERNAL_POLICY "
                    "estiver envolvida nesta Policy (ADR-0064)."
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

    def adopt_rule_version(
        self,
        organization_id: OrganizationId,
        rule_identity_id: TypedId,
        rule_version_id: TypedId,
        purpose: str,
        scope: str,
        actor: UniversalReference,
        reason: str = "",
        occurred_at: datetime | None = None,
    ) -> RuleAdoption:
        if self.rules is None or self.adoptions is None:
            raise RuntimeError(
                "RuleGovernanceService exige repositorios de regras e adocoes para adotar regra."
            )

        identity = self.identities.get_by_id(rule_identity_id)
        if identity is None or identity.organization_id != organization_id:
            raise KeyError(f"Identidade de regra {rule_identity_id.value} nao encontrada.")

        rule = self.rules.get_by_id(rule_version_id)
        if rule is None or rule.organization_id != organization_id or rule.code != identity.code:
            raise KeyError(f"Versao de regra {rule_version_id.value} nao encontrada.")

        existing = self.adoptions.get_active_by_identity_and_scope(
            organization_id=organization_id,
            rule_identity_id=rule_identity_id,
            purpose=purpose,
            scope=scope,
        )
        if existing is not None:
            raise ValueError("Ja existe uma adocao ativa para esta regra, finalidade e escopo.")

        adoption = RuleAdoption.adopt(
            organization_id=organization_id,
            rule_identity_id=rule_identity_id,
            rule_version_id=rule_version_id,
            purpose=purpose,
            scope=scope,
            adopted_by=actor,
            reason=reason,
            adopted_at=occurred_at,
        )
        self.adoptions.save(adoption)
        self.timeline.append(
            RuleTimelineEvent.record(
                organization_id=organization_id,
                rule_identity_id=identity.rule_identity_id,
                event_type=RuleTimelineEventType.RULE_ADOPTED,
                actor=actor,
                rule_version_id=rule.rule_id,
                reason=reason,
                occurred_at=occurred_at,
            )
        )
        return adoption

    def replace_rule_adoption(
        self,
        organization_id: OrganizationId,
        rule_identity_id: TypedId,
        current_adoption_id: TypedId,
        new_rule_version_id: TypedId,
        actor: UniversalReference,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> RuleAdoption:
        if self.rules is None or self.adoptions is None:
            raise RuntimeError(
                "RuleGovernanceService exige repositorios de regras e adocoes "
                "para substituir adocao."
            )
        if not reason.strip():
            raise ValueError("Substituicao de adocao exige reason explicita.")

        identity = self.identities.get_by_id(rule_identity_id)
        if identity is None or identity.organization_id != organization_id:
            raise KeyError(f"Identidade de regra {rule_identity_id.value} nao encontrada.")

        active = self.adoptions.get_by_id(current_adoption_id)
        if active is None or active.organization_id != organization_id:
            raise KeyError(f"Adocao {current_adoption_id.value} nao encontrada.")
        if active.rule_identity_id != rule_identity_id:
            raise ValueError("A adocao informada nao pertence a identidade de regra indicada.")
        if active.status is not RuleAdoptionStatus.ACTIVE:
            raise ValueError("Somente adocao ativa pode ser substituida.")

        replacement_rule = self.rules.get_by_id(new_rule_version_id)
        if (
            replacement_rule is None
            or replacement_rule.organization_id != organization_id
            or replacement_rule.code != identity.code
        ):
            raise KeyError(f"Versao de regra {new_rule_version_id.value} nao encontrada.")
        if replacement_rule.rule_id == active.rule_version_id:
            raise ValueError("A nova versao precisa ser diferente da adocao ativa.")

        superseded = active.supersede(
            adopted_by=actor,
            reason=reason,
            adopted_at=occurred_at,
        )
        replacement = RuleAdoption.adopt(
            organization_id=organization_id,
            rule_identity_id=rule_identity_id,
            rule_version_id=new_rule_version_id,
            purpose=active.purpose,
            scope=active.scope,
            adopted_by=actor,
            reason=reason,
            adopted_at=occurred_at,
        )
        self.adoptions.update(superseded)
        self.adoptions.save(replacement)
        self.timeline.append(
            RuleTimelineEvent.record(
                organization_id=organization_id,
                rule_identity_id=identity.rule_identity_id,
                event_type=RuleTimelineEventType.RULE_ADOPTION_CHANGED,
                actor=actor,
                rule_version_id=replacement_rule.rule_id,
                reason=reason,
                occurred_at=occurred_at,
            )
        )
        return replacement
