"""Criar tabela de pedidos de tipo de entidade (EntityTypeRequest).

Registra a intencao declarada por um principal autenticado de operar como um
dos tipos de entidade da vertical Livestock. Nunca concede acesso por si so
(ADR-0031) -- a concessao de Membership/Role acontece so quando o pedido e
aprovado por quem ja tem a permissao de decisao.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA

revision = "20260731_0063"
down_revision = "20260730_0062"
branch_labels = None
depends_on = None

SCHEMA = CORE_AUDIT_SCHEMA
TABLE = "entity_type_requests"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_kind", sa.String(length=40), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("request_id"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_entity_type_requests_organization",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["core_identity.users.user_id"],
            name="fk_entity_type_requests_user",
        ),
        sa.CheckConstraint(
            "status IN ('PENDENTE', 'APROVADA', 'NEGADA')",
            name="ck_entity_type_requests_status",
        ),
        sa.CheckConstraint(
            "(status = 'PENDENTE') = (decided_at IS NULL)",
            name="ck_entity_type_requests_decision_coherente",
        ),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{TABLE}
            USING (
                record_owner_organization_id = NULLIF(
                    current_setting('titan.organization_id', true),
                    ''
                )::uuid
            )
            WITH CHECK (
                record_owner_organization_id = NULLIF(
                    current_setting('titan.organization_id', true),
                    ''
                )::uuid
            )
            """
        )
    )
    op.create_index(
        "ix_entity_type_requests_lookup",
        TABLE,
        ["record_owner_organization_id", "requested_by_user_id", "status"],
        unique=False,
        schema=SCHEMA,
    )
    # Uma pessoa nao pode acumular dois pedidos pendentes na mesma Organization
    # -- a checagem da aplicacao (get_pending_for_user) e reforcada aqui contra
    # corrida entre duas requisicoes concorrentes.
    op.create_index(
        "uq_entity_type_requests_pending_per_user",
        TABLE,
        ["record_owner_organization_id", "requested_by_user_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'PENDENTE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_entity_type_requests_pending_per_user", table_name=TABLE, schema=SCHEMA)
    op.drop_index("ix_entity_type_requests_lookup", table_name=TABLE, schema=SCHEMA)
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{TABLE}"))
    op.drop_table(TABLE, schema=SCHEMA)
