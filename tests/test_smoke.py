import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_workspace_metadata_can_be_loaded() -> None:
    pyproject = PROJECT_ROOT / "pyproject.toml"

    with pyproject.open("rb") as manifest:
        metadata = tomllib.load(manifest)

    assert metadata["project"]["name"] == "titan"
    assert metadata["project"]["requires-python"] == ">=3.12,<3.13"
    assert set(metadata["project"]["dependencies"]) == {
        "alembic==1.18.5",
        "fastapi==0.139.2",
        "pika>=1.4.1",
        "psycopg[binary]==3.3.4",
        "pyjwt[crypto]==2.13.0",
        "sqlalchemy==2.0.51",
        "uvicorn==0.51.0",
    }
