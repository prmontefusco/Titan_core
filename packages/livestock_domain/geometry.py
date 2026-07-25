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

## Camada do imóvel não é camada territorial

Esta entidade guarda **camadas do imóvel**: perímetro, reserva legal, APP,
hidrografia — partes do próprio cadastro daquela propriedade, que só existem
enquanto ela existe.

**Camadas territoriais são outra coisa.** Embargo do IBAMA, terra indígena da
FUNAI, alerta do PRODES e uso do solo do MapBiomas existem independentemente de
qualquer imóvel; a pergunta que elas respondem não é "qual é a reserva legal
desta fazenda", e sim "esta fazenda intersecta aquela área". Guardá-las aqui
faria uma área pública virar atributo de um imóvel privado, e obrigaria a
duplicá-la para cada propriedade que a tocasse.

Elas exigem modelo próprio — camada versionada com vigência e cobertura, e
avaliação espacial que produz `SpatialAssessment` (ADR-0026) — e é por isso que
`layer` aqui é validada contra o que descreve o imóvel.
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

# O perímetro do imóvel. É a camada que responde "onde fica a fazenda", e por
# isso é o padrão de quem não declara camada alguma.
CAMADA_PERIMETRO = "AREA_IMOVEL"

# Camadas do CAR que descrevem partes do próprio imóvel. A lista é conhecida, e
# não fechada: o provider pode passar a entregar outras, e recusá-las aqui
# obrigaria a alterar o domínio para importar dado que já existe.
CAMADAS_DO_IMOVEL: frozenset[str] = frozenset(
    {
        CAMADA_PERIMETRO,
        "APPS",
        "AREA_CONSOLIDADA",
        "AREA_POUSIO",
        "HIDROGRAFIA",
        "RESERVA_LEGAL",
        "SERVIDAO_ADMINISTRATIVA",
        "USO_RESTRITO",
        "VEGETACAO_NATIVA",
    }
)


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
    # **A camada é dimensão, e não versão.** Perímetro, reserva legal e APP são
    # coisas de natureza diferente sobre o mesmo imóvel: tratá-las como versões
    # faria a reserva legal ser devolvida no lugar do perímetro na consulta
    # seguinte. A versão é por (propriedade, camada).
    layer: str
    srid: int
    source_payload: str
    source_digest: str
    version: int
    captured_at: datetime | None = None
    external_reference: str | None = None
    imported_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = None
    # O que veio junto do provider, sem interpretacao. Guardar evita ter de
    # consultar de novo para saber o que a importacao viu — e a consulta de
    # amanha pode devolver outra coisa, porque o CAR e retificavel.
    source_attributes: dict[str, Any] = field(default_factory=dict)
    # Identifica a resposta INTEIRA; `source_digest` identifica so o poligono.
    response_digest: str | None = None
    # A versão da camada no provider, quando ele a declara. É ela que permite
    # reproduzir a avaliação de hoje contra o material de hoje, meses depois
    # (ADR-0026: comparação reproduzível exige snapshot ou versão identificada).
    layer_version: str | None = None

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
        if not self.layer or not self.layer.strip():
            raise ValueError("layer é obrigatória: sem ela não se sabe o que a geometria é.")
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
        if self.response_digest is not None and len(self.response_digest) != 64:
            raise ValueError("response_digest deve ser um SHA-256 em hexadecimal.")
        if self.source is GeometrySource.SICAR_CAR and not self.external_reference:
            raise ValueError(
                "Geometria vinda do SICAR exige a referência externa (código do imóvel): "
                "sem ela, a importação não é reproduzível."
            )

    @property
    def e_perimetro(self) -> bool:
        """Se esta geometria é o limite do imóvel, e não uma área interna a ele."""
        return self.layer == CAMADA_PERIMETRO

    @property
    def e_area_protegida(self) -> bool:
        """Camadas em que a legislação restringe atividade dentro do imóvel.

        Não é conclusão jurídica: diz que a área foi **declarada** como reserva
        legal, APP ou uso restrito no CAR. Se há gado ali, e se isso é irregular,
        é avaliação com regra versionada — nunca inferência desta propriedade.
        """
        return self.layer in {"APPS", "RESERVA_LEGAL", "USO_RESTRITO"}

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
    _guard_aneis(coordenadas, multiplo=tipo == "MultiPolygon")
    return dados


# Um anel fechado precisa de três posições distintas mais a repetição da
# primeira. Com menos que isso não há área — é linha ou ponto disfarçado.
MINIMO_DE_POSICOES_NO_ANEL = 4


def _guard_aneis(coordenadas: list[Any], multiplo: bool) -> None:
    """Recusa anel degenerado antes de o banco ser acionado.

    **Dado oficial contém isto.** O SICAR entrega camadas com componentes de duas
    posições, e o PostGIS as recusa com "Too few points in geometry component".
    Conferir aqui faz a recusa acontecer com mensagem do domínio, e não depender
    de haver banco — o que também a torna testável sem PostGIS.
    """
    poligonos = coordenadas if multiplo else [coordenadas]
    for poligono in poligonos:
        if not isinstance(poligono, list) or not poligono:
            raise GeometriaInvalida("Polígono sem anéis.")
        for anel in poligono:
            if not isinstance(anel, list) or len(anel) < MINIMO_DE_POSICOES_NO_ANEL:
                quantas = len(anel) if isinstance(anel, list) else 0
                raise GeometriaInvalida(
                    f"Anel com {quantas} posições não delimita área: são necessárias ao "
                    f"menos {MINIMO_DE_POSICOES_NO_ANEL}, sendo a última igual à primeira."
                )
            if anel[0] != anel[-1]:
                raise GeometriaInvalida(
                    "Anel não fechado: a última posição precisa repetir a primeira."
                )


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
