"""Casos de uso e portas para Gestão de Políticas Versionadas (ADR-0038/Passo 6.1)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.core_domain.policy import Policy, PolicyStatus
from packages.shared_kernel import OrganizationId, TypedId


class PolicyRepositoryPort(Protocol):
    def save(self, policy: Policy) -> None: ...

    def get_by_id(self, policy_id: TypedId) -> Policy | None: ...

    def get_by_code_and_version(
        self, organization_id: OrganizationId, code: str, version: int
    ) -> Policy | None: ...

    def get_active_at(
        self, organization_id: OrganizationId, code: str, at_time: datetime
    ) -> Policy | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Policy]: ...


@dataclass(frozen=True, slots=True)
class PolicyService:
    repository: PolicyRepositoryPort

    def create_draft(
        self,
        organization_id: OrganizationId,
        code: str,
        name: str,
        description: str = "",
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> Policy:
        code_clean = code.strip().lower()
        existing = self.repository.get_by_code_and_version(
            organization_id=organization_id, code=code_clean, version=1
        )
        if existing is not None:
            raise ValueError(
                f"Já existe uma política com o código '{code_clean}' para esta organização."
            )

        draft = Policy.create_draft(
            organization_id=organization_id,
            code=code_clean,
            name=name,
            description=description,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        self.repository.save(draft)
        return draft

    def publish_policy(self, policy_id: TypedId, published_at: datetime | None = None) -> Policy:
        policy = self.repository.get_by_id(policy_id)
        if policy is None:
            raise KeyError(f"Política {policy_id.value} não encontrada.")

        # Procura se existe alguma versão PUBLICADA anterior para substituir
        now = published_at or datetime.now(UTC)
        if policy.version > 1:
            prev_published = self.repository.get_by_code_and_version(
                organization_id=policy.organization_id,
                code=policy.code,
                version=policy.version - 1,
            )
            if prev_published is not None and prev_published.status == PolicyStatus.PUBLISHED:
                superseded = prev_published.supersede()
                self.repository.save(superseded)

        published = policy.publish(published_at=now)
        self.repository.save(published)
        return published

    def create_next_version(
        self,
        policy_id: TypedId,
        name: str | None = None,
        description: str | None = None,
    ) -> Policy:
        current_policy = self.repository.get_by_id(policy_id)
        if current_policy is None:
            raise KeyError(f"Política {policy_id.value} não encontrada.")

        next_draft = current_policy.create_next_version(name=name, description=description)
        self.repository.save(next_draft)
        return next_draft

    def revoke_policy(self, policy_id: TypedId) -> Policy:
        policy = self.repository.get_by_id(policy_id)
        if policy is None:
            raise KeyError(f"Política {policy_id.value} não encontrada.")

        revoked = policy.revoke()
        self.repository.save(revoked)
        return revoked

    def get_active_policy_at(
        self, organization_id: OrganizationId, code: str, at_time: datetime
    ) -> Policy | None:
        return self.repository.get_active_at(
            organization_id=organization_id, code=code.strip().lower(), at_time=at_time
        )
