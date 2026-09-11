"""Consistência de `docs/architecture/verticals.toml` e do portão de propriedade de arquivo.

O manifesto é a fonte da verdade de composição das verticais (ver
`docs/architecture/VERTICAL_OWNERSHIP_MATRIX.md`). Estes testes garantem que ele
permanece internamente coerente e que `scripts/check_file_ownership.py` aplica as
regras de `PARALLEL_VERTICAL_SAFETY`.
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "docs" / "architecture" / "verticals.toml"
GUARD_PATH = PROJECT_ROOT / "scripts" / "check_file_ownership.py"

REQUIRED_VERTICAL_KEYS = frozenset(
    {
        "display_name",
        "status",
        "import_prefix",
        "package_roots",
        "test_roots",
        "owned_path_prefixes",
        "event_namespaces",
        "migration_owner",
        "migration_locations",
    }
)


def _manifest() -> dict[str, Any]:
    return tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_guard() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_check_file_ownership", GUARD_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registrar antes de executar: o maquinário de @dataclass resolve
    # sys.modules[cls.__module__] ao processar as anotações.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_exists_and_declares_schema_version() -> None:
    assert MANIFEST_PATH.exists(), f"{MANIFEST_PATH.relative_to(PROJECT_ROOT)} não existe."
    assert _manifest().get("schema_version") == 1


def test_every_vertical_has_the_required_keys() -> None:
    verticals = _manifest()["verticals"]
    assert verticals, "O manifesto não registra nenhuma vertical."
    for vertical_id, body in verticals.items():
        missing = REQUIRED_VERTICAL_KEYS - body.keys()
        assert not missing, f"Vertical '{vertical_id}' sem as chaves: {sorted(missing)}"


def test_sustainment_is_not_registered_until_decision_b() -> None:
    """`sustainment` só entra depois da decisão B (mesmo vertical_id de `asset` ou irmã).

    Se este teste falhar porque alguém registrou `sustainment`, atualize
    `docs/architecture/DECISIONS_REQUIRED_PHASE0.md` (decisão B) e este teste no
    mesmo PR — conscientemente, não em silêncio.
    """
    assert "sustainment" not in _manifest()["verticals"], (
        "sustainment foi registrado; ver decisão B de DECISIONS_REQUIRED_PHASE0.md"
    )


def test_import_prefixes_are_unique_and_distinct_from_core() -> None:
    manifest = _manifest()
    prefixes = [body["import_prefix"] for body in manifest["verticals"].values()]
    assert len(prefixes) == len(set(prefixes)), f"import_prefix duplicado: {prefixes}"
    core_prefixes = {p.split("_", 1)[0] for p in manifest["core"]["package_prefixes"]}
    assert core_prefixes == {"core"}
    assert "core" not in prefixes
    assert manifest["core"]["shared_kernel"] not in prefixes


def test_owned_path_prefixes_do_not_overlap_between_verticals() -> None:
    verticals = _manifest()["verticals"]
    for left_id, left in verticals.items():
        for right_id, right in verticals.items():
            if left_id >= right_id:
                continue
            for a in left["owned_path_prefixes"]:
                for b in right["owned_path_prefixes"]:
                    assert not (a.startswith(b) or b.startswith(a)), (
                        f"Prefixo de caminho ambíguo entre '{left_id}' ({a}) e '{right_id}' ({b})"
                    )


def test_event_namespaces_and_migration_owners_are_disjoint() -> None:
    verticals = _manifest()["verticals"]
    core_tokens = set(_manifest()["core"].get("module_owner_tokens", []))
    seen_ns: dict[str, str] = {}
    seen_owner: dict[str, str] = {}
    for vertical_id, body in verticals.items():
        for namespace in body["event_namespaces"]:
            assert namespace not in seen_ns, (
                f"Namespace de evento '{namespace}' reivindicado por "
                f"'{seen_ns[namespace]}' e '{vertical_id}'"
            )
            seen_ns[namespace] = vertical_id

        # `migration_owner` + aliases: tokens `titan.module_owner` que a vertical
        # reivindica. Devem ser não vazios, não colidir entre verticais e não
        # colidir com os tokens do Core.
        owner_tokens = {body["migration_owner"], *body.get("migration_owner_aliases", [])}
        assert all(owner_tokens), f"'{vertical_id}': migration_owner/alias vazio"
        assert not (owner_tokens & core_tokens), (
            f"'{vertical_id}': token de migration colide com o Core: {owner_tokens & core_tokens}"
        )
        for token in owner_tokens:
            assert token not in seen_owner, (
                f"Token de migration '{token}' reivindicado por "
                f"'{seen_owner[token]}' e '{vertical_id}'"
            )
            seen_owner[token] = vertical_id


def test_owned_prefixes_that_point_into_the_repo_resolve_or_are_future() -> None:
    """Prefixo que aponta para um arquivo concreto (não termina em '/') e já existe
    deve resolver; prefixos de diretório de vertical ainda não criada são tolerados."""
    verticals = _manifest()["verticals"]
    for vertical_id, body in verticals.items():
        future = body["status"] in {"bootstrap", "planned"}
        for prefix in body["owned_path_prefixes"]:
            if prefix.endswith("/") or prefix.endswith("_"):
                continue
            target = PROJECT_ROOT / prefix
            if not target.exists() and not future:
                pytest.fail(
                    f"'{vertical_id}': prefixo de arquivo '{prefix}' não existe e a "
                    "vertical não está em bootstrap/planned."
                )


# --- portão de propriedade de arquivo -------------------------------------------------


def test_guard_flags_vertical_pr_touching_another_vertical() -> None:
    guard = _load_guard()
    manifest = guard.Manifest.load(MANIFEST_PATH)
    report = guard.evaluate(
        manifest=manifest,
        changed_files=["packages/asset_domain/vehicle.py", "packages/livestock_domain/animal.py"],
        lane="asset",
        change_class="",
    )
    assert not report.ok
    assert any("outra vertical" in v for v in report.violations)


def test_guard_flags_vertical_pr_touching_shared_path() -> None:
    guard = _load_guard()
    manifest = guard.Manifest.load(MANIFEST_PATH)
    report = guard.evaluate(
        manifest=manifest,
        changed_files=["alembic.ini"],
        lane="asset",
        change_class="",
    )
    assert not report.ok
    assert any("compartilhado" in v for v in report.violations)


def test_guard_flags_mixed_shared_integration_pr() -> None:
    guard = _load_guard()
    manifest = guard.Manifest.load(MANIFEST_PATH)
    report = guard.evaluate(
        manifest=manifest,
        changed_files=["alembic.ini", "packages/livestock_domain/animal.py"],
        lane="integration",
        change_class="SHARED_INTEGRATION",
    )
    assert not report.ok
    assert any("PR misto" in v for v in report.violations)


def test_guard_allows_clean_vertical_pr() -> None:
    guard = _load_guard()
    manifest = guard.Manifest.load(MANIFEST_PATH)
    report = guard.evaluate(
        manifest=manifest,
        changed_files=[
            "packages/asset_domain/vehicle.py",
            "tests/asset_domain/test_vehicle.py",
            "docs/asset/05_DOMAIN_MODEL.md",
            "docs/CHECKLIST_DE_IMPLEMENTACAO.md",
        ],
        lane="asset",
        change_class="",
    )
    assert report.ok, report.violations


def test_guard_allows_clean_shared_integration_pr() -> None:
    guard = _load_guard()
    manifest = guard.Manifest.load(MANIFEST_PATH)
    report = guard.evaluate(
        manifest=manifest,
        changed_files=["alembic.ini", "tests/architecture/test_dependency_boundaries.py"],
        lane="integration",
        change_class="SHARED_INTEGRATION",
    )
    assert report.ok, report.violations


def test_guard_requires_change_class_on_integration_branch() -> None:
    guard = _load_guard()
    manifest = guard.Manifest.load(MANIFEST_PATH)
    report = guard.evaluate(
        manifest=manifest,
        changed_files=["alembic.ini"],
        lane="integration",
        change_class="",
    )
    assert not report.ok
    assert any("CHANGE_CLASS=SHARED_INTEGRATION" in v for v in report.violations)
