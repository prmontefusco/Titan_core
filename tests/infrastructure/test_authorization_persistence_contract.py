from pathlib import Path

from packages.core_infrastructure.persistence.authorization import (
    assignments_table,
    permissions_table,
    revocations_table,
    role_permissions_table,
    roles_table,
)


def test_no_direct_user_permission_contract_exists() -> None:
    tables = (
        permissions_table,
        roles_table,
        role_permissions_table,
        assignments_table,
        revocations_table,
    )
    assert all("user_id" not in table.c for table in tables)
    assert "membership_id" in assignments_table.c


def test_permission_is_reference_catalog_and_organization_data_is_protected() -> None:
    assert "REFERENCE_CATALOG" in str(permissions_table.comment)
    for table in (roles_table, role_permissions_table, assignments_table, revocations_table):
        assert "PROTECTED" in str(table.comment)
        assert "record_owner_organization_id" in table.c


def test_migration_has_append_only_revocation_rls_and_reversible_chain() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260721_0005_create_roles_permissions.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260721_0005"' in source
    assert 'down_revision: str | None = "20260721_0004"' in source
    assert "MembershipRoleRevocation" not in source
    assert "membership_role_revocations" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "REVOKE ALL ON core_identity.permissions FROM PUBLIC" in source
    assert 'op.drop_table("permissions", schema=SCHEMA)' in source


def test_permissions_rls_reconciliation_migration_keeps_catalog_readable() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260909_0085_enable_rls_on_reference_permissions_and_quarantine.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260909_0085"' in source
    assert 'down_revision: str | None = "20260909_0084"' in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert 'IDENTITY_SCHEMA = "core_identity"' in source
    assert 'PERMISSIONS_TABLE = "permissions"' in source
    assert "permissions_select_reference_catalog" in source
    assert "FOR SELECT USING (true)" in source
    assert "permissions_insert_by_owner" in source
