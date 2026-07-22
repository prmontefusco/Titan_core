from pathlib import Path

from packages.core_infrastructure.persistence.outbox import outbox_messages_table


def test_outbox_is_protected_and_preserves_versioned_envelope() -> None:
    assert "PROTECTED" in str(outbox_messages_table.comment)
    for column in (
        "message_id",
        "record_owner_organization_id",
        "kind",
        "contract_type",
        "contract_version",
        "causation_id",
        "payload_canonical_bytes",
        "classification",
        "status",
    ):
        assert column in outbox_messages_table.c


def test_outbox_migration_has_no_update_or_delete_policy() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260722_0013_create_outbox_messages.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260722_0013"' in source
    assert 'down_revision: str | None = "20260722_0012"' in source
    assert "FOR UPDATE" not in source
    assert "FOR DELETE" not in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "fk_outbox_causation_event_owner" in source
