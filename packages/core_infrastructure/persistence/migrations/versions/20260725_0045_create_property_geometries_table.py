"""Geometria da propriedade rural (Passo 17.1, ADR-0026).

Primeira coluna espacial do Titan. A extensao PostGIS esta ativa desde o Passo
1.4A e a ADR-0026 a colocou no caminho critico em 21/07/2026; ate aqui ela estava
no banco e ausente do dominio.

Duas representacoes coexistem, e a distincao e da ADR-0026:

- `source_payload` guarda o material EXATAMENTE como recebido, com digest. Ele
  nunca e reserializado: reserializar normalizaria espacos e ordem de chaves, e o
  digest deixaria de identificar o que chegou.
- `geom` guarda a representacao normalizada em SRID 4326, para as operacoes
  espaciais. A transformacao e registrada em `source_srid`, nunca silenciosa.

A tabela e append-only por versao: reimportar o CAR cria linha nova com
`version` incrementada. Sobrescrever faria a auditoria de 2027 ler a decisao de
2025 contra um poligono que nao existia na epoca.

Revision ID: 20260725_0045
Revises: 20260725_0044
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260725_0045"
down_revision: str | None = "20260725_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABELA = "property_geometries"
SRID = 4326


def upgrade() -> None:
    # A extensao precisa existir antes da coluna. Falhar aqui e explicito e
    # preferivel a criar a tabela sem o tipo espacial e descobrir na primeira
    # consulta.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        TABELA,
        sa.Column("geometry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("layer", sa.String(length=60), nullable=False, server_default="AREA_IMOVEL"),
        sa.Column("source_srid", sa.Integer(), nullable=False),
        sa.Column("source_payload", sa.Text(), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=False),
        sa.Column("external_reference", sa.String(length=120), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.PrimaryKeyConstraint("geometry_id"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_property_geometries_organization",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            [f"{SCHEMA}.rural_properties.property_id"],
            name="fk_property_geometries_property",
        ),
        # Uma versao por (propriedade, CAMADA). A camada e dimensao, e nao
        # versao: perimetro, reserva legal e APP sao naturezas diferentes sobre o
        # mesmo imovel, e versiona-las juntas faria a reserva legal ser devolvida
        # no lugar do perimetro.
        sa.UniqueConstraint(
            "property_id", "layer", "version", name="uq_property_geometries_version"
        ),
        sa.CheckConstraint("version >= 1", name="ck_property_geometries_version"),
        sa.CheckConstraint("source_srid > 0", name="ck_property_geometries_srid"),
        sa.CheckConstraint("char_length(source_digest) = 64", name="ck_property_geometries_digest"),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
    )

    # A coluna espacial entra por AddGeometryColumn para que o SRID fique
    # registrado no catalogo do PostGIS, e nao apenas na definicao da coluna.
    op.execute(
        f"SELECT AddGeometryColumn('{SCHEMA}', '{TABELA}', 'geom', {SRID}, 'MULTIPOLYGON', 2)"
    )
    op.execute(f"ALTER TABLE {SCHEMA}.{TABELA} ALTER COLUMN geom SET NOT NULL")
    # Geometria invalida nao e corrigida em silencio: ela nao entra. Reparo e
    # derivado novo, com metodo e diferencas declarados (ADR-0026).
    op.execute(
        f"ALTER TABLE {SCHEMA}.{TABELA} "
        f"ADD CONSTRAINT ck_{TABELA}_geom_valida CHECK (ST_IsValid(geom))"
    )
    op.execute(f"CREATE INDEX ix_{TABELA}_geom ON {SCHEMA}.{TABELA} USING GIST (geom)")
    op.create_index(
        f"ix_{TABELA}_property", TABELA, ["property_id", "layer", "version"], schema=SCHEMA
    )

    op.execute(f"ALTER TABLE {SCHEMA}.{TABELA} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {SCHEMA}.{TABELA} FORCE ROW LEVEL SECURITY")
    # Bounding box, centroide e qualquer derivado espacial revelam localizacao
    # protegida, e por isso a politica cobre a linha inteira.
    op.execute(
        f"""
        CREATE POLICY {TABELA}_isolamento ON {SCHEMA}.{TABELA}
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
    op.execute(f"DROP POLICY IF EXISTS {TABELA}_isolamento ON {SCHEMA}.{TABELA}")
    op.drop_index(f"ix_{TABELA}_property", table_name=TABELA, schema=SCHEMA)
    op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.ix_{TABELA}_geom")
    op.drop_table(TABELA, schema=SCHEMA)
    # A extensao NAO e removida: outras tabelas podem passar a depender dela, e
    # remove-la aqui derrubaria o que veio depois. Reverter a extensao exige ADR
    # propria, conforme o plano de reversao da ADR-0026.
