"""Repositório PostGIS com RLS para a geometria da propriedade (Passo 17.1).

**PostGIS pertence à Infrastructure** (ADR-0026). As funções `ST_*` vivem aqui e
não atravessam a fronteira para o domínio, que guarda o material declarado e não
sabe transformar sistema de referência — isso exige PROJ, e PROJ é do banco.

Duas responsabilidades que só existem aqui:

1. **Transformar para o SRID canônico.** O material pode chegar em qualquer
   sistema; a coluna espacial é 4326. A transformação é registrada em
   `source_srid`, e o original permanece intacto em `source_payload`.
2. **Recusar geometria inválida.** `ST_IsValid` é conferido antes de gravar, e a
   recusa nomeia o motivo. Geometria inválida **não é reparada em silêncio**:
   reparo é derivado novo, com método e diferenças declarados.
"""

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_domain.geometry import (
    SRID_CANONICO,
    GeometriaInvalida,
    GeometrySource,
    PropertyGeometry,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.livestock_infrastructure.persistence.spatial_types import Geometry
from packages.shared_kernel import OrganizationId, TypedId

property_geometries_table = Table(
    "property_geometries",
    livestock_metadata,
    Column("geometry_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("property_id", PG_UUID(as_uuid=True), nullable=False),
    Column("source", String(40), nullable=False),
    Column("source_srid", Integer, nullable=False),
    Column("source_payload", Text, nullable=False),
    Column("source_digest", String(64), nullable=False),
    Column("external_reference", String(120), nullable=True),
    Column("version", Integer, nullable=False),
    Column("captured_at", DateTime(timezone=True), nullable=True),
    Column("imported_at", DateTime(timezone=True), nullable=False),
    Column("notes", String(1000), nullable=True),
    Column("geom", Geometry("MultiPolygon", SRID_CANONICO), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_property_geometries_organization",
    ),
    ForeignKeyConstraint(
        ["property_id"],
        ["core_audit.rural_properties.property_id"],
        name="fk_property_geometries_property",
    ),
    UniqueConstraint("property_id", "version", name="uq_property_geometries_version"),
    CheckConstraint("version >= 1", name="ck_property_geometries_version"),
    CheckConstraint("source_srid > 0", name="ck_property_geometries_srid"),
    CheckConstraint("char_length(source_digest) = 64", name="ck_property_geometries_digest"),
    CheckConstraint("ST_IsValid(geom)", name="ck_property_geometries_geom_valida"),
    Index("ix_property_geometries_property", "property_id", "version"),
    Index("ix_property_geometries_geom", "geom", postgresql_using="gist"),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
)


@dataclass(frozen=True, slots=True)
class TransactionalPropertyGeometryRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalPropertyGeometryRepository exige transacao ativa.")

    def save(self, geometry: PropertyGeometry) -> None:
        """Grava a versão nova, com o material original e a representação canônica.

        A geometria é construída **dentro do banco**, por expressão SQL: trazê-la
        para o Python só para devolvê-la exigiria serializar e desserializar sem
        necessidade, e a única razão para fazê-lo seria manipulá-la aqui — que é
        justamente o que a ADR-0026 mantém do lado da Infrastructure.
        """
        self._guard_valida(geometry.source_payload, geometry.srid)
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.property_geometries (
                    geometry_id, record_owner_organization_id, property_id, source,
                    source_srid, source_payload, source_digest, external_reference,
                    version, captured_at, imported_at, notes, geom
                ) VALUES (
                    :geometry_id, :organization_id, :property_id, :source,
                    :source_srid, :source_payload, :source_digest, :external_reference,
                    :version, :captured_at, :imported_at, :notes,
                    ST_Multi(
                        ST_Transform(
                            ST_SetSRID(ST_GeomFromGeoJSON(:source_payload), :source_srid),
                            :canonico
                        )
                    )
                )
                """
            ),
            {
                "geometry_id": geometry.geometry_id.value,
                "organization_id": geometry.organization_id.value,
                "property_id": geometry.property_id.value,
                "source": geometry.source.value,
                "source_srid": geometry.srid,
                "source_payload": geometry.source_payload,
                "source_digest": geometry.source_digest,
                "external_reference": geometry.external_reference,
                "version": geometry.version,
                "captured_at": geometry.captured_at,
                "imported_at": geometry.imported_at,
                "notes": geometry.notes,
                "canonico": SRID_CANONICO,
            },
        )

    def current_for(self, property_id: TypedId) -> PropertyGeometry | None:
        """A versão vigente é a de maior número — a última importada.

        Versões anteriores permanecem, e é por elas que uma avaliação histórica
        continua sendo reproduzível.
        """
        row = self.connection.execute(
            select(property_geometries_table)
            .where(property_geometries_table.c.property_id == property_id.value)
            .order_by(property_geometries_table.c.version.desc())
            .limit(1)
        ).fetchone()
        return None if row is None else self._mapear(row)

    def get_by_id(self, geometry_id: TypedId) -> PropertyGeometry | None:
        row = self.connection.execute(
            select(property_geometries_table).where(
                property_geometries_table.c.geometry_id == geometry_id.value
            )
        ).fetchone()
        return None if row is None else self._mapear(row)

    def history_of(self, property_id: TypedId) -> list[PropertyGeometry]:
        rows = self.connection.execute(
            select(property_geometries_table)
            .where(property_geometries_table.c.property_id == property_id.value)
            .order_by(property_geometries_table.c.version.asc())
        ).fetchall()
        return [self._mapear(row) for row in rows]

    def next_version_for(self, property_id: TypedId) -> int:
        atual = self.connection.execute(
            select(func.max(property_geometries_table.c.version)).where(
                property_geometries_table.c.property_id == property_id.value
            )
        ).scalar()
        return 1 if atual is None else int(atual) + 1

    def _guard_valida(self, payload: str, srid: int) -> None:
        """Confere a validade topológica antes de gravar, e nomeia o motivo.

        A `CHECK` da tabela já barraria a gravação, mas com mensagem do PostgreSQL
        que não diz **onde** a geometria se rompe. `ST_IsValidReason` diz — e um
        anel que se autointersecta a trinta mil coordenadas de distância é
        impossível de achar sem isso.

        Geometria inválida **não é reparada aqui**: reparo é derivado novo, com
        método, parâmetros e diferenças declarados (ADR-0026).
        """
        linha = self.connection.execute(
            text(
                """
                SELECT ST_IsValid(g) AS valida, ST_IsValidReason(g) AS motivo
                FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:payload), :origem) AS g) AS entrada
                """
            ),
            {"payload": payload, "origem": srid},
        ).fetchone()

        if linha is None:
            raise GeometriaInvalida("O material não produziu geometria alguma.")
        if not linha.valida:
            raise GeometriaInvalida(
                f"Geometria inválida e não reparada: {linha.motivo}. "
                "Reparo é derivado novo, com método e diferenças declarados, e não "
                "acontece em silêncio no momento da gravação."
            )

    @staticmethod
    def _mapear(row: Row[Any]) -> PropertyGeometry:
        imported_at = row.imported_at
        if imported_at.tzinfo is None:
            imported_at = imported_at.replace(tzinfo=UTC)
        captured_at = row.captured_at
        if captured_at is not None and captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)

        return PropertyGeometry(
            geometry_id=TypedId(entity_type="property_geometry", value=row.geometry_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            property_id=TypedId(entity_type="rural_property", value=row.property_id),
            source=GeometrySource(row.source),
            srid=row.source_srid,
            source_payload=row.source_payload,
            source_digest=row.source_digest,
            external_reference=row.external_reference,
            version=row.version,
            captured_at=captured_at,
            imported_at=imported_at,
            notes=row.notes,
        )
