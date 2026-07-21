"""Inicializar o controle técnico de migrations.

Revision ID: 20260721_0001
Revises:
Create Date: 2026-07-21
"""

from collections.abc import Sequence

revision: str = "20260721_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Não cria tabela de domínio; Alembic mantém apenas sua versão técnica."""


def downgrade() -> None:
    """Não há objeto de domínio a remover nesta revisão inicial."""
