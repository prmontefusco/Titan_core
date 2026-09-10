"""Filtro de autogeração do Alembic por `titan.module_owner` (passo S-M2).

O módulo sob teste ainda não é usado por nenhum `env.py`; estes testes fixam o
contrato que o `env.py` de cada vertical vai consumir em A-M1.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Column, Integer, MetaData, Table

from packages.core_infrastructure.persistence.migrations.module_owner import (
    make_include_object,
    module_owner_of,
    parse_titan_comment,
)


def _table(name: str, *, comment: str | None = None, schema: str | None = "core_audit") -> Table:
    return Table(
        name,
        MetaData(),
        Column("id", Integer, primary_key=True),
        comment=comment,
        schema=schema,
    )


def test_parse_titan_comment_variants() -> None:
    assert parse_titan_comment("titan.classification=PROTECTED;titan.module_owner=livestock") == {
        "titan.classification": "PROTECTED",
        "titan.module_owner": "livestock",
    }
    assert parse_titan_comment(None) == {}
    assert parse_titan_comment("") == {}
    assert parse_titan_comment("  titan.module_owner = asset ; ") == {"titan.module_owner": "asset"}
    assert parse_titan_comment("sem-igual;titan.module_owner=core_audit") == {
        "titan.module_owner": "core_audit"
    }


def test_module_owner_of_reads_comment_then_info() -> None:
    assert module_owner_of(_table("t", comment="titan.module_owner=asset")) == "asset"

    from_info = _table("t2", comment=None)
    from_info.info["titan.module_owner"] = "livestock"
    assert module_owner_of(from_info) == "livestock"

    assert module_owner_of(_table("t3", comment="titan.classification=PROTECTED")) is None
    assert module_owner_of(object()) is None


def test_include_object_passes_non_table_objects_through() -> None:
    include = make_include_object(owned_tokens={"asset"})
    column = _table("t", comment="titan.module_owner=livestock").c.id
    assert include(column, "id", "column", False, None) is True
    assert include(object(), "ix_t", "index", False, None) is True


def test_include_object_includes_own_and_excludes_foreign_tables() -> None:
    include = make_include_object(owned_tokens={"asset"})
    mine = _table("vehicles", comment="titan.classification=PROTECTED;titan.module_owner=asset")
    theirs = _table(
        "animals", comment="titan.classification=PROTECTED;titan.module_owner=livestock"
    )
    assert include(mine, "vehicles", "table", False, None) is True
    assert include(theirs, "animals", "table", False, None) is False


def test_include_object_tolerates_owner_token_aliases() -> None:
    include = make_include_object(owned_tokens={"livestock", "titan_livestock"})
    a = _table("a", comment="titan.module_owner=livestock")
    b = _table("b", comment="titan.module_owner=titan_livestock")
    assert include(a, "a", "table", False, None) is True
    assert include(b, "b", "table", False, None) is True


def test_include_object_honours_fk_allowlist_for_core_targets() -> None:
    include = make_include_object(
        owned_tokens={"asset"},
        fk_allowlist={("core_identity", "organizations")},
    )
    organizations = _table(
        "organizations", comment="titan.module_owner=core_identity", schema="core_identity"
    )
    assert include(organizations, "organizations", "table", False, None) is True


def test_unowned_table_is_excluded_by_default_and_configurable() -> None:
    strict = make_include_object(owned_tokens={"asset"})
    lenient = make_include_object(owned_tokens={"asset"}, unowned_table_included=True)
    orphan = _table("legacy", comment=None)
    assert strict(orphan, "legacy", "table", False, None) is False
    assert lenient(orphan, "legacy", "table", False, None) is True


def test_reflected_table_falls_back_to_compare_to_owner() -> None:
    include = make_include_object(owned_tokens={"asset"})
    reflected = _table("vehicles", comment=None)
    metadata_side = _table("vehicles", comment="titan.module_owner=asset")
    assert include(reflected, "vehicles", "table", True, metadata_side) is True


def test_empty_owned_tokens_is_rejected() -> None:
    with pytest.raises(ValueError, match="owned_tokens"):
        make_include_object(owned_tokens=set())
