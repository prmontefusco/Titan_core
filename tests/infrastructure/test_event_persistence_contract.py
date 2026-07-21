from pathlib import Path

from packages.core_infrastructure.persistence.events import domain_events_table


def test_domain_event_table_is_protected_and_append_only_by_contract() -> None:
    assert "PROTECTED" in str(domain_events_table.comment)
    assert "record_owner_organization_id" in domain_events_table.c
    assert "payload_canonical_bytes" in domain_events_table.c
    assert "previous_hash" not in domain_events_table.c
    assert "current_hash" not in domain_events_table.c


def test_event_migration_has_rls_no_mutation_policy_and_reversible_schema() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260721_0008_create_domain_events.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260721_0008"' in source
    assert 'down_revision: str | None = "20260721_0007"' in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "FOR UPDATE" not in source
    assert "FOR DELETE" not in source
    assert "REVOKE ALL ON core_audit.domain_events FROM PUBLIC" in source
    assert "DROP SCHEMA" in source
