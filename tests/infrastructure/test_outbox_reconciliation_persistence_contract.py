"""Testes de contrato da persistencia de reconciliacao da Outbox (Passo 4.9A)."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import Connection

from packages.core_infrastructure.persistence.outbox import (
    TransactionalOutboxReconciliationRepository,
)


def test_transactional_outbox_reconciliation_repository_requires_active_transaction() -> None:
    conn = MagicMock(spec=Connection)
    conn.in_transaction.return_value = False

    with pytest.raises(
        RuntimeError,
        match="TransactionalOutboxReconciliationRepository exige transacao ativa.",
    ):
        TransactionalOutboxReconciliationRepository(connection=conn)
