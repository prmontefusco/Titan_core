"""Modelo de domínio imutável para Políticas de Conformidade Versionadas (ADR-0038/Passo 6.1)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from packages.shared_kernel import OrganizationId, TypedId


class PolicyStatus(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class Policy:
    policy_id: TypedId
    organization_id: OrganizationId
    code: str
    name: str
    description: str
    version: int = 1
    status: PolicyStatus = PolicyStatus.DRAFT
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ser do tipo 'policy'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("code de Policy deve ser uma string não vazia.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name de Policy deve ser uma string não vazia.")
        if not isinstance(self.description, str):
            raise TypeError("description de Policy deve ser uma string.")
        if not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version deve ser um número inteiro >= 1.")
        if not isinstance(self.status, PolicyStatus):
            raise TypeError("status deve ser um PolicyStatus válido.")
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_to < self.valid_from
        ):
            raise ValueError("valid_to não pode ser anterior a valid_from.")

    def publish(self, published_at: datetime | None = None) -> "Policy":
        if self.status != PolicyStatus.DRAFT:
            raise ValueError("Apenas políticas em RASCUNHO podem ser publicadas.")
        pub_time = published_at or datetime.now(UTC)
        return Policy(
            policy_id=self.policy_id,
            organization_id=self.organization_id,
            code=self.code,
            name=self.name,
            description=self.description,
            version=self.version,
            status=PolicyStatus.PUBLISHED,
            valid_from=self.valid_from or pub_time,
            valid_to=self.valid_to,
            created_at=self.created_at,
            published_at=pub_time,
        )

    def supersede(self) -> "Policy":
        if self.status != PolicyStatus.PUBLISHED:
            raise ValueError("Apenas políticas PUBLICADAS podem ser substituídas.")
        return Policy(
            policy_id=self.policy_id,
            organization_id=self.organization_id,
            code=self.code,
            name=self.name,
            description=self.description,
            version=self.version,
            status=PolicyStatus.SUPERSEDED,
            valid_from=self.valid_from,
            valid_to=self.valid_to,
            created_at=self.created_at,
            published_at=self.published_at,
        )

    def revoke(self) -> "Policy":
        if self.status == PolicyStatus.REVOKED:
            raise ValueError("Política já foi revogada anteriormente.")
        return Policy(
            policy_id=self.policy_id,
            organization_id=self.organization_id,
            code=self.code,
            name=self.name,
            description=self.description,
            version=self.version,
            status=PolicyStatus.REVOKED,
            valid_from=self.valid_from,
            valid_to=self.valid_to,
            created_at=self.created_at,
            published_at=self.published_at,
        )

    def create_next_version(
        self, name: str | None = None, description: str | None = None
    ) -> "Policy":
        if self.status not in (PolicyStatus.PUBLISHED, PolicyStatus.SUPERSEDED):
            raise ValueError("Apenas políticas publicadas ou substituídas podem gerar nova versão.")
        return Policy(
            policy_id=TypedId.new("policy"),
            organization_id=self.organization_id,
            code=self.code,
            name=name or self.name,
            description=description if description is not None else self.description,
            version=self.version + 1,
            status=PolicyStatus.DRAFT,
            valid_from=None,
            valid_to=None,
            created_at=datetime.now(UTC),
            published_at=None,
        )

    @classmethod
    def create_draft(
        cls,
        organization_id: OrganizationId,
        code: str,
        name: str,
        description: str = "",
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> "Policy":
        return cls(
            policy_id=TypedId.new("policy"),
            organization_id=organization_id,
            code=code.strip().lower(),
            name=name.strip(),
            description=description.strip(),
            version=1,
            status=PolicyStatus.DRAFT,
            valid_from=valid_from,
            valid_to=valid_to,
        )
