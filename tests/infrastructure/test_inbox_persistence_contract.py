"""Testes de contrato da persistencia da Inbox (ADR-0038)."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import Connection

from packages.core_infrastructure.persistence.inbox import TransactionalInboxRepository


def test_transactional_inbox_repository_requires_active_transaction() -> None:
    conn = MagicMock(spec=Connection)
    conn.in_transaction.return_value = False

    with pytest.raises(RuntimeError, match="TransactionalInboxRepository exige transacao ativa."):
        TransactionalInboxRepository(connection=conn)
