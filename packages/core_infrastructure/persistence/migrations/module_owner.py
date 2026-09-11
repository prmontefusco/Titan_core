"""Escopo de autogeração do Alembic por dono de módulo (`titan.module_owner`).

Cada tabela do Titan carimba o dono no comentário, no formato
``titan.classification=<C>;titan.module_owner=<owner>`` (ver, p.ex.,
``packages/core_infrastructure/persistence/events.py``). Enquanto o ambiente de
migrations for único, o `env.py` filtra a autogeração por **schema**
(``core_identity`` / ``core_audit``). Quando cada vertical passar a ter o próprio
``env.py`` (passo A-M1 de ``docs/architecture/MIGRATION_CONCURRENCY_STRATEGY.md``),
o filtro por schema não basta — Livestock e Asset dividem o schema ``core_audit``
—, e o `env.py` de cada vertical precisa considerar **apenas** as tabelas do seu
dono, mais as tabelas do Core que são alvo de FK.

Este módulo fornece esse filtro como um `include_object` do Alembic. **Ainda não
é usado por nenhum `env.py`** — é infraestrutura preparada para A-M1, com testes
unitários próprios. Não importa nada de vertical e não altera comportamento.

Contrato para A-M1 (exemplo do `env.py` de Asset)::

    from packages.core_infrastructure.persistence.migrations.module_owner import (
        make_include_object,
    )

    include_object = make_include_object(
        owned_tokens={"asset"},
        fk_allowlist={("core_identity", "organizations")},
    )
    context.configure(..., include_object=include_object, include_schemas=True)
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

TITAN_MODULE_OWNER_KEY = "titan.module_owner"


def parse_titan_comment(comment: str | None) -> dict[str, str]:
    """``"a=1;b=2"`` -> ``{"a": "1", "b": "2"}``. Tolera espaço, item vazio e
    ausência de ``=`` (item sem ``=`` é ignorado)."""
    if not comment:
        return {}
    result: dict[str, str] = {}
    for chunk in comment.split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        key, _, value = chunk.partition("=")
        result[key.strip()] = value.strip()
    return result


def module_owner_of(obj: Any) -> str | None:
    """Dono declarado de uma tabela SQLAlchemy (ou objeto com ``.comment`` /
    ``.info``), ou ``None`` se não houver carimbo."""
    info = getattr(obj, "info", None)
    if isinstance(info, Mapping):
        owner = info.get(TITAN_MODULE_OWNER_KEY) or info.get("module_owner")
        if isinstance(owner, str) and owner:
            return owner
    parsed = parse_titan_comment(getattr(obj, "comment", None))
    return parsed.get(TITAN_MODULE_OWNER_KEY)


IncludeObject = Callable[[Any, str | None, str, bool, Any], bool]


def make_include_object(
    *,
    owned_tokens: Iterable[str],
    fk_allowlist: Iterable[tuple[str | None, str]] = (),
    unowned_table_included: bool = False,
) -> IncludeObject:
    """Constrói um `include_object` do Alembic que aceita apenas tabelas do
    próprio dono, mais os alvos de FK do Core na allowlist.

    - objetos que não são ``table`` (colunas, índices, constraints, …) passam:
      pertencem à tabela pai, cuja inclusão já foi decidida;
    - ``table`` cujo ``titan.module_owner`` ∈ ``owned_tokens`` -> incluída;
    - ``table`` ``(schema, name)`` ∈ ``fk_allowlist`` -> incluída (alvo de FK do
      Core que o `env.py` da vertical precisa enxergar, mas não gerencia);
    - ``table`` sem carimbo de dono -> ``unowned_table_included`` (padrão
      ``False``: fail-closed — a autogeração da vertical ignora o que não é dela,
      em vez de propor criar/remover);
    - ``table`` de outro dono -> excluída.
    """
    owned = frozenset(owned_tokens)
    allow = frozenset(fk_allowlist)
    if not owned:
        raise ValueError("owned_tokens não pode ser vazio.")

    def include_object(
        obj: Any,
        name: str | None,
        type_: str,
        reflected: bool,  # noqa: FBT001 - assinatura fixada pelo Alembic
        compare_to: Any,
    ) -> bool:
        if type_ != "table":
            return True
        schema = getattr(obj, "schema", None)
        if (schema, name or getattr(obj, "name", "")) in allow:
            return True
        owner = module_owner_of(obj)
        if owner is None:
            owner = module_owner_of(compare_to)
        if owner is None:
            return unowned_table_included
        return owner in owned

    return include_object
