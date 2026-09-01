from pathlib import Path

from packages.livestock_infrastructure.persistence.market_supply_query_audit_repository import (
    market_supply_query_audit_records_table,
)

MIGRATION = Path(
    "packages/core_infrastructure/persistence/migrations/versions/"
    "20260831_0078_create_market_supply_query_audit_records.py"
)


def test_market_supply_query_audit_table_is_protected_minimized_and_temporal() -> None:
    assert "PROTECTED" in str(market_supply_query_audit_records_table.comment)
    assert "livestock" in str(market_supply_query_audit_records_table.comment)
    for column in (
        "audit_id",
        "record_owner_organization_id",
        "requester_organization_id",
        "beneficiary_organization_id",
        "access_purpose",
        "authorization_context_digest",
        "policy_id",
        "policy_version",
        "privacy_profile_id",
        "privacy_profile_version",
        "candidate_population_digest",
        "population_digest",
        "query_fingerprint_digest",
        "policy_context_digest",
        "filter_fingerprint",
        "result_subject_count",
        "reference_time",
        "knowledge_cutoff",
        "requested_at",
        "evaluated_at",
        "disclosure_state",
        "decision_reason_codes",
        "outcome",
        "external_disposition",
        "result_digest",
        "revocation_state",
        "correlation_id",
        "idempotency_reference",
        "semantic_request_digest",
        "grant_id",
        "record_digest",
    ):
        assert column in market_supply_query_audit_records_table.c

    forbidden_payload_columns = {
        "animal_id",
        "animal_identifier",
        "property_id",
        "producer_id",
        "evidence_payload",
        "dossier_payload",
        "verification_bundle_payload",
    }
    assert forbidden_payload_columns.isdisjoint(market_supply_query_audit_records_table.c.keys())


def test_market_supply_query_audit_migration_is_append_only_rls_and_reversible() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260831_0078"' in source
    assert 'down_revision: str | None = "20260827_0077"' in source
    assert "core_audit" in source
    assert "market_supply_query_audit_records" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "market_supply_query_audit_select" in source
    assert "market_supply_query_audit_insert" in source
    assert "FOR UPDATE" not in source
    assert "FOR DELETE" not in source
    assert "REVOKE ALL ON core_audit.market_supply_query_audit_records FROM PUBLIC" in source
    assert "op.drop_table(TABLE, schema=SCHEMA)" in source


def test_market_supply_query_audit_migration_uses_owner_only_runtime_rls() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "record_owner_organization_id =" in source
    assert "current_setting('titan.organization_id', true)" in source
    assert "IN (requester_organization_id" not in source
    assert "IN (beneficiary_organization_id" not in source


def test_market_supply_query_audit_migration_preserves_release_invariants() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "ck_market_supply_query_audit_release_disposition" in source
    assert "ck_market_supply_query_audit_result_digest" in source
    assert "ck_market_supply_query_audit_population_digest" in source
    assert "outcome = 'RELEASED' AND result_digest IS NOT NULL" in source
    assert "outcome <> 'RELEASED' AND result_digest IS NULL" in source
    assert "population_digest IS NOT NULL OR outcome <> 'RELEASED'" in source
