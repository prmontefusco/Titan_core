from pathlib import Path

MIGRATION = (
    Path("packages/core_infrastructure/persistence/migrations/versions")
    / "20260907_0080_create_ai_explanation_audit_records.py"
)


def test_ai_explanation_audit_migration_preserves_release_and_rls_invariants() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "core_audit" in source
    assert "ai_explanation_audit_records" in source
    assert "record_owner_organization_id" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "ai_explanation_audit_select" in source
    assert "ai_explanation_audit_insert" in source
    assert "FOR UPDATE" not in source
    assert "FOR DELETE" not in source
    assert "ck_ai_explanation_audit_released_output_digest" in source
    assert "ck_ai_explanation_audit_accepted_disposition" in source
    assert "raw_prompt" not in source
    assert "raw_provider_output" not in source
    assert "raw_source_identifier" not in source
    assert "provider_exception" not in source
