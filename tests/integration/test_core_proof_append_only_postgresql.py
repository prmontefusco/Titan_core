"""Garantias físicas append-only dos registros probatórios Core."""

from sqlalchemy import text

from tests.livestock_api_support import Ambiente


def test_core_proofs_allow_only_select_and_insert_under_rls(ambiente: Ambiente) -> None:
    rows = ambiente.connection.execute(
        text(
            """
            SELECT tablename, cmd
            FROM pg_policies
            WHERE schemaname = 'core_audit'
              AND tablename IN ('evaluations', 'decisions', 'dossiers')
            ORDER BY tablename, cmd
            """
        )
    ).all()

    commands_by_table: dict[str, set[str]] = {}
    for row in rows:
        commands_by_table.setdefault(row.tablename, set()).add(row.cmd)

    assert commands_by_table == {
        "decisions": {"INSERT", "SELECT"},
        "dossiers": {"INSERT", "SELECT"},
        "evaluations": {"INSERT", "SELECT"},
    }
