"""Persistencia PostgreSQL para DecisionAuthorityProfile (ADR-0053/T3 da ADR-0048)."""

import json
from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.decision_governance import DecisionAuthorityProfile
from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

decision_authority_profiles_table = Table(
    "decision_authority_profiles",
    organization_metadata,
    Column("authority_profile_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("principal_reference", JSONB, nullable=False),
    Column("role_name", String(255), nullable=False),
    Column("purpose", String(255), nullable=False),
    Column("emission_method", String(50), nullable=False),
    Column("approvals_required", Integer, nullable=False),
    Column("max_delegated_severity", String(50), nullable=False),
    Column("is_active", Boolean, nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=True),
    Column("valid_to", DateTime(timezone=True), nullable=True),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_decision_authority_profiles_organization",
    ),
    UniqueConstraint(
        "authority_profile_id",
        "record_owner_organization_id",
        name="uq_decision_authority_profiles_id_org",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TransactionalDecisionAuthorityProfileRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalDecisionAuthorityProfileRepository exige transacao ativa."
            )

    def save(self, profile: DecisionAuthorityProfile) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.decision_authority_profiles (
                    authority_profile_id,
                    record_owner_organization_id,
                    principal_reference,
                    role_name,
                    purpose,
                    emission_method,
                    approvals_required,
                    max_delegated_severity,
                    is_active,
                    valid_from,
                    valid_to
                ) VALUES (
                    :authority_profile_id,
                    :org_id,
                    :principal_reference,
                    :role_name,
                    :purpose,
                    :emission_method,
                    :approvals_required,
                    :max_delegated_severity,
                    :is_active,
                    :valid_from,
                    :valid_to
                )
                """
            ),
            {
                "authority_profile_id": profile.authority_id.value,
                "org_id": profile.organization_id.value,
                "principal_reference": json.dumps(reference_to_dict(profile.principal_reference)),
                "role_name": profile.role_name,
                "purpose": profile.purpose,
                "emission_method": profile.emission_method.value,
                "approvals_required": profile.approvals_required,
                "max_delegated_severity": profile.max_delegated_severity,
                "is_active": profile.is_active,
                "valid_from": profile.valid_from,
                "valid_to": profile.valid_to,
            },
        )

    def get_by_id(self, authority_id: TypedId) -> DecisionAuthorityProfile | None:
        row = self.connection.execute(
            text(
                """
                SELECT authority_profile_id,
                       record_owner_organization_id,
                       principal_reference,
                       role_name,
                       purpose,
                       emission_method,
                       approvals_required,
                       max_delegated_severity,
                       is_active,
                       valid_from,
                       valid_to
                  FROM core_audit.decision_authority_profiles
                 WHERE authority_profile_id = :authority_id
                """
            ),
            {"authority_id": authority_id.value},
        ).first()
        if row is None:
            return None
        valid_from = (
            row.valid_from.replace(tzinfo=UTC)
            if row.valid_from is not None and row.valid_from.tzinfo is None
            else row.valid_from
        )
        valid_to = (
            row.valid_to.replace(tzinfo=UTC)
            if row.valid_to is not None and row.valid_to.tzinfo is None
            else row.valid_to
        )
        principal_reference = reference_from_dict(row.principal_reference)
        if principal_reference is None:
            raise ValueError("principal_reference persistida da autoridade deve ser valida.")
        return DecisionAuthorityProfile(
            authority_id=TypedId(
                entity_type="authority_profile",
                value=row.authority_profile_id,
            ),
            organization_id=OrganizationId(row.record_owner_organization_id),
            principal_reference=principal_reference,
            role_name=row.role_name,
            purpose=row.purpose,
            emission_method=DecisionEmissionMethod(row.emission_method),
            approvals_required=row.approvals_required,
            max_delegated_severity=row.max_delegated_severity,
            is_active=row.is_active,
            valid_from=valid_from,
            valid_to=valid_to,
        )
