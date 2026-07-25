"""Geometria da propriedade rural (Passo 17.1 - Titan Livestock, ADR-0026).

Primeira coluna espacial do Titan. A ADR-0026 autorizou o PostGIS em 21/07/2026 e
o colocou no caminho crítico do MVP; até aqui ele estava ativo no banco e ausente
do domínio, e `RuralProperty` guardava município e UF.

**Geometria é evidência, não verdade automática.** Um polígono estruturalmente
válido não comprova titularidade, regularidade ambiental nem conformidade
jurídica — comprova apenas que alguém declarou aquele limite, por aquela fonte,
naquele instante.

**A geometria é entidade própria, e não campo da propriedade.** Reimportar o CAR
cria uma **versão nova**; a anterior permanece, e avaliações antigas continuam
apontando para a que usaram. Sobrescrever faria a auditoria de 2027 ler a decisão
de 2025 contra um polígono que não existia na época — que é o que a ADR-0026
proíbe ao dizer que geometria atual não substitui versão histórica.

**O material recebido é preservado.** Normalizar destruindo o original impediria
auditar a própria transformação, e a ADR-0026 distingue `SourceGeometry` de
`NormalizedGeometry` justamente por isso.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc

# WGS 84. É o sistema que a EUDR espera e o alvo canônico da normalização.
SRID_CANONICO = 4326

# Só limite de área entra aqui. Ponto não é promovido a polígono nem
# interpretado como limite cadastral (ADR-0026).
TIPOS_ADMITIDOS: frozenset[str] = frozenset({"Polygon", "MultiPolygon"})


class GeometrySource(StrEnum):
    """De onde veio o limite declarado.

    Localização declarada, importada de fonte oficial e derivada por cálculo
    permanecem semanticamente distintas: o dado vale conforme a origem, e a
    origem é consultável.
    """

    SICAR_CAR = "SICAR_CAR"
    DECLARADA = "DECLARADA"
    IMPORTADA_DE_TERCEIRO = "IMPORTADA_DE_TERCEIRO"


class GeometryRepresentation(StrEnum):
    """Qual representação este registro guarda (ADR-0026).

    `REPARADA` não é emitida por este passo: geometria inválida é recusada, e
    reparo é derivado novo com método, parâmetros e diferenças declarados.
    """

    SOURCE = "SOURCE"
    NORMALIZED = "NORMALIZED"


class GeometriaInvalida(ValueError):
    """O material recebido não pode ser admitido como limite de propriedade."""


@dataclass(frozen=True, slots=True)
class PropertyGeometry:
    """Um limite declarado de propriedade, imutável e versionado."""

    geometry_id: TypedId
    organization_id: OrganizationId
    property_id: TypedId
    source: GeometrySource
    srid: int
    source_payload: str
    source_digest: str
    version: int
    captured_at: datetime | None = None
    external_reference: str | None = None
    imported_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = None

    def __post_init__(self) -> None:
        require_utc(self.imported_at, field_name="imported_at")
        if self.captured_at is not None:
            require_utc(self.captured_at, field_name="captured_at")
        if self.geometry_id.entity_type != "property_geometry":
            raise ValueError(
                "geometry_id deve ter entity_type 'property_geometry', recebido "
                f"'{self.geometry_id.entity_type}'."
            )
        if self.property_id.entity_type != "rural_property":
            raise ValueError("property_id deve apontar para uma propriedade rural.")
        if not isinstance(self.source, GeometrySource):
            raise TypeError("source deve ser um GeometrySource.")
        if self.version < 1:
            raise ValueError("version deve ser >= 1.")
        # Coordenada sem sistema de referência conhecido é recusada: um número sem
        # SRID não localiza nada, e adivinhá-lo produziria interseção falsa.
        if self.srid <= 0:
            raise GeometriaInvalida("srid é obrigatório e deve ser positivo.")
        if self.source_digest != digest_de(self.source_payload):
            raise GeometriaInvalida(
                "source_digest não confere com o material declarado: o registro "
                "afirmaria proveniência de um conteúdo que não é o dele."
            )
        if self.external_reference is not None and not self.external_reference.strip():
            raise ValueError("external_reference, quando informado, não pode ser vazio.")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("notes, quando informado, não pode ser vazio.")
        if self.source is GeometrySource.SICAR_CAR and not self.external_reference:
            raise ValueError(
                "Geometria vinda do SICAR exige a referência externa (código do imóvel): "
                "sem ela, a importação não é reproduzível."
            )

    @property
    def normalizada(self) -> bool:
        """Se o material já chegou no sistema de referência canônico.

        Quando não, a Infrastructure guarda também a representação transformada —
        e a transformação é registrada, nunca silenciosa.
        """
        return self.srid == SRID_CANONICO


def digest_de(payload: str) -> str:
    """SHA-256 do material exatamente como recebido.

    Calculado sobre o texto original, e não sobre uma reserialização: reserializar
    normalizaria espaços e ordem de chaves, e o digest deixaria de identificar o
    que de fato chegou.
    """
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validar_geojson(payload: str) -> dict[str, Any]:
    """Confere o que dá para conferir sem banco: forma, tipo e coordenadas.

    A validade **topológica** — anéis que se cruzam, buracos fora do polígono — é
    do PostGIS, e a Infrastructure a confere com `ST_IsValid` antes de gravar.
    Aqui recusa-se o que é malformado antes mesmo de chegar lá.
    """
    try:
        dados = json.loads(payload)
    except json.JSONDecodeError as erro:
        raise GeometriaInvalida(f"O material não é JSON válido: {erro}") from erro

    if not isinstance(dados, dict):
        raise GeometriaInvalida("A geometria deve ser um objeto GeoJSON.")

    tipo = dados.get("type")
    if tipo not in TIPOS_ADMITIDOS:
        raise GeometriaInvalida(
            f"Tipo '{tipo}' não é admitido como limite de propriedade. "
            f"Aceitos: {', '.join(sorted(TIPOS_ADMITIDOS))}. "
            "Ponto não é promovido a polígono nem interpretado como limite cadastral."
        )

    coordenadas = dados.get("coordinates")
    if not isinstance(coordenadas, list) or not coordenadas:
        raise GeometriaInvalida("A geometria não declara coordenadas.")

    _guard_coordenadas(coordenadas)
    return dados


def _guard_coordenadas(valor: Any, profundidade: int = 0) -> None:
    """Percorre a árvore de coordenadas até os pares, conferindo cada um.

    Longitude e latitude fora de faixa costumam ser eixos invertidos — um erro
    que produz geometria sintaticamente válida em lugar nenhum do planeta.
    """
    if profundidade > 4:
        raise GeometriaInvalida("Estrutura de coordenadas aninhada além do admitido.")
    if not isinstance(valor, list) or not valor:
        raise GeometriaInvalida("Estrutura de coordenadas malformada.")

    if isinstance(valor[0], int | float):
        if len(valor) < 2:
            raise GeometriaInvalida("Cada coordenada exige ao menos longitude e latitude.")
        longitude, latitude = valor[0], valor[1]
        if not -180 <= longitude <= 180:
            raise GeometriaInvalida(
                f"Longitude {longitude} fora da faixa [-180, 180]. "
                "Conferir se os eixos não estão invertidos."
            )
        if not -90 <= latitude <= 90:
            raise GeometriaInvalida(
                f"Latitude {latitude} fora da faixa [-90, 90]. "
                "Conferir se os eixos não estão invertidos."
            )
        return

    for parte in valor:
        _guard_coordenadas(parte, profundidade + 1)
