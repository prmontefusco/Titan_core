from pathlib import Path

from packages.core_infrastructure.persistence.memberships import memberships_table


def test_membership_table_preserves_temporal_link_and_audit_origin() -> None:
    assert set(memberships_table.c.keys()) == {
        "membership_id",
        "user_id",
        "organization_id",
        "record_owner_organization_id",
        "valid_from",
        "valid_until",
        "status",
        "origin_reference_type",
        "origin_reference_id",
        "granted_by_actor_id",
    }
    assert "role" not in " ".join(memberships_table.c.keys()).lower()
    assert "permission" not in " ".join(memberships_table.c.keys()).lower()


def test_membership_migration_declares_constraints_rls_and_revoke() -> None:
    source = (
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260721_0004_create_memberships.py"
    )
    content = Path(source).read_text(encoding="utf-8")

    assert "record_owner_organization_id = organization_id" in content
    assert "valid_until IS NULL OR valid_until > valid_from" in content
    assert "ENABLE ROW LEVEL SECURITY" in content
    assert "FORCE ROW LEVEL SECURITY" in content
    assert "memberships_select_by_owner" in content
    assert "memberships_insert_by_owner" in content
    assert "REVOKE ALL ON core_identity.memberships FROM PUBLIC" in content
    assert "fk_memberships_user" in content


def test_membership_migration_is_linear_and_reversible() -> None:
    source = (
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260721_0004_create_memberships.py"
    )
    content = Path(source).read_text(encoding="utf-8")

    assert 'revision: str = "20260721_0004"' in content
    assert 'down_revision: str | None = "20260721_0003"' in content
    assert "op.drop_table(TABLE, schema=SCHEMA)" in content
