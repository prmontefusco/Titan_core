from pathlib import Path

from packages.core_infrastructure.persistence.idempotency import idempotency_records_table


def test_idempotency_table_has_semantic_scope_and_protection() -> None:
    assert "PROTECTED" in str(idempotency_records_table.comment)
    for column in (
        "record_owner_organization_id",
        "idempotency_key",
        "principal_type",
        "principal_id",
        "purpose",
        "operation",
        "intent_digest",
        "result_canonical_bytes",
        "expires_at",
    ):
        assert column in idempotency_records_table.c


def test_idempotency_initial_migration_is_reversible_and_has_no_delete_policy() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260722_0012_create_idempotency_records.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260722_0012"' in source
    assert 'down_revision: str | None = "20260721_0011"' in source
    assert "FOR DELETE" not in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "TRANSICAO_DE_IDEMPOTENCIA_INVALIDA" in source
    assert "idempotency_completion_only" in source
    assert "op.drop_table(TABLE, schema=SCHEMA)" in source


def test_idempotency_expiration_migration_adds_ttl_without_delete_policy() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260909_0086_add_idempotency_expiration.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260909_0086"' in source
    assert 'down_revision: str | None = "20260909_0085"' in source
    assert 'RETENTION_INTERVAL = "30 days"' in source
    assert "expires_at = requested_at + INTERVAL" in source
    assert "ck_idempotency_expires_after_request" in source
    assert "ix_idempotency_records_expired_completed" in source
    assert "status = 'CONCLUIDA'" in source
    assert "FOR DELETE" not in source
    assert "NEW.expires_at <> OLD.expires_at" in source
