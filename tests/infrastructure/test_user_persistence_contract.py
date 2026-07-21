import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy.dialects.postgresql import UUID

from packages.core_infrastructure.persistence.users import users_table

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "packages"
    / "core_infrastructure"
    / "persistence"
    / "migrations"
    / "versions"
    / "20260721_0003_create_users.py"
)
FORBIDDEN_COLUMNS = {
    "access_token",
    "client_secret",
    "membership_id",
    "password",
    "permission_id",
    "refresh_token",
    "role_id",
    "secret",
    "token",
}


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("user_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_user_table_contains_only_internal_identity_and_record_owner() -> None:
    column_names = set(users_table.c.keys())

    assert column_names == {"user_id", "record_owner_organization_id"}
    assert column_names.isdisjoint(FORBIDDEN_COLUMNS)
    assert users_table.schema == "core_identity"
    assert users_table.c.user_id.primary_key
    assert isinstance(users_table.c.user_id.type, UUID)
    assert not users_table.c.record_owner_organization_id.nullable
    assert users_table.comment == (
        "titan.classification=PROTECTED;titan.module_owner=core_identity"
    )


def test_user_migration_declares_adr_rls_policies_and_no_credentials() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Decisão: ADR 0030" in source
    assert "Classificação: PROTECTED" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "users_select_by_owner" in source
    assert "users_insert_by_owner" in source
    assert "fk_users_record_owner_organization" in source
    assert "REVOKE ALL ON core_identity.users FROM PUBLIC" in source
    for forbidden in FORBIDDEN_COLUMNS:
        assert f'sa.Column("{forbidden}"' not in source


def test_user_migration_is_reversible_and_follows_revision_chain() -> None:
    migration = load_migration()
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert migration.revision == "20260721_0003"
    assert migration.down_revision == "20260721_0002"
    assert "DROP POLICY users_insert_by_owner" in source
    assert "DROP POLICY users_select_by_owner" in source
    assert "op.drop_table(TABLE, schema=SCHEMA)" in source
