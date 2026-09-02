from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Connection

from packages.core_infrastructure.persistence.authorization_grant import (
    TransactionalAuthorizationGrantRepository,
)
from packages.shared_kernel import OrganizationId, TypedId


class RecordingConnection:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self.statement: object | None = None
        self.parameters: dict[str, Any] | None = None
        self.rows = rows or []

    def execute(self, statement: object, parameters: dict[str, Any]) -> "RecordingResult":
        self.statement = statement
        self.parameters = parameters
        return RecordingResult(self.rows)


class RecordingResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


def test_revoke_preserves_revocation_reason_parameter() -> None:
    connection = RecordingConnection()
    grant_id = uuid4()
    revoked_at = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)

    TransactionalAuthorizationGrantRepository(cast(Connection, connection)).revoke(
        grant_id,
        revoked_at=revoked_at,
        revoked_by="security-review",
        revocation_reason="Contrato encerrado",
    )

    assert connection.parameters == {
        "grant_id": grant_id,
        "revoked_at": revoked_at,
        "revoked_by": "security-review",
        "revocation_reason": "Contrato encerrado",
    }
    assert connection.statement is not None
    assert "revocation_reason = :revocation_reason" in str(connection.statement)


def test_list_active_grants_filters_by_policy_beneficiary_purpose_scope_and_time() -> None:
    grant_id = uuid4()
    owner_id = uuid4()
    beneficiary_id = uuid4()
    policy_id = uuid4()
    policy_version_id = uuid4()
    valid_from = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
    valid_until = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    created_at = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
    requested_at = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
    connection = RecordingConnection(
        rows=[
            (
                grant_id,
                owner_id,
                beneficiary_id,
                policy_id,
                policy_version_id,
                "MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
                "MARKET_SUPPLY_AGGREGATE_V1",
                valid_from,
                valid_until,
                "ATIVO",
                created_at,
                "owner-admin",
                None,
                None,
                None,
            )
        ]
    )

    grants = TransactionalAuthorizationGrantRepository(
        cast(Connection, connection)
    ).list_active_by_policy_beneficiary_purpose_scope_at(
        policy_id=TypedId("policy", policy_id),
        beneficiary_organization_id=OrganizationId(beneficiary_id),
        access_purpose="MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
        field_scope_profile="MARKET_SUPPLY_AGGREGATE_V1",
        requested_at=requested_at,
    )

    assert connection.parameters == {
        "policy_id": str(policy_id),
        "beneficiary_org_id": str(beneficiary_id),
        "access_purpose": "MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
        "field_scope_profile": "MARKET_SUPPLY_AGGREGATE_V1",
        "requested_at": requested_at,
    }
    assert connection.statement is not None
    statement = str(connection.statement)
    assert "access_purpose = :access_purpose" in statement
    assert "field_scope_profile = :field_scope_profile" in statement
    assert "valid_from <= :requested_at" in statement
    assert "valid_until > :requested_at" in statement
    assert len(grants) == 1
    assert grants[0].grant_id == grant_id
    assert grants[0].owner_organization_id == OrganizationId(owner_id)
    assert grants[0].beneficiary_organization_id == OrganizationId(beneficiary_id)
