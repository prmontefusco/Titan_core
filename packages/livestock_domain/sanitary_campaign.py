"""Campanha sanitaria oficial do Titan Livestock (Passo 14.2)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


@dataclass(frozen=True, slots=True)
class SanitaryCampaign:
    campaign_id: TypedId
    organization_id: OrganizationId
    code: str
    name: str
    starts_at: datetime
    ends_at: datetime
    disease: str | None = None
    authority: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.starts_at, field_name="starts_at")
        require_utc(self.ends_at, field_name="ends_at")
        require_utc(self.created_at, field_name="created_at")
        if self.campaign_id.entity_type != "sanitary_campaign":
            raise ValueError(
                "campaign_id deve ter entity_type 'sanitary_campaign', recebido "
                f"'{self.campaign_id.entity_type}'."
            )
        if not self.code or not self.code.strip():
            raise ValueError("code nao pode ser vazio.")
        if not self.name or not self.name.strip():
            raise ValueError("name nao pode ser vazio.")
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at deve ser posterior a starts_at.")

    def covers(self, applied_at: datetime) -> bool:
        require_utc(applied_at, field_name="applied_at")
        return self.starts_at <= applied_at <= self.ends_at
