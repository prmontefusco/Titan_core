"""Repositorio PostgreSQL para campanhas sanitarias (Passo 14.2)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.sanitary_campaign_service import (
    SanitaryCampaignRepositoryPort,
)
from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

sanitary_campaigns_table = Table(
    "sanitary_campaigns",
    livestock_metadata,
    Column("campaign_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("code", String(120), nullable=False),
    Column("name", String(255), nullable=False),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("ends_at", DateTime(timezone=True), nullable=False),
    Column("disease", String(255), nullable=True),
    Column("authority", String(255), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "record_owner_organization_id",
        "code",
        name="uq_sanitary_campaigns_org_code",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_sanitary_campaigns_organization",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalSanitaryCampaignRepository(SanitaryCampaignRepositoryPort):
    connection: Connection

    def save(self, campaign: SanitaryCampaign) -> None:
        self.connection.execute(
            insert(sanitary_campaigns_table).values(
                campaign_id=campaign.campaign_id.value,
                record_owner_organization_id=campaign.organization_id.value,
                code=campaign.code,
                name=campaign.name,
                starts_at=campaign.starts_at,
                ends_at=campaign.ends_at,
                disease=campaign.disease,
                authority=campaign.authority,
                created_at=campaign.created_at,
            )
        )

    def get_by_id(self, campaign_id: TypedId) -> SanitaryCampaign | None:
        if campaign_id.entity_type != "sanitary_campaign":
            return None
        row = self.connection.execute(
            select(sanitary_campaigns_table).where(
                sanitary_campaigns_table.c.campaign_id == campaign_id.value
            )
        ).fetchone()
        return None if row is None else self._map(row)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> SanitaryCampaign | None:
        row = self.connection.execute(
            select(sanitary_campaigns_table).where(
                sanitary_campaigns_table.c.record_owner_organization_id == organization_id.value,
                sanitary_campaigns_table.c.code == code,
            )
        ).fetchone()
        return None if row is None else self._map(row)

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[SanitaryCampaign]:
        rows = self.connection.execute(
            select(sanitary_campaigns_table)
            .where(sanitary_campaigns_table.c.record_owner_organization_id == organization_id.value)
            .order_by(sanitary_campaigns_table.c.starts_at.desc())
            .limit(limit)
            .offset(offset)
        ).fetchall()
        return [self._map(row) for row in rows]

    def _map(self, row: Row[Any]) -> SanitaryCampaign:
        def aware(value: datetime) -> datetime:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value

        return SanitaryCampaign(
            campaign_id=TypedId(entity_type="sanitary_campaign", value=row.campaign_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            code=row.code,
            name=row.name,
            starts_at=aware(row.starts_at),
            ends_at=aware(row.ends_at),
            disease=row.disease,
            authority=row.authority,
            created_at=aware(row.created_at),
        )
