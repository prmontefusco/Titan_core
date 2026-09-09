"""Testes de contrato da persistencia da Inbox (ADR-0038)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Connection

from packages.core_infrastructure.persistence.inbox import (
    TransactionalInboxRepository,
    untrusted_message_quarantine_table,
)


def test_transactional_inbox_repository_requires_active_transaction() -> None:
    conn = MagicMock(spec=Connection)
    conn.in_transaction.return_value = False

    with pytest.raises(RuntimeError, match="TransactionalInboxRepository exige transacao ativa."):
        TransactionalInboxRepository(connection=conn)


def test_untrusted_quarantine_has_owner_scope_column() -> None:
    assert "PROTECTED" in str(untrusted_message_quarantine_table.comment)
    assert "record_owner_organization_id" in untrusted_message_quarantine_table.c


def test_untrusted_quarantine_rls_migration_is_owner_scoped() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260909_0085_enable_rls_on_reference_permissions_and_quarantine.py"
    ).read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert 'MESSAGING_SCHEMA = "core_messaging"' in source
    assert 'QUARANTINE_TABLE = "untrusted_message_quarantine"' in source
    assert "untrusted_message_quarantine_select_by_owner" in source
    assert "untrusted_message_quarantine_insert_by_owner_or_unscoped" in source
    assert "fk_untrusted_message_quarantine_owner" in source
