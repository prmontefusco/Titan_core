"""Casos de uso e portas para Gestão de Regras Versionadas (ADR-0038/Passo 6.2)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain.rule import Rule, RuleCondition, SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId


class RuleRepositoryPort(Protocol):
    def save(self, rule: Rule) -> None: ...

    def get_by_id(self, rule_id: TypedId) -> Rule | None: ...

    def get_by_policy_code_and_version(
        self,
        organization_id: OrganizationId,
        policy_id: TypedId,
        code: str,
        version: int,
    ) -> Rule | None: ...

    def list_active_rules_for_policy_at(
        self,
        organization_id: OrganizationId,
        policy_id: TypedId,
        at_time: datetime,
    ) -> list[Rule]: ...

    def list_by_policy(
        self,
        organization_id: OrganizationId,
        policy_id: TypedId,
    ) -> list[Rule]: ...


@dataclass(frozen=True, slots=True)
class RuleService:
    repository: RuleRepositoryPort

    def create_rule(
        self,
        policy_id: TypedId,
        organization_id: OrganizationId,
        code: str,
        name: str,
        description: str = "",
        severity: SeverityLevel = SeverityLevel.BLOCKING,
        normative_source: str = "",
        required_evidence_types: tuple[str, ...] = (),
        conditions: tuple[RuleCondition, ...] = (),
        justification: str = "",
        corrective_action: str = "",
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> Rule:
        code_clean = code.strip().lower()
        existing = self.repository.get_by_policy_code_and_version(
            organization_id=organization_id,
            policy_id=policy_id,
            code=code_clean,
            version=1,
        )
        if existing is not None:
            raise ValueError(f"Já existe uma regra com o código '{code_clean}' para esta política.")

        rule = Rule.create(
            policy_id=policy_id,
            organization_id=organization_id,
            code=code_clean,
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
        self.repository.save(rule)
        return rule

    def create_next_version(
        self,
        rule_id: TypedId,
        name: str | None = None,
        description: str | None = None,
        severity: SeverityLevel | None = None,
        required_evidence_types: tuple[str, ...] | None = None,
        conditions: tuple[RuleCondition, ...] | None = None,
    ) -> Rule:
        current_rule = self.repository.get_by_id(rule_id)
        if current_rule is None:
            raise KeyError(f"Regra {rule_id.value} não encontrada.")

        next_rule = current_rule.create_next_version(
            name=name,
            description=description,
            severity=severity,
            required_evidence_types=required_evidence_types,
            conditions=conditions,
        )
        self.repository.save(next_rule)
        return next_rule

    def list_active_rules_for_policy_at(
        self,
        organization_id: OrganizationId,
        policy_id: TypedId,
        at_time: datetime,
    ) -> list[Rule]:
        return self.repository.list_active_rules_for_policy_at(
            organization_id=organization_id, policy_id=policy_id, at_time=at_time
        )
