from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "quality.yml"


def test_ci_uses_minimal_permissions_and_pinned_actions() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in content
    assert "persist-credentials: false" in content
    assert "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd" in content
    assert "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405" in content
    assert "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b" in content
    assert "ubuntu-latest" not in content


def test_ci_runs_every_official_quality_command() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")

    expected_commands = {
        "uv lock --check",
        "uv sync --locked",
        "uv run --locked pytest",
        "uv run --locked ruff check .",
        "uv run --locked ruff format --check .",
        "uv run --locked mypy",
    }

    assert all(f"run: {command}" in content for command in expected_commands)
