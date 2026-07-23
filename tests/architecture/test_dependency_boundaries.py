import ast
from collections.abc import Iterator
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_ROOT = PROJECT_ROOT / "packages"

# Os pacotes que compõem o Titan Core. A lista é explícita porque um teste de
# fronteira que varre um diretório inexistente passa sem verificar nada — foi o
# que aconteceu enquanto este arquivo apontava para `packages/core`, que nunca
# existiu. `require_existing_root` existe para que isso não se repita em silêncio.
CORE_PACKAGES = ("core_domain", "core_application", "core_infrastructure", "core_integrity")

# O env.py do Alembic é o ponto de composição das migrations de TODO o banco. As
# tabelas de uma vertical que compartilham o schema core_audit precisam ser
# registradas na mesma MetaData do Core para o `alembic check` resolver as FKs e
# não propor removê-las; isso obriga o ambiente de migrations a importar as
# tabelas da vertical. Ele é a única exceção — infraestrutura de composição, não
# lógica reutilizável do Core. Todo o resto do Core permanece proibido de conhecer
# verticais. O caminho mais limpo a prazo é a vertical possuir o próprio ambiente
# de migrations; enquanto elas viverem sob o Core, esta exceção é necessária.
MIGRATIONS_COMPOSITION_ROOT = (
    PACKAGES_ROOT / "core_infrastructure" / "persistence" / "migrations" / "env.py"
)


def require_existing_root(root: Path) -> Path:
    """Falha alto quando o alvo da fronteira não existe.

    Sem esta guarda, renomear um pacote transforma o teste correspondente em
    aprovação automática, que é pior do que não ter o teste.
    """
    assert root.exists(), (
        f"O diretório {root.relative_to(PROJECT_ROOT)} não existe: a fronteira "
        "arquitetural correspondente não está sendo verificada."
    )
    return root


def python_modules(root: Path) -> Iterator[Path]:
    yield from require_existing_root(root).rglob("*.py")


def imported_modules(module: Path) -> Iterator[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def violations_for(root: Path, forbidden: tuple[str, ...]) -> list[str]:
    return [
        f"{module.relative_to(PROJECT_ROOT)} -> {dependency}"
        for module in python_modules(root)
        for dependency in imported_modules(module)
        if any(dependency == prefix or dependency.startswith(f"{prefix}.") for prefix in forbidden)
    ]


def test_reusable_packages_do_not_import_executable_apps() -> None:
    violations = violations_for(PACKAGES_ROOT, ("apps",))

    assert not violations, "Packages reutilizáveis importam apps executáveis:\n" + "\n".join(
        violations
    )


def test_core_domain_does_not_import_framework_or_infrastructure() -> None:
    violations = violations_for(
        PACKAGES_ROOT / "core_domain",
        (
            "apps",
            "fastapi",
            "sqlalchemy",
            "packages.core_infrastructure",
            "packages.verticals",
        ),
    )

    assert not violations, "Core Domain possui dependência proibida:\n" + "\n".join(violations)


def test_core_domain_does_not_import_application() -> None:
    """A dependência aponta para dentro: Application conhece Domain, nunca o contrário."""
    violations = violations_for(PACKAGES_ROOT / "core_domain", ("packages.core_application",))

    assert not violations, "Core Domain importa a camada de aplicação:\n" + "\n".join(violations)


def test_core_application_does_not_import_apps_or_infrastructure() -> None:
    violations = violations_for(
        PACKAGES_ROOT / "core_application", ("apps", "packages.core_infrastructure")
    )

    assert not violations, "Core Application possui dependência proibida:\n" + "\n".join(violations)


def test_core_application_does_not_import_framework() -> None:
    """Caso de uso não conhece HTTP nem ORM: quem os conhece é a Infrastructure."""
    violations = violations_for(PACKAGES_ROOT / "core_application", ("fastapi", "sqlalchemy"))

    assert not violations, "Core Application conhece framework ou ORM:\n" + "\n".join(violations)


def test_shared_kernel_does_not_import_core_or_apps() -> None:
    """O shared kernel é a base do grafo: não pode depender de quem depende dele."""
    violations = violations_for(
        PACKAGES_ROOT / "shared_kernel",
        (
            "apps",
            "fastapi",
            "sqlalchemy",
            "packages.core_domain",
            "packages.core_application",
            "packages.core_infrastructure",
            "packages.verticals",
        ),
    )

    assert not violations, "Shared Kernel possui dependência proibida:\n" + "\n".join(violations)


def test_core_does_not_import_verticals() -> None:
    """Nenhum pacote do Core conhece vertical alguma.

    Examina se os pacotes do Core importam qualquer módulo de verticais
    (ex: packages.livestock_domain, packages.livestock_application, etc).
    """
    forbidden_verticals = (
        "packages.verticals",
        "packages.livestock_domain",
        "packages.livestock_application",
        "packages.livestock_infrastructure",
    )
    violations = [
        f"{module.relative_to(PROJECT_ROOT)} -> {dependency}"
        for package in CORE_PACKAGES
        for module in python_modules(PACKAGES_ROOT / package)
        if module != MIGRATIONS_COMPOSITION_ROOT
        for dependency in imported_modules(module)
        if any(
            dependency == prefix or dependency.startswith(f"{prefix}.")
            for prefix in forbidden_verticals
        )
    ]

    assert not violations, "Titan Core importa módulos de verticais:\n" + "\n".join(violations)


def test_migrations_composition_root_exists() -> None:
    """A exceção acima só é segura enquanto o alvo existir.

    Se o env.py for movido ou renomeado, a exceção viraria letra morta e o teste
    de fronteira voltaria a valer para ele sem ninguém perceber — a mesma classe
    de falha silenciosa que `require_existing_root` evita.
    """
    assert MIGRATIONS_COMPOSITION_ROOT.exists(), (
        "O ponto de composição das migrations não está no caminho esperado; "
        "a exceção de fronteira em test_core_does_not_import_verticals está obsoleta."
    )
