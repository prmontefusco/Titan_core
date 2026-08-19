"""Serviço de compartilhamento bilateral de BuyerPolicy contratual (ADR-0065)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from packages.core_infrastructure.persistence.authorization_grant import (
    AuthorizationGrant,
    AuthorizationGrantRepositoryPort,
)
from packages.core_infrastructure.persistence.policy import PolicyRepositoryPort
from packages.core_application.policy_origin import (
    is_buyer_policy_origin,
    resolve_policy_origin,
)
from packages.core_domain.policy import PolicyStatus
from packages.core_domain.rule_governance import RuleSourceType
from packages.core_infrastructure.persistence.rule import RuleVersionRepositoryPort
from packages.core_infrastructure.persistence.rule_governance import (
    RuleIdentityRepositoryPort,
)
from packages.shared_kernel import OrganizationId, TypedId


@dataclass(frozen=True, slots=True)
class PolicySharingService:
    """Orquestração de grants bilaterais para BuyerPolicy contratual."""

    policies: PolicyRepositoryPort
    rules: RuleVersionRepositoryPort
    identities: RuleIdentityRepositoryPort
    grants: AuthorizationGrantRepositoryPort

    def create_grant(
        self,
        owner_organization_id: OrganizationId,
        policy_id: TypedId,
        beneficiary_organization_id: OrganizationId,
        access_purpose: str,
        field_scope_profile: str,
        valid_until: datetime,
        created_by: str,
    ) -> AuthorizationGrant:
        """Cria grant bilateral para compartilhamento de Policy contratual.

        Precondições (não é responsabilidade deste service validar):
        - owner_organization_id é o OrganizationContext ativo
        - valid_until > now()
        - access_purpose e field_scope_profile são valores controlados

        Validações realizadas neste service:
        - Policy existe e pertence ao owner
        - Policy é homogeneamente CONTRACT
        - Policy está PUBLISHED
        """
        policy = self.policies.get_by_id(policy_id)
        if policy is None or policy.organization_id != owner_organization_id:
            raise KeyError(f"Policy {policy_id.value} não encontrada ou não pertence ao owner")

        if policy.status != PolicyStatus.PUBLISHED:
            raise ValueError(
                f"Policy {policy_id.value} não está PUBLISHED; status atual: {policy.status}"
            )

        # Verifica homogeneidade contratual
        rules = self.rules.list_by_policy(
            organization_id=owner_organization_id,
            policy_id=policy_id,
        )
        if not rules:
            raise ValueError(
                f"Policy {policy_id.value} não possui Rules publicadas; compartilhamento recusado"
            )

        origin = resolve_policy_origin(owner_organization_id, rules, self.identities)
        if not origin.homogeneous or origin.source_type != RuleSourceType.CONTRACT:
            raise ValueError(
                f"Policy {policy_id.value} não é homogeneamente CONTRACT; "
                "compartilhamento recusado (ADR-0065)"
            )

        # Cria grant
        grant_id = uuid4()
        now = datetime.now()
        grant = AuthorizationGrant(
            grant_id=grant_id,
            owner_organization_id=owner_organization_id,
            beneficiary_organization_id=beneficiary_organization_id,
            policy_id=policy_id,
            policy_version_id=TypedId("policy_version", policy.current_version_id.value),
            access_purpose=access_purpose,
            field_scope_profile=field_scope_profile,
            valid_from=now,
            valid_until=valid_until,
            status="ATIVO",
            created_at=now,
            created_by=created_by,
        )

        self.grants.save(grant)
        return grant

    def get_active_grant(
        self,
        policy_id: TypedId,
        beneficiary_organization_id: OrganizationId,
    ) -> AuthorizationGrant | None:
        """Obtém grant ativo para uma Policy e beneficiário específicos."""
        return self.grants.get_active_by_policy_and_beneficiary(
            policy_id=policy_id,
            beneficiary_organization_id=beneficiary_organization_id,
        )

    def revoke_grant(
        self,
        owner_organization_id: OrganizationId,
        grant_id: UUID,
        revocation_reason: str | None,
        revoked_by: str,
    ) -> None:
        """Revoga um grant.

        Precondição: revoked_by é o User ativo no contexto do owner.
        """
        grant = self.grants.get_by_id(grant_id)
        if grant is None:
            raise KeyError(f"Grant {grant_id} não encontrado")

        if grant.owner_organization_id != owner_organization_id:
            raise ValueError(
                f"Grant {grant_id} pertence a outro owner; revogação recusada"
            )

        if grant.status == "REVOGADO":
            raise ValueError(f"Grant {grant_id} já foi revogado")

        self.grants.update_status_to_revoked(
            grant_id=grant_id,
            revoked_by=revoked_by,
            revocation_reason=revocation_reason,
        )
