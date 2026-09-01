from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Connection

from packages.core_infrastructure.persistence.authorization_grant import (
    TransactionalAuthorizationGrantRepository,
)


class RecordingConnection:
    def __init__(self) -> None:
        self.statement: object | None = None
        self.parameters: dict[str, Any] | None = None

    def execute(self, statement: object, parameters: dict[str, Any]) -> None:
        self.statement = statement
        self.parameters = parameters


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
