"""Geometria da propriedade contra PostGIS real (Passo 17.1, ADR-0026).

O que estes testes provam, e que nenhum teste em memória provaria: a
transformação de SRID acontece de verdade, geometria topologicamente inválida é
recusada com o motivo, reimportar cria versão nova sem destruir a anterior, e o
polígono de uma Organization é invisível para a outra.
"""

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.livestock_domain.geometry import (
    CAMADA_PERIMETRO,
    SRID_CANONICO,
    GeometriaInvalida,
    GeometrySource,
    PropertyGeometry,
    digest_de,
)
from packages.livestock_infrastructure.persistence.geometry_repository import (
    TransactionalPropertyGeometryRepository,
)
from packages.shared_kernel import OrganizationId, TypedId

# Um quadrado em Brasília, fechado e sem autointerseção.
QUADRADO = json.dumps(
    {
        "type": "Polygon",
        "coordinates": [
            [[-47.9, -15.8], [-47.8, -15.8], [-47.8, -15.7], [-47.9, -15.7], [-47.9, -15.8]]
        ],
    }
)

# Ampulheta: os lados se cruzam no meio. Sintaticamente perfeita, topologicamente
# inválida — o caso que só o PostGIS pega.
AMPULHETA = json.dumps(
    {
        "type": "Polygon",
        "coordinates": [
            [[-47.9, -15.8], [-47.8, -15.7], [-47.8, -15.8], [-47.9, -15.7], [-47.9, -15.8]]
        ],
    }
)


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn, conn.begin():
        yield conn


def _organizacao(conn: Connection) -> OrganizationId:
    organizacao = OrganizationId(uuid4())
    conn.execute(
        text(
            "INSERT INTO core_identity.organizations "
            "(organization_id, record_owner_organization_id) VALUES (:org, :org)"
        ),
        {"org": organizacao.value},
    )
    return organizacao


def _propriedade(conn: Connection, organizacao: OrganizationId, codigo: str) -> TypedId:
    property_id = TypedId.new("rural_property")
    conn.execute(
        text(
            """
            INSERT INTO core_audit.rural_properties (
                property_id, record_owner_organization_id, code, name,
                municipality, state_code, status, version, created_at
            ) VALUES (
                :pid, :org, :code, 'Fazenda de Teste', 'Brasilia', 'DF', 'ACTIVE', 1, :agora
            )
            """
        ),
        {
            "pid": property_id.value,
            "org": organizacao.value,
            "code": codigo,
            "agora": datetime.now(UTC),
        },
    )
    return property_id


def _geometria(
    organizacao: OrganizationId,
    property_id: TypedId,
    payload: str = QUADRADO,
    srid: int = SRID_CANONICO,
    version: int = 1,
    source: GeometrySource = GeometrySource.DECLARADA,
    layer: str = CAMADA_PERIMETRO,
) -> PropertyGeometry:
    return PropertyGeometry(
        geometry_id=TypedId.new("property_geometry"),
        organization_id=organizacao,
        property_id=property_id,
        source=source,
        layer=layer,
        srid=srid,
        source_payload=payload,
        source_digest=digest_de(payload),
        version=version,
    )


def _contexto(conn: Connection, organizacao: OrganizationId) -> None:
    conn.execute(
        text("SELECT set_config('titan.organization_id', :org, true)"),
        {"org": str(organizacao.value)},
    )


def test_a_geometria_e_gravada_e_relida(db_connection: Connection) -> None:
    organizacao = _organizacao(db_connection)
    property_id = _propriedade(db_connection, organizacao, f"P-{uuid4().hex[:8]}")
    _contexto(db_connection, organizacao)
    repositorio = TransactionalPropertyGeometryRepository(connection=db_connection)

    repositorio.save(_geometria(organizacao, property_id))
    encontrada = repositorio.current_for(property_id)

    assert encontrada is not None
    assert encontrada.version == 1
    # O material volta exatamente como entrou, e o digest continua conferindo.
    assert encontrada.source_payload == QUADRADO
    assert encontrada.source_digest == digest_de(QUADRADO)


def test_geometria_topologicamente_invalida_e_recusada_com_motivo(
    db_connection: Connection,
) -> None:
    """Ampulheta passa na validação sintática e só o PostGIS a rejeita."""
    organizacao = _organizacao(db_connection)
    property_id = _propriedade(db_connection, organizacao, f"P-{uuid4().hex[:8]}")
    _contexto(db_connection, organizacao)
    repositorio = TransactionalPropertyGeometryRepository(connection=db_connection)

    with pytest.raises(GeometriaInvalida) as erro:
        repositorio.save(_geometria(organizacao, property_id, payload=AMPULHETA))

    # O motivo do PostGIS viaja: sem ele, achar onde o anel se rompe é inviável.
    assert "Self-intersection" in str(erro.value) or "self-intersection" in str(erro.value)
    assert "não é reparada" in str(erro.value) or "não reparada" in str(erro.value)


def test_srid_diferente_do_canonico_e_transformado(db_connection: Connection) -> None:
    """SIRGAS 2000 / UTM 23S é o que costuma sair de software de topografia."""
    organizacao = _organizacao(db_connection)
    property_id = _propriedade(db_connection, organizacao, f"P-{uuid4().hex[:8]}")
    _contexto(db_connection, organizacao)
    repositorio = TransactionalPropertyGeometryRepository(connection=db_connection)
    utm = json.dumps(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [190000.0, 8250000.0],
                    [191000.0, 8250000.0],
                    [191000.0, 8251000.0],
                    [190000.0, 8250000.0],
                ]
            ],
        }
    )

    repositorio.save(_geometria(organizacao, property_id, payload=utm, srid=31983))

    guardada = db_connection.execute(
        text(
            "SELECT ST_SRID(geom) AS srid, ST_GeometryType(geom) AS tipo "
            "FROM core_audit.property_geometries WHERE property_id = :pid"
        ),
        {"pid": property_id.value},
    ).fetchone()
    assert guardada is not None
    # A coluna é sempre canônica; a origem fica declarada em source_srid.
    assert guardada.srid == SRID_CANONICO
    assert guardada.tipo == "ST_MultiPolygon"

    relida = repositorio.current_for(property_id)
    assert relida is not None
    assert relida.srid == 31983
    assert not relida.normalizada


def test_polygon_simples_vira_multipolygon(db_connection: Connection) -> None:
    """Uniformizar o tipo evita que a consulta trate dois casos."""
    organizacao = _organizacao(db_connection)
    property_id = _propriedade(db_connection, organizacao, f"P-{uuid4().hex[:8]}")
    _contexto(db_connection, organizacao)
    TransactionalPropertyGeometryRepository(connection=db_connection).save(
        _geometria(organizacao, property_id)
    )

    tipo = db_connection.execute(
        text(
            "SELECT ST_GeometryType(geom) AS tipo FROM core_audit.property_geometries "
            "WHERE property_id = :pid"
        ),
        {"pid": property_id.value},
    ).scalar()
    assert tipo == "ST_MultiPolygon"


def test_reimportar_cria_versao_nova_sem_destruir_a_anterior(db_connection: Connection) -> None:
    """Sem isto, a auditoria leria a decisão antiga contra o polígono de hoje."""
    organizacao = _organizacao(db_connection)
    property_id = _propriedade(db_connection, organizacao, f"P-{uuid4().hex[:8]}")
    _contexto(db_connection, organizacao)
    repositorio = TransactionalPropertyGeometryRepository(connection=db_connection)
    maior = json.dumps(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [-47.95, -15.85],
                    [-47.75, -15.85],
                    [-47.75, -15.65],
                    [-47.95, -15.65],
                    [-47.95, -15.85],
                ]
            ],
        }
    )

    repositorio.save(_geometria(organizacao, property_id))
    assert repositorio.next_version_for(property_id) == 2
    repositorio.save(_geometria(organizacao, property_id, payload=maior, version=2))

    historico = repositorio.history_of(property_id)
    assert [g.version for g in historico] == [1, 2]
    # A primeira continua inteira, e é por ela que a avaliação antiga se reproduz.
    assert historico[0].source_payload == QUADRADO
    assert repositorio.current_for(property_id).version == 2  # type: ignore[union-attr]


def test_a_mesma_versao_duas_vezes_e_recusada_pelo_banco(db_connection: Connection) -> None:
    organizacao = _organizacao(db_connection)
    property_id = _propriedade(db_connection, organizacao, f"P-{uuid4().hex[:8]}")
    _contexto(db_connection, organizacao)
    repositorio = TransactionalPropertyGeometryRepository(connection=db_connection)
    repositorio.save(_geometria(organizacao, property_id))

    with pytest.raises(Exception, match="uq_property_geometries_version"):
        repositorio.save(_geometria(organizacao, property_id))


def test_a_geometria_de_outra_organizacao_e_invisivel(db_connection: Connection) -> None:
    """Bounding box e centroide também revelam localização, e o RLS cobre a linha."""
    org_a = _organizacao(db_connection)
    org_b = _organizacao(db_connection)
    property_id = _propriedade(db_connection, org_a, f"P-{uuid4().hex[:8]}")
    _contexto(db_connection, org_a)
    repositorio = TransactionalPropertyGeometryRepository(connection=db_connection)
    repositorio.save(_geometria(org_a, property_id))
    assert repositorio.current_for(property_id) is not None

    db_connection.execute(text("SET LOCAL ROLE titan_rls_probe"))
    try:
        _contexto(db_connection, org_b)
        assert repositorio.current_for(property_id) is None
    finally:
        db_connection.execute(text("RESET ROLE"))


@pytest.fixture(autouse=True)
def _papel_sem_bypass(db_connection: Connection) -> Iterator[None]:
    """O usuário `titan` é superusuário e ignora RLS.

    Teste que afirma isolamento precisa de papel que não o contorne, senão passa
    por acidente e continua passando com o RLS desligado.
    """
    db_connection.execute(
        text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'titan_rls_probe') THEN "
            "CREATE ROLE titan_rls_probe NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF; END $$"
        )
    )
    db_connection.execute(text("GRANT USAGE ON SCHEMA core_audit TO titan_rls_probe"))
    db_connection.execute(text("GRANT SELECT ON core_audit.property_geometries TO titan_rls_probe"))
    yield


def test_a_camada_e_dimensao_e_nao_versao(db_connection: Connection) -> None:
    """Importar a reserva legal nao pode transformar o perimetro em versao antiga."""
    organizacao = _organizacao(db_connection)
    property_id = _propriedade(db_connection, organizacao, f"P-{uuid4().hex[:8]}")
    _contexto(db_connection, organizacao)
    repositorio = TransactionalPropertyGeometryRepository(connection=db_connection)

    repositorio.save(_geometria(organizacao, property_id))
    reserva = json.dumps(
        {
            "type": "Polygon",
            "coordinates": [
                [[-47.89, -15.79], [-47.85, -15.79], [-47.85, -15.75], [-47.89, -15.79]]
            ],
        }
    )
    repositorio.save(_geometria(organizacao, property_id, payload=reserva, layer="RESERVA_LEGAL"))

    # Cada camada comeca na versao 1: elas nao se versionam juntas.
    assert repositorio.next_version_for(property_id, CAMADA_PERIMETRO) == 2
    assert repositorio.next_version_for(property_id, "RESERVA_LEGAL") == 2

    perimetro = repositorio.current_for(property_id, CAMADA_PERIMETRO)
    assert perimetro is not None
    assert perimetro.source_payload == QUADRADO
    assert perimetro.e_perimetro

    protegida = repositorio.current_for(property_id, "RESERVA_LEGAL")
    assert protegida is not None
    assert protegida.e_area_protegida

    assert {g.layer for g in repositorio.current_layers_for(property_id)} == {
        CAMADA_PERIMETRO,
        "RESERVA_LEGAL",
    }
