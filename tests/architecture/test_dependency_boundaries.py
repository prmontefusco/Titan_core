import ast
from collections.abc import Iterator
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_ROOT = PROJECT_ROOT / "packages"


def python_modules(root: Path) -> Iterator[Path]:
    if root.exists():
        yield from root.rglob("*.py")


def imported_modules(module: Path) -> Iterator[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_reusable_packages_do_not_import_executable_apps() -> None:
    violations = [
        f"{module.relative_to(PROJECT_ROOT)} -> {dependency}"
        for module in python_modules(PACKAGES_ROOT)
        for dependency in imported_modules(module)
        if dependency == "apps" or dependency.startswith("apps.")
    ]

    assert not violations, "Packages reutilizáveis importam apps executáveis:\n" + "\n".join(
        violations
    )


def test_core_does_not_import_verticals() -> None:
    core_root = PACKAGES_ROOT / "core"
    violations = [
        f"{module.relative_to(PROJECT_ROOT)} -> {dependency}"
        for module in python_modules(core_root)
        for dependency in imported_modules(module)
        if dependency == "packages.verticals" or dependency.startswith("packages.verticals.")
    ]

    assert not violations, "Titan Core importa módulos de verticais:\n" + "\n".join(violations)
