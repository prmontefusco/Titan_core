import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy.dialects.postgresql import UUID

from packages.core_infrastructure.persistence.organizations import (
    CORE_IDENTITY_SCHEMA,
    ORGANIZATION_CONTEXT_SETTING,
    organizations_table,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "packages"
    / "core_infrastructure"
    / "persistence"
    / "migrations"
    / "versions"
    / "20260721_0002_create_organizations.py"
)


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("organization_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_organization_table_contract_is_protected_and_typed() -> None:
    assert organizations_table.schema == CORE_IDENTITY_SCHEMA
    assert set(organizations_table.c.keys()) == {
        "organization_id",
        "record_owner_organization_id",
    }
    assert organizations_table.c.organization_id.primary_key
    assert isinstance(organizations_table.c.organization_id.type, UUID)
    assert not organizations_table.c.record_owner_organization_id.nullable
    assert ORGANIZATION_CONTEXT_SETTING == "titan.organization_id"


def test_migration_declares_owner_classification_rls_and_policies() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Classificação: PROTECTED" in source
    assert "Módulo owner: core_identity" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "organizations_select_by_owner" in source
    assert "organizations_insert_by_owner" in source
    assert "current_setting('titan.organization_id', true)" in source
    assert "REVOKE ALL ON core_identity.organizations FROM PUBLIC" in source


def test_migration_is_reversible_and_follows_revision_chain() -> None:
    migration = load_migration()
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert migration.revision == "20260721_0002"
    assert migration.down_revision == "20260721_0001"
    assert "DROP POLICY organizations_insert_by_owner" in source
    assert "DROP POLICY organizations_select_by_owner" in source
    assert "op.drop_table(TABLE, schema=SCHEMA)" in source
    assert "DROP SCHEMA" in source
