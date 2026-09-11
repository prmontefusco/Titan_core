"""Portão de propriedade de arquivo para desenvolvimento paralelo de verticais.

Lê `docs/architecture/verticals.toml` e o conjunto de arquivos alterados de um PR,
e recusa combinações que violam `PARALLEL_VERTICAL_SAFETY`
(`docs/architecture/PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md`):

  - PR de uma vertical que toca caminho de OUTRA vertical              -> FALHA
  - PR de uma vertical que toca caminho compartilhado (Lane C)         -> FALHA
    (exceto os arquivos append-only listados em [shared].append_by_any_lane)
  - PR compartilhado (CHANGE_CLASS=SHARED_INTEGRATION) que também toca
    caminho de uma vertical (PR misto)                                 -> FALHA
  - caminho compartilhado tocado sem CHANGE_CLASS=SHARED_INTEGRATION   -> FALHA

A lane vem do prefixo do branch, não do conteúdo do diff:
  vertical/livestock/*  -> lane "livestock"
  vertical/asset/*      -> lane "asset"
  integration/*         -> lane "integration"  (exige CHANGE_CLASS=SHARED_INTEGRATION)
  review/*              -> lane "review"       (não deveria abrir PR de merge)

Uso na CI (GitHub Actions, pull_request):

    python scripts/check_file_ownership.py \
        --manifest docs/architecture/verticals.toml \
        --base-ref "$BASE_SHA" \
        --branch "$HEAD_REF" \
        --change-class "$CHANGE_CLASS"

Uso local:

    python scripts/check_file_ownership.py --files path/a path/b --branch vertical/asset/x
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

SHARED_INTEGRATION = "SHARED_INTEGRATION"


@dataclass(frozen=True)
class Manifest:
    """Visão do `verticals.toml` que o portão precisa."""

    owned_prefixes: dict[str, tuple[str, ...]]  # vertical_id -> prefixos de caminho
    append_by_any_lane: frozenset[str]

    @classmethod
    def load(cls, path: Path) -> Manifest:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        verticals = data.get("verticals", {})
        owned = {
            vertical_id: tuple(body.get("owned_path_prefixes", ()))
            for vertical_id, body in verticals.items()
        }
        shared = data.get("shared", {})
        return cls(
            owned_prefixes=owned,
            append_by_any_lane=frozenset(shared.get("append_by_any_lane", ())),
        )

    def owner_of(self, repo_path: str) -> str | None:
        """`vertical_id` dono do caminho, ou None se for compartilhado (Lane C)."""
        normalized = repo_path.replace("\\", "/")
        for vertical_id, prefixes in self.owned_prefixes.items():
            if any(normalized.startswith(prefix) for prefix in prefixes):
                return vertical_id
        return None


@dataclass
class Report:
    violations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.violations.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)

    @property
    def ok(self) -> bool:
        return not self.violations


def lane_from_branch(branch: str) -> str:
    branch = branch.strip()
    if branch.startswith("vertical/livestock/"):
        return "livestock"
    if branch.startswith("vertical/asset/"):
        return "asset"
    if branch.startswith("vertical/sustainment/"):
        return "sustainment"
    if branch.startswith(("integration/", "shared/")):
        return "integration"
    if branch.startswith("review/"):
        return "review"
    return "unknown"


def changed_files_from_git(base_ref: str) -> list[str]:
    merge_base = subprocess.run(
        ["git", "merge-base", base_ref, "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    diff = subprocess.run(
        ["git", "diff", "--name-only", f"{merge_base}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line.strip() for line in diff.splitlines() if line.strip()]


def evaluate(
    *,
    manifest: Manifest,
    changed_files: Sequence[str],
    lane: str,
    change_class: str,
) -> Report:
    report = Report()
    is_shared_pr = change_class.strip().upper() == SHARED_INTEGRATION

    if not changed_files:
        report.note("Nenhum arquivo alterado; portão de propriedade não se aplica.")
        return report

    owners = {path: manifest.owner_of(path) for path in changed_files}
    touched_verticals = {owner for owner in owners.values() if owner is not None}
    shared_touched = sorted(
        path
        for path, owner in owners.items()
        if owner is None and path not in manifest.append_by_any_lane
    )

    if lane in {"livestock", "asset", "sustainment"}:
        foreign = sorted(
            f"{path}  (dono: {owner})"
            for path, owner in owners.items()
            if owner is not None and owner != lane
        )
        if foreign:
            report.fail(
                f"PR da lane '{lane}' toca caminho(s) de outra vertical:\n  " + "\n  ".join(foreign)
            )
        if shared_touched:
            report.fail(
                f"PR da lane '{lane}' toca caminho(s) compartilhado(s) (Lane C). "
                "Isso exige um PR separado com CHANGE_CLASS=SHARED_INTEGRATION "
                "(docs/architecture/SHARED_CHANGE_PROTOCOL.md §2):\n  "
                + "\n  ".join(shared_touched)
            )
        if is_shared_pr:
            report.fail(
                "PR da lane de vertical não pode declarar CHANGE_CLASS=SHARED_INTEGRATION. "
                "Separe a mudança compartilhada em um PR de branch integration/*."
            )
        return report

    if lane == "integration" or is_shared_pr:
        if not is_shared_pr:
            report.fail(
                "PR de branch integration/* deve declarar CHANGE_CLASS=SHARED_INTEGRATION "
                "(rótulo/entrada no corpo do PR)."
            )
        if len(touched_verticals) > 0:
            mixed = sorted(
                f"{path}  (dono: {owner})" for path, owner in owners.items() if owner is not None
            )
            report.fail(
                "PR de Shared Integration não pode conter também caminhos de feature de vertical "
                "(proíbe o PR misto — docs/architecture/SHARED_CHANGE_PROTOCOL.md §2):\n  "
                + "\n  ".join(mixed)
            )
        report.note(
            f"PR de Shared Integration: {len(shared_touched)} caminho(s) Lane C. "
            "Exige o Nível 2 de CI (Core + todas as verticais)."
        )
        return report

    if lane == "review":
        report.fail(
            "Branch review/* não deve abrir PR de merge. Revisão produz findings, não código."
        )
        return report

    report.fail(
        f"Prefixo de branch não reconhecido para a lane (branch lane='{lane}'). "
        "Use vertical/<id>/*, integration/* ou review/*."
    )
    return report


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="docs/architecture/verticals.toml",
        type=Path,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base-ref", help="ref base do PR; diff é base..HEAD via merge-base")
    source.add_argument("--files", nargs="*", help="lista explícita de caminhos alterados")
    parser.add_argument("--branch", default="", help="nome do branch de origem do PR")
    parser.add_argument(
        "--change-class",
        default="",
        help="'SHARED_INTEGRATION' para PR de Lane C; vazio caso contrário",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    manifest = Manifest.load(args.manifest)
    if args.files is not None:
        changed = [f.strip() for f in args.files if f.strip()]
    else:
        changed = changed_files_from_git(args.base_ref)

    lane = lane_from_branch(args.branch) if args.branch else "unknown"
    report = evaluate(
        manifest=manifest,
        changed_files=changed,
        lane=lane,
        change_class=args.change_class,
    )

    for note in report.notes:
        print(f"[ownership] {note}")
    for violation in report.violations:
        print(f"[ownership] VIOLAÇÃO: {violation}", file=sys.stderr)

    if report.ok:
        print(f"[ownership] OK — lane='{lane}', {len(changed)} arquivo(s).")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
