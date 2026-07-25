"""Evento reprodutivo e origem da identidade do animal (Passo 13.3, ADR-0040).

Ate aqui o animal surgia por cadastro, e `birth_date` era um campo preenchido por
quem digitava. O nascimento passa a ser a origem comprovavel da identidade.

Tres mudancas em `animals`, todas constitutivas e imutaveis:

- `birth_property_id` passa a aceitar nulo, porque ausencia de dado contextual
  nao pode impedir o registro de um fato real ocorrido;
- `birth_property_source` diz de onde veio a propriedade, e o dado vale conforme
  a origem;
- `birth_outcome` distingue nascido vivo de natimorto. Natimorto NAO recebe
  registro de saida: `MORTE` afirmaria que nasceu vivo e morreu depois.

O rebanho legado recebe `NAO_INFORMADO` e `DECLARED` — preencher `NASCIDO_VIVO`
afirmaria o que ninguem registrou.

Revision ID: 20260725_0044
Revises: 20260725_0043
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260725_0044"
down_revision: str | None = "20260725_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
EVENTOS = "reproductive_events"
CRIAS = "reproductive_event_offspring"


def upgrade() -> None:
    op.add_column(
        "animals",
        sa.Column(
            "birth_outcome",
            sa.String(length=20),
            nullable=False,
            server_default="NAO_INFORMADO",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "animals",
        sa.Column(
            "birth_property_source",
            sa.String(length=40),
            nullable=False,
            server_default="DECLARED",
        ),
        schema=SCHEMA,
    )
    op.alter_column(
        "animals",
        "birth_property_id",
        existing_type=postgresql.UUID(),
        nullable=True,
        schema=SCHEMA,
    )
    # A coerencia entre valor e procedencia e do banco, e nao so do servico: um
    # registro que diz de onde veio um dado que nao existe mente sobre si mesmo.
    op.create_check_constraint(
        "ck_animals_birth_property_source",
        "animals",
        "(birth_property_id IS NULL AND birth_property_source = 'UNKNOWN')"
        " OR (birth_property_id IS NOT NULL AND birth_property_source <> 'UNKNOWN')",
        schema=SCHEMA,
    )

    op.create_table(
        EVENTOS,
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dam_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sire_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gestational_age_days", sa.Integer(), nullable=True),
        sa.Column("gestational_age_basis", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("evidence_references", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_reproductive_events_organization",
        ),
        sa.ForeignKeyConstraint(
            ["dam_id"], [f"{SCHEMA}.animals.animal_id"], name="fk_reproductive_events_dam"
        ),
        sa.ForeignKeyConstraint(
            ["sire_id"], [f"{SCHEMA}.animals.animal_id"], name="fk_reproductive_events_sire"
        ),
        # Ausencia significa desconhecido, nunca zero.
        sa.CheckConstraint(
            "gestational_age_days IS NULL OR gestational_age_days > 0",
            name="ck_reproductive_events_gestational_age",
        ),
        sa.CheckConstraint(
            "(gestational_age_days IS NULL AND gestational_age_basis = 'UNKNOWN')"
            " OR (gestational_age_days IS NOT NULL AND gestational_age_basis <> 'UNKNOWN')",
            name="ck_reproductive_events_gestational_basis",
        ),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
    )
    op.create_index("ix_reproductive_events_dam", EVENTOS, ["dam_id", "occurred_at"], schema=SCHEMA)

    op.create_table(
        CRIAS,
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("event_id", "animal_id"),
        sa.ForeignKeyConstraint(
            ["event_id"],
            [f"{SCHEMA}.{EVENTOS}.event_id"],
            name="fk_offspring_event",
        ),
        sa.ForeignKeyConstraint(
            ["animal_id"], [f"{SCHEMA}.animals.animal_id"], name="fk_offspring_animal"
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_offspring_organization",
        ),
        # Um animal nasce de um parto so. Invariante que apenas a aplicacao
        # garante se perde na primeira execucao concorrente.
        sa.UniqueConstraint("animal_id", name="uq_offspring_animal"),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
    )

    for tabela in (EVENTOS, CRIAS):
        op.execute(f"ALTER TABLE {SCHEMA}.{tabela} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {SCHEMA}.{tabela} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {tabela}_isolamento ON {SCHEMA}.{tabela}
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
    for tabela in (CRIAS, EVENTOS):
        op.execute(f"DROP POLICY IF EXISTS {tabela}_isolamento ON {SCHEMA}.{tabela}")
    op.drop_table(CRIAS, schema=SCHEMA)
    op.drop_index("ix_reproductive_events_dam", table_name=EVENTOS, schema=SCHEMA)
    op.drop_table(EVENTOS, schema=SCHEMA)

    op.drop_constraint("ck_animals_birth_property_source", "animals", schema=SCHEMA)
    op.alter_column(
        "animals",
        "birth_property_id",
        existing_type=postgresql.UUID(),
        nullable=False,
        schema=SCHEMA,
    )
    op.drop_column("animals", "birth_property_source", schema=SCHEMA)
    op.drop_column("animals", "birth_outcome", schema=SCHEMA)
