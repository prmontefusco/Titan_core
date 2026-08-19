"""Persistência de grants bilaterais para compartilhamento de BuyerPolicy (ADR-0065)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import Connection, text

from packages.shared_kernel import OrganizationId, TypedId


@dataclass(frozen=True, slots=True)
class AuthorizationGrant:
    """Grant bilateral entre Organization owner (comprador) e beneficiary (fornecedor)."""

    grant_id: UUID
    owner_organization_id: OrganizationId
    beneficiary_organization_id: OrganizationId
    policy_id: TypedId
    policy_version_id: TypedId
    access_purpose: str  # ex: AUTOAVALIACAO_CONTRATUAL_FORNECEDOR
    field_scope_profile: str  # ex: CONTRATO_MINIMO
    valid_from: datetime
    valid_until: datetime
    status: str  # ATIVO, REVOGADO, EXPIRADO
    created_at: datetime
    created_by: str
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    revocation_reason: str | None = None


class AuthorizationGrantRepositoryPort(Protocol):
    """Interface para persistência de AuthorizationGrant."""

    def save(self, grant: AuthorizationGrant) -> None:
        """Persiste um novo grant."""
        ...

    def get_by_id(self, grant_id: UUID) -> AuthorizationGrant | None:
        """Obtém grant por ID."""
        ...

    def get_active_by_policy_and_beneficiary(
        self,
        policy_id: TypedId,
        beneficiary_organization_id: OrganizationId,
    ) -> AuthorizationGrant | None:
        """Obtém grant ativo para uma Policy e beneficiário específicos."""
        ...

    def list_by_owner(
        self,
        owner_organization_id: OrganizationId,
    ) -> list[AuthorizationGrant]:
        """Lista todos os grants emitidos por um owner."""
        ...

    def list_by_beneficiary(
        self,
        beneficiary_organization_id: OrganizationId,
    ) -> list[AuthorizationGrant]:
        """Lista todos os grants recebidos por um beneficiário."""
        ...

    def update_status_to_revoked(
        self,
        grant_id: UUID,
        revoked_by: str,
        revocation_reason: str | None = None,
    ) -> None:
        """Marca grant como REVOGADO."""
        ...


@dataclass(frozen=True, slots=True)
class TransactionalAuthorizationGrantRepository:
    """Implementação transacional do repositório de grants."""

    connection: Connection

    def save(self, grant: AuthorizationGrant) -> None:
        """Persiste um novo grant."""
        self.connection.execute(
            text(
                """
                INSERT INTO core_identity.authorization_grants (
                    grant_id,
                    owner_organization_id,
                    beneficiary_organization_id,
                    policy_id,
                    policy_version_id,
                    access_purpose,
                    field_scope_profile,
                    valid_from,
                    valid_until,
                    status,
                    created_at,
                    created_by,
                    record_owner_organization_id
                ) VALUES (
                    :grant_id,
                    :owner_org_id,
                    :beneficiary_org_id,
                    :policy_id,
                    :policy_version_id,
                    :access_purpose,
                    :field_scope_profile,
                    :valid_from,
                    :valid_until,
                    :status,
                    :created_at,
                    :created_by,
                    :owner_org_id
                )
                """
            ),
            {
                "grant_id": grant.grant_id,
                "owner_org_id": str(grant.owner_organization_id.value),
                "beneficiary_org_id": str(grant.beneficiary_organization_id.value),
                "policy_id": str(grant.policy_id.value),
                "policy_version_id": str(grant.policy_version_id.value),
                "access_purpose": grant.access_purpose,
                "field_scope_profile": grant.field_scope_profile,
                "valid_from": grant.valid_from,
                "valid_until": grant.valid_until,
                "status": grant.status,
                "created_at": grant.created_at,
                "created_by": grant.created_by,
            },
        )

    def get_by_id(self, grant_id: UUID) -> AuthorizationGrant | None:
        """Obtém grant por ID."""
        row = self.connection.execute(
            text(
                """
                SELECT
                    grant_id,
                    owner_organization_id,
                    beneficiary_organization_id,
                    policy_id,
                    policy_version_id,
                    access_purpose,
                    field_scope_profile,
                    valid_from,
                    valid_until,
                    status,
                    created_at,
                    created_by,
                    revoked_at,
                    revoked_by,
                    revocation_reason
                FROM core_identity.authorization_grants
                WHERE grant_id = :grant_id
                """
            ),
            {"grant_id": grant_id},
        ).fetchone()

        if not row:
            return None

        return AuthorizationGrant(
            grant_id=row[0],
            owner_organization_id=OrganizationId(row[1]),
            beneficiary_organization_id=OrganizationId(row[2]),
            policy_id=TypedId("policy", row[3]),
            policy_version_id=TypedId("policy_version", row[4]),
            access_purpose=row[5],
            field_scope_profile=row[6],
            valid_from=row[7],
            valid_until=row[8],
            status=row[9],
            created_at=row[10],
            created_by=row[11],
            revoked_at=row[12],
            revoked_by=row[13],
            revocation_reason=row[14],
        )

    def get_active_by_policy_and_beneficiary(
        self,
        policy_id: TypedId,
        beneficiary_organization_id: OrganizationId,
    ) -> AuthorizationGrant | None:
        """Obtém grant ativo para uma Policy e beneficiário específicos."""
        row = self.connection.execute(
            text(
                """
                SELECT
                    grant_id,
                    owner_organization_id,
                    beneficiary_organization_id,
                    policy_id,
                    policy_version_id,
                    access_purpose,
                    field_scope_profile,
                    valid_from,
                    valid_until,
                    status,
                    created_at,
                    created_by,
                    revoked_at,
                    revoked_by,
                    revocation_reason
                FROM core_identity.authorization_grants
                WHERE
                    policy_id = :policy_id
                    AND beneficiary_organization_id = :beneficiary_org_id
                    AND status = 'ATIVO'
                    AND valid_until > CURRENT_TIMESTAMP
                LIMIT 1
                """
            ),
            {
                "policy_id": str(policy_id.value),
                "beneficiary_org_id": str(beneficiary_organization_id.value),
            },
        ).fetchone()

        if not row:
            return None

        return AuthorizationGrant(
            grant_id=row[0],
            owner_organization_id=OrganizationId(row[1]),
            beneficiary_organization_id=OrganizationId(row[2]),
            policy_id=TypedId("policy", row[3]),
            policy_version_id=TypedId("policy_version", row[4]),
            access_purpose=row[5],
            field_scope_profile=row[6],
            valid_from=row[7],
            valid_until=row[8],
            status=row[9],
            created_at=row[10],
            created_by=row[11],
            revoked_at=row[12],
            revoked_by=row[13],
            revocation_reason=row[14],
        )

    def list_by_owner(
        self,
        owner_organization_id: OrganizationId,
    ) -> list[AuthorizationGrant]:
        """Lista todos os grants emitidos por um owner."""
        rows = self.connection.execute(
            text(
                """
                SELECT
                    grant_id,
                    owner_organization_id,
                    beneficiary_organization_id,
                    policy_id,
                    policy_version_id,
                    access_purpose,
                    field_scope_profile,
                    valid_from,
                    valid_until,
                    status,
                    created_at,
                    created_by,
                    revoked_at,
                    revoked_by,
                    revocation_reason
                FROM core_identity.authorization_grants
                WHERE owner_organization_id = :owner_org_id
                ORDER BY created_at DESC
                """
            ),
            {"owner_org_id": str(owner_organization_id.value)},
        ).fetchall()

        return [
            AuthorizationGrant(
                grant_id=row[0],
                owner_organization_id=OrganizationId(row[1]),
                beneficiary_organization_id=OrganizationId(row[2]),
                policy_id=TypedId("policy", row[3]),
                policy_version_id=TypedId("policy_version", row[4]),
                access_purpose=row[5],
                field_scope_profile=row[6],
                valid_from=row[7],
                valid_until=row[8],
                status=row[9],
                created_at=row[10],
                created_by=row[11],
                revoked_at=row[12],
                revoked_by=row[13],
                revocation_reason=row[14],
            )
            for row in rows
        ]

    def list_by_beneficiary(
        self,
        beneficiary_organization_id: OrganizationId,
    ) -> list[AuthorizationGrant]:
        """Lista todos os grants recebidos por um beneficiário."""
        rows = self.connection.execute(
            text(
                """
                SELECT
                    grant_id,
                    owner_organization_id,
                    beneficiary_organization_id,
                    policy_id,
                    policy_version_id,
                    access_purpose,
                    field_scope_profile,
                    valid_from,
                    valid_until,
                    status,
                    created_at,
                    created_by,
                    revoked_at,
                    revoked_by,
                    revocation_reason
                FROM core_identity.authorization_grants
                WHERE beneficiary_organization_id = :beneficiary_org_id
                ORDER BY created_at DESC
                """
            ),
            {"beneficiary_org_id": str(beneficiary_organization_id.value)},
        ).fetchall()

        return [
            AuthorizationGrant(
                grant_id=row[0],
                owner_organization_id=OrganizationId(row[1]),
                beneficiary_organization_id=OrganizationId(row[2]),
                policy_id=TypedId("policy", row[3]),
                policy_version_id=TypedId("policy_version", row[4]),
                access_purpose=row[5],
                field_scope_profile=row[6],
                valid_from=row[7],
                valid_until=row[8],
                status=row[9],
                created_at=row[10],
                created_by=row[11],
                revoked_at=row[12],
                revoked_by=row[13],
                revocation_reason=row[14],
            )
            for row in rows
        ]

    def update_status_to_revoked(
        self,
        grant_id: UUID,
        revoked_by: str,
        revocation_reason: str | None = None,
    ) -> None:
        """Marca grant como REVOGADO."""
        self.connection.execute(
            text(
                """
                UPDATE core_identity.authorization_grants
                SET
                    status = 'REVOGADO',
                    revoked_at = CURRENT_TIMESTAMP,
                    revoked_by = :revoked_by,
                    revocation_reason = :revocation_reason
                WHERE grant_id = :grant_id
                """
            ),
            {
                "grant_id": grant_id,
                "revoked_by": revoked_by,
                "revocation_reason": revocation_reason,
            },
        )
