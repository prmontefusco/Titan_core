import ast
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_ROOT = PROJECT_ROOT / "packages"
API_ROOT = PROJECT_ROOT / "apps" / "api"
VERTICALS_MANIFEST = PROJECT_ROOT / "docs" / "architecture" / "verticals.toml"

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


# --- fonte da verdade das verticais (docs/architecture/verticals.toml) ---------------
#
# A lista de verticais é SEMPRE explícita no manifesto — nunca inferida do sistema
# de arquivos (evita tratar um pacote qualquer como vertical). Uma vertical
# registrada mas ainda não criada no disco é PULADA pelos testes de fronteira, e
# `test_every_registered_vertical_is_scanned_or_explicitly_pending` garante que
# isso não vira aprovação vazia.


def registered_verticals() -> dict[str, dict[str, object]]:
    data = tomllib.loads(VERTICALS_MANIFEST.read_text(encoding="utf-8"))
    return cast("dict[str, dict[str, object]]", data["verticals"])


def layer_import_prefixes(import_prefix: str) -> tuple[str, ...]:
    return (
        f"packages.{import_prefix}_domain",
        f"packages.{import_prefix}_application",
        f"packages.{import_prefix}_infrastructure",
    )


def existing_layer_roots(import_prefix: str) -> list[Path]:
    roots = [
        PACKAGES_ROOT / f"{import_prefix}_domain",
        PACKAGES_ROOT / f"{import_prefix}_application",
        PACKAGES_ROOT / f"{import_prefix}_infrastructure",
    ]
    return [root for root in roots if root.exists()]


# Superfície de `core_infrastructure` que `<vertical>_application` pode importar
# (DEPENDENCY_RULES.md §5). `<vertical>_infrastructure -> core_infrastructure`
# permanece irrestrito pela matriz de dependência; só a camada de aplicação é
# limitada às portas sancionadas.
CORE_INFRA_APPLICATION_ALLOWLIST = (
    "packages.core_infrastructure.persistence.events",
    "packages.core_infrastructure.persistence.organizations",
    "packages.core_infrastructure.organization_context",
)


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

    Os prefixos proibidos vêm do manifesto: toda vertical registrada
    (`livestock`, `asset`, …) é coberta automaticamente, mesmo antes de existir
    no disco. A exceção nomeada `MIGRATIONS_COMPOSITION_ROOT` permanece.
    """
    forbidden_verticals = ("packages.verticals",) + tuple(
        prefix
        for body in registered_verticals().values()
        for prefix in layer_import_prefixes(str(body["import_prefix"]))
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


def test_every_registered_vertical_is_scanned_or_explicitly_pending() -> None:
    """Guarda contra aprovação vazia dos testes de fronteira por vertical.

    - vertical registrada com pacotes no disco  -> é varrida;
    - vertical registrada sem pacote no disco    -> tolerada só se status
      'bootstrap'/'planned' (senão é regressão de configuração);
    - se NENHUMA vertical registrada foi varrida -> falha (mesma filosofia de
      `require_existing_root`).
    """
    verticals = registered_verticals()
    assert verticals, "O manifesto não registra nenhuma vertical."

    scanned_any = False
    for vertical_id, body in verticals.items():
        prefix = str(body["import_prefix"])
        roots = existing_layer_roots(prefix)
        if roots:
            scanned_any = True
            continue
        status = str(body.get("status", ""))
        assert status in {"bootstrap", "planned"}, (
            f"Vertical '{vertical_id}' registrada (status '{status}') mas nenhum "
            f"pacote packages/{prefix}_* existe: regressão de configuração."
        )

    assert scanned_any, (
        "Nenhuma vertical registrada tem pacotes no disco — os testes de fronteira "
        "por vertical não verificaram nada."
    )


def test_verticals_do_not_import_each_other() -> None:
    """Para cada par ordenado de verticais distintas, `a_*` não importa `b_*`.

    No‑op enquanto só uma vertical existe no disco; passa a valer assim que a
    segunda é criada, sem alteração de código (a lista vem do manifesto).
    """
    verticals = registered_verticals()
    for a_id, a_body in verticals.items():
        a_roots = existing_layer_roots(str(a_body["import_prefix"]))
        if not a_roots:
            continue
        forbidden = tuple(
            prefix
            for b_id, b_body in verticals.items()
            if b_id != a_id
            for prefix in layer_import_prefixes(str(b_body["import_prefix"]))
        )
        if not forbidden:
            continue
        violations = [
            violation for root in a_roots for violation in violations_for(root, forbidden)
        ]
        assert not violations, f"A vertical '{a_id}' importa outra vertical:\n" + "\n".join(
            violations
        )


def test_vertical_domain_stays_pure() -> None:
    """Generaliza a regra do `core_domain` para toda vertical registrada."""
    for vertical_id, body in registered_verticals().items():
        prefix = str(body["import_prefix"])
        domain_root = PACKAGES_ROOT / f"{prefix}_domain"
        if not domain_root.exists():
            continue
        forbidden = (
            "apps",
            "fastapi",
            "sqlalchemy",
            f"packages.{prefix}_application",
            f"packages.{prefix}_infrastructure",
            "packages.core_application",
            "packages.core_infrastructure",
        )
        violations = violations_for(domain_root, forbidden)
        assert not violations, (
            f"O domínio da vertical '{vertical_id}' tem dependência proibida:\n"
            + "\n".join(violations)
        )


def test_vertical_application_does_not_import_framework_or_apps() -> None:
    for vertical_id, body in registered_verticals().items():
        prefix = str(body["import_prefix"])
        application_root = PACKAGES_ROOT / f"{prefix}_application"
        if not application_root.exists():
            continue
        violations = violations_for(application_root, ("apps", "fastapi", "sqlalchemy"))
        assert not violations, (
            f"A aplicação da vertical '{vertical_id}' conhece framework, ORM ou apps:\n"
            + "\n".join(violations)
        )


def test_vertical_application_core_infra_imports_are_allowlisted() -> None:
    """`<vertical>_application -> core_infrastructure` só alcança as portas de
    DEPENDENCY_RULES.md §5. `<vertical>_infrastructure` permanece irrestrito."""
    for vertical_id, body in registered_verticals().items():
        prefix = str(body["import_prefix"])
        application_root = PACKAGES_ROOT / f"{prefix}_application"
        if not application_root.exists():
            continue
        offending = [
            f"{module.relative_to(PROJECT_ROOT)} -> {dependency}"
            for module in python_modules(application_root)
            for dependency in imported_modules(module)
            if (
                dependency == "packages.core_infrastructure"
                or dependency.startswith("packages.core_infrastructure.")
            )
            and not any(
                dependency == allowed or dependency.startswith(f"{allowed}.")
                for allowed in CORE_INFRA_APPLICATION_ALLOWLIST
            )
        ]
        assert not offending, (
            f"A aplicação da vertical '{vertical_id}' importa infraestrutura do Core "
            "fora da allowlist (DEPENDENCY_RULES.md §5):\n" + "\n".join(offending)
        )


def test_core_named_http_adapters_do_not_import_livestock() -> None:
    """Adapter HTTP nomeado como Core não pode interpretar uma vertical."""
    require_existing_root(API_ROOT)
    forbidden_verticals = (
        "apps.api.livestock",
        "packages.livestock_domain",
        "packages.livestock_application",
        "packages.livestock_infrastructure",
    )
    violations = [
        f"{module.relative_to(PROJECT_ROOT)} -> {dependency}"
        for module in API_ROOT.glob("core_*.py")
        for dependency in imported_modules(module)
        if any(
            dependency == prefix or dependency.startswith(f"{prefix}.")
            for prefix in forbidden_verticals
        )
    ]
    assert not violations, "Adapter HTTP Core importa semântica Livestock:\n" + "\n".join(
        violations
    )


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
