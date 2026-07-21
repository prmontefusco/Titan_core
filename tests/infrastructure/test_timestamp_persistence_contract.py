from pathlib import Path

from packages.core_infrastructure.persistence.timestamping import (
    temporal_anchors_table,
    timestamp_attempts_table,
    timestamp_validations_table,
)


def test_timestamp_tables_are_protected_and_semantically_separate() -> None:
    for table in (timestamp_attempts_table, timestamp_validations_table, temporal_anchors_table):
        assert "PROTECTED" in str(table.comment)
        assert "record_owner_organization_id" in table.c
    assert "raw_token" in timestamp_attempts_table.c
    assert "reason_code" in timestamp_validations_table.c
    assert "proved_at" in temporal_anchors_table.c


def test_timestamp_migration_is_append_only_and_reversible() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260721_0011_create_timestamp_records.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260721_0011"' in source
    assert 'down_revision: str | None = "20260721_0010"' in source
    assert "FOR UPDATE" not in source
    assert "FOR DELETE" not in source
    assert source.count("FORCE ROW LEVEL SECURITY") == 1
    assert "op.drop_table(table, schema=SCHEMA)" in source
