from pathlib import Path


def test_core_audit_tenant_rls_hardening_migration_covers_known_gaps() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260831_0079_harden_core_audit_tenant_rls.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260831_0079"' in source
    assert 'down_revision: str | None = "20260831_0078"' in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    for table in (
        "authorization_grants",
        "decision_proposals",
        "decision_reviews",
        "decision_overrides",
        "decision_contestations",
        "establishment_qualifications",
    ):
        assert table in source
    assert "authorization_grants_select" in source
    assert "beneficiary_organization_id" in source
    assert "FOR DELETE" not in source
