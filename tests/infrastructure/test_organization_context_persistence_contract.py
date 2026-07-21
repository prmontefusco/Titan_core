from pathlib import Path

from packages.core_infrastructure.persistence.external_identities import (
    external_identities_table,
)


def test_external_identity_has_canonical_key_without_mutable_profile_fields() -> None:
    columns = set(external_identities_table.c.keys())
    assert {"issuer", "subject", "internal_principal_id", "status"} <= columns
    assert not columns.intersection({"email", "username", "name", "token", "password"})


def test_external_identity_migration_is_protected_unique_and_reversible() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260721_0006_create_external_identities.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260721_0006"' in source
    assert 'down_revision: str | None = "20260721_0005"' in source
    assert "uq_external_identities_issuer_subject" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "REVOKE ALL ON core_identity.external_identities FROM PUBLIC" in source
    assert "op.drop_table(TABLE, schema=SCHEMA)" in source
