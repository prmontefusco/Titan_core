"""Saida do animal do rebanho (Passo 13.1).

Ate aqui o animal nao tinha fim: todo animal cadastrado permanecia
implicitamente vivo e presente. O estado e derivado da existencia desta linha, e
nao de campo mutavel em `animals` — estado guardado em campo diverge do historico
assim que alguem o edita.

Revision ID: 20260725_0043
Revises: 20260724_0042
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260725_0043"
down_revision: str | None = "20260724_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "animal_exits"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("exit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exit_type", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("destination", sa.String(length=255), nullable=True),
        sa.Column(
            "evidence_references",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("exit_id"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_animal_exits_organization",
        ),
        sa.ForeignKeyConstraint(
            ["animal_id"],
            ["core_audit.animals.animal_id"],
            name="fk_animal_exits_animal",
        ),
        # Sair e terminal. Invariante que so a aplicacao garante se perde na
        # primeira execucao concorrente.
        sa.UniqueConstraint("animal_id", name="uq_animal_exits_animal"),
        schema=SCHEMA,
    )

    op.execute(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {SCHEMA}.{TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {TABLE}_isolamento ON {SCHEMA}.{TABLE}
        USING (
            record_owner_organization_id
            = NULLIF(current_setting('titan.organization_id', true), '')::uuid
        )
        WITH CHECK (
            record_owner_organization_id
            = NULLIF(current_setting('titan.organization_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {TABLE}_isolamento ON {SCHEMA}.{TABLE}")
    op.drop_table(TABLE, schema=SCHEMA)
