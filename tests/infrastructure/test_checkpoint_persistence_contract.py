from pathlib import Path

from packages.core_infrastructure.persistence.checkpoints import (
    checkpoint_events_table,
    integrity_checkpoints_table,
)


def test_checkpoint_tables_are_protected_and_preserve_coverage() -> None:
    for table in (integrity_checkpoints_table, checkpoint_events_table):
        assert "PROTECTED" in str(table.comment)
        assert "record_owner_organization_id" in table.c
    assert "checkpoint_digest" in integrity_checkpoints_table.c
    assert "sequence" in checkpoint_events_table.c
    assert "event_hash" in checkpoint_events_table.c


def test_checkpoint_migration_is_append_only_and_reversible() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260721_0010_create_integrity_checkpoints.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260721_0010"' in source
    assert 'down_revision: str | None = "20260721_0009"' in source
    assert source.count("FORCE ROW LEVEL SECURITY") == 1
    assert "FOR UPDATE" not in source
    assert "FOR DELETE" not in source
    assert "op.drop_table(table, schema=SCHEMA)" in source
