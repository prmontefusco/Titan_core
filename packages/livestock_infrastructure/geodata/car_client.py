"""Cliente do Titan_geodata para consulta de imóvel no CAR (Passo 17.2, ADR-0026).

O Titan_geodata é o **provider externo substituível por contrato versionado** que a
ADR-0026 previa. Ele é a autoridade das camadas; o Titan consome e guarda o que
usou, para que a reprodutibilidade seja responsabilidade sua e não do provedor.

Usa apenas a biblioteca padrão, pelo mesmo critério do cliente do Keycloak:
acrescentar dependência HTTP de produção por causa de uma integração de leitura
seria caro pelo motivo errado.

**O que este cliente não faz:** julgar. `des_condic` diz onde o cadastro está na
fila do SICAR — "Aguardando analise", "Analisado, aguardando atendimento a
notificacao" — e isso é estado de processo, nunca conformidade ambiental.
Convertê-lo em decisão faria o Titan emitir conclusão que ninguém apurou.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from packages.livestock_domain.geometry import digest_de

TIMEOUT_PADRAO_SEGUNDOS = 30
CAMINHO_IMOVEL = "/api/v1/sicar/properties"
CAMINHO_IBAMA_POLIGONO = "/api/v1/ibama/spatial/polygon"


class CarNaoEncontrado(LookupError):
    """O código informado não corresponde a imóvel na base consultada."""


class GeodataIndisponivel(RuntimeError):
    """O provider não respondeu, ou respondeu o que não se sabe interpretar."""


class GeodataNaoConfigurado(RuntimeError):
    """Falta endereço ou chave para consultar o provider."""


@dataclass(frozen=True, slots=True)
class CarProperty:
    """O imóvel como o provider o descreveu, sem interpretação.

    `polygon_payload` é o que vira geometria e sobre o que o digest dela é
    calculado. `response_digest` identifica a **resposta inteira** — os dois
    respondem perguntas diferentes: um diz qual é o limite, o outro diz qual foi
    o material recebido.
    """

    cod_imovel: str
    state: str
    layer: str
    polygon_payload: str
    polygon_digest: str
    response_digest: str
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def captured_at(self) -> datetime | None:
        """Quando o CAR foi atualizado — e não quando foi importado.

        A ADR-0026 separa instante de observação de instante de ingestão, e a
        diferença aqui é grande: há cadastro com dado de cinco anos atrás.
        """
        return _instante(self.attributes.get("dat_atuali"))

    @property
    def municipality(self) -> str | None:
        valor = self.attributes.get("municipio")
        return str(valor) if valor else None

    @property
    def state_code(self) -> str | None:
        valor = self.attributes.get("cod_estado")
        return str(valor).upper() if valor else None

    @property
    def area_hectares(self) -> float | None:
        valor = self.attributes.get("num_area")
        return float(valor) if isinstance(valor, int | float) else None

    @property
    def registry_condition(self) -> str | None:
        """Estado do cadastro na fila do SICAR — nunca conformidade ambiental."""
        valor = self.attributes.get("des_condic")
        return str(valor) if valor else None


@dataclass(frozen=True, slots=True)
class CarLayer:
    """Uma camada do imóvel — perímetro, reserva legal, APP, hidrografia.

    **Camadas não são versões umas das outras.** São naturezas diferentes sobre o
    mesmo imóvel, e o que as separa é o `layer`.
    """

    layer: str
    label: str
    polygon_payload: str
    polygon_digest: str
    area_hectares: float | None
    feature_count: int | None


@dataclass(frozen=True, slots=True)
class SpatialRestriction:
    """Uma feicao territorial que intersecta o poligono consultado."""

    source: str
    layer: str
    feature_id: int | None
    polygon_payload: str
    polygon_digest: str
    response_digest: str
    version_id: str | None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SpatialRestrictionAssessment:
    """Resultado cru de uma consulta espacial por poligono."""

    source: str
    layer: str
    operation: str
    version_ids: tuple[str, ...]
    restriction_count: int
    restrictions: tuple[SpatialRestriction, ...]
    response_digest: str


class CarLookupPort(Protocol):
    def fetch(self, cod_imovel: str, state: str) -> CarProperty: ...

    def fetch_layers(self, cod_imovel: str, state: str) -> list[CarLayer]: ...

    def fetch_ibama_overlaps(
        self, *, polygon_payload: str, srid: int = 4326
    ) -> SpatialRestrictionAssessment: ...


@dataclass(frozen=True, slots=True)
class GeodataCarClient(CarLookupPort):
    """Adapter HTTP. Trocá-lo por outro provider não deve tocar na Application."""

    base_url: str
    api_key: str
    timeout_seconds: int = TIMEOUT_PADRAO_SEGUNDOS

    def __post_init__(self) -> None:
        if not self.base_url.strip() or not self.api_key.strip():
            raise GeodataNaoConfigurado(
                "Consulta ao CAR exige TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY."
            )

    @property
    def chave_mascarada(self) -> str:
        """Identifica a chave sem revela-la.

        "Invalid API key" sem dizer QUAL chave foi usada e o mesmo problema do 500
        sanitizado do Marco 10.4: quem le nao sabe se a variavel chegou vazia,
        truncada, com o placeholder literal ou simplesmente errada. O prefixo
        distingue os quatro casos e nao expoe o segredo.
        """
        if len(self.api_key) <= 12:
            return f"{len(self.api_key)} caracteres"
        return f"{self.api_key[:10]}...{self.api_key[-4:]} ({len(self.api_key)} caracteres)"

    def fetch(self, cod_imovel: str, state: str) -> CarProperty:
        codigo = cod_imovel.strip()
        uf = state.strip().upper()
        if not codigo:
            raise ValueError("cod_imovel não pode ser vazio.")
        if len(uf) != 2:
            raise ValueError("state deve ter duas letras.")

        url = (
            f"{self.base_url.rstrip('/')}{CAMINHO_IMOVEL}/"
            f"{urllib.parse.quote(codigo, safe='')}?{urllib.parse.urlencode({'state': uf})}"
        )
        pedido = urllib.request.Request(
            url,
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(pedido, timeout=self.timeout_seconds) as resposta:
                bruto = resposta.read()
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                raise CarNaoEncontrado(
                    f"Imóvel '{codigo}' não encontrado em {uf} na base consultada."
                ) from erro
            corpo = erro.read().decode("utf-8", errors="replace")[:300]
            raise GeodataIndisponivel(
                f"O provider devolveu {erro.code} para '{codigo}': {corpo}"
                f" (chave usada: {self.chave_mascarada})"
            ) from erro
        except urllib.error.URLError as erro:
            raise GeodataIndisponivel(
                f"Provider inacessível em {self.base_url}: {erro.reason}"
            ) from erro

        return interpretar_resposta(bruto)

    def fetch_layers(self, cod_imovel: str, state: str) -> list[CarLayer]:
        """Todas as camadas que o provider tem para o imóvel.

        A reserva legal e as APPs vêm do próprio CAR: são áreas onde a legislação
        restringe atividade, e chegam sem depender de camada de embargo alguma.
        """
        bruto = self._pedir(
            f"{CAMINHO_IMOVEL}/{urllib.parse.quote(cod_imovel.strip(), safe='')}/layers",
            state,
            cod_imovel,
        )
        try:
            dados = json.loads(bruto)
        except json.JSONDecodeError as erro:
            raise GeodataIndisponivel("O provider não devolveu JSON.") from erro
        if not isinstance(dados, list):
            raise GeodataIndisponivel("A lista de camadas não veio como lista.")
        return [interpretar_camada(item) for item in dados]

    def fetch_ibama_overlaps(
        self, *, polygon_payload: str, srid: int = 4326
    ) -> SpatialRestrictionAssessment:
        """Consulta embargos do IBAMA sobre um poligono informado."""
        if not polygon_payload.strip():
            raise ValueError("polygon_payload não pode ser vazio.")
        if srid <= 0:
            raise ValueError("srid deve ser positivo.")
        try:
            geometry = json.loads(polygon_payload)
        except json.JSONDecodeError as erro:
            raise ValueError("polygon_payload deve ser um GeoJSON válido.") from erro
        if not isinstance(geometry, dict) or geometry.get("type") not in {
            "Polygon",
            "MultiPolygon",
        }:
            raise ValueError("polygon_payload deve descrever Polygon ou MultiPolygon.")

        url = f"{self.base_url.rstrip('/')}{CAMINHO_IBAMA_POLIGONO}"
        pedido = urllib.request.Request(
            url,
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
            method="POST",
            data=json.dumps(
                {"geometry": geometry, "srid": srid},
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8"),
        )
        try:
            with urllib.request.urlopen(pedido, timeout=self.timeout_seconds) as resposta:
                bruto = resposta.read()
        except urllib.error.HTTPError as erro:
            corpo = erro.read().decode("utf-8", errors="replace")[:300]
            raise GeodataIndisponivel(
                f"O provider devolveu {erro.code} na consulta espacial do IBAMA: {corpo}"
                f" (chave usada: {self.chave_mascarada})"
            ) from erro
        except urllib.error.URLError as erro:
            raise GeodataIndisponivel(
                f"Provider inacessível em {self.base_url}: {erro.reason}"
            ) from erro
        return interpretar_restricoes_espaciais(bruto)

    def _pedir(self, caminho: str, state: str, cod_imovel: str) -> bytes:
        uf = state.strip().upper()
        if not cod_imovel.strip():
            raise ValueError("cod_imovel não pode ser vazio.")
        if len(uf) != 2:
            raise ValueError("state deve ter duas letras.")

        url = f"{self.base_url.rstrip('/')}{caminho}?{urllib.parse.urlencode({'state': uf})}"
        pedido = urllib.request.Request(
            url,
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(pedido, timeout=self.timeout_seconds) as resposta:
                resultado: bytes = resposta.read()
                return resultado
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                raise CarNaoEncontrado(
                    f"Imóvel '{cod_imovel}' não encontrado em {uf} na base consultada."
                ) from erro
            corpo = erro.read().decode("utf-8", errors="replace")[:300]
            raise GeodataIndisponivel(
                f"O provider devolveu {erro.code} para '{cod_imovel}': {corpo}"
                f" (chave usada: {self.chave_mascarada})"
            ) from erro
        except urllib.error.URLError as erro:
            raise GeodataIndisponivel(
                f"Provider inacessível em {self.base_url}: {erro.reason}"
            ) from erro


def interpretar_camada(item: Any) -> CarLayer:
    """Uma entrada da lista de camadas, recusando o que não se sabe ler."""
    if not isinstance(item, dict):
        raise GeodataIndisponivel("Entrada de camada malformada.")
    geometria = item.get("geometry")
    if not isinstance(geometria, dict) or "type" not in geometria:
        raise GeodataIndisponivel(
            f"A camada '{item.get('layer')}' não traz geometria reconhecível."
        )
    payload = json.dumps(geometria, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    area = item.get("area_hectares")
    contagem = item.get("feature_count")
    return CarLayer(
        layer=str(item.get("layer", "")),
        label=str(item.get("label", "")),
        polygon_payload=payload,
        polygon_digest=digest_de(payload),
        area_hectares=float(area) if isinstance(area, int | float) else None,
        feature_count=int(contagem) if isinstance(contagem, int) else None,
    )


def interpretar_resposta(bruto: bytes) -> CarProperty:
    """Traduz a resposta do provider, recusando o que não se sabe ler.

    Fica fora do cliente para poder ser exercitada sem rede, e para que trocar o
    transporte não exija reescrever a interpretação.
    """
    texto = bruto.decode("utf-8")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise GeodataIndisponivel("O provider não devolveu JSON.") from erro

    poligono = dados.get("polygon")
    if not isinstance(poligono, dict) or "type" not in poligono:
        raise GeodataIndisponivel("A resposta não traz geometria reconhecível no campo 'polygon'.")

    # Serialização canônica: o mesmo conteúdo produz sempre os mesmos bytes, e é
    # sobre eles que o digest da geometria é calculado.
    payload = json.dumps(poligono, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    return CarProperty(
        cod_imovel=str(dados.get("cod_imovel", "")),
        state=str(dados.get("state", "")).upper(),
        layer=str(dados.get("layer", "")),
        polygon_payload=payload,
        polygon_digest=digest_de(payload),
        response_digest=digest_de(texto),
        attributes=dict(dados.get("properties") or {}),
    )


def interpretar_restricoes_espaciais(bruto: bytes) -> SpatialRestrictionAssessment:
    """Traduz a resposta espacial do provider em tipos do Titan."""
    texto = bruto.decode("utf-8")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise GeodataIndisponivel("O provider não devolveu JSON.") from erro

    dataset = dados.get("dataset")
    if not isinstance(dataset, dict):
        raise GeodataIndisponivel("A resposta espacial não traz metadados do dataset.")
    source = dataset.get("source")
    layer = dataset.get("layer")
    version_ids = dataset.get("version_ids") or []
    if not isinstance(source, str) or not source:
        raise GeodataIndisponivel("A resposta espacial não informa a fonte.")
    if not isinstance(layer, str) or not layer:
        raise GeodataIndisponivel("A resposta espacial não informa a camada.")
    if not isinstance(version_ids, list):
        raise GeodataIndisponivel("version_ids precisa ser uma lista.")

    operation = dados.get("operation")
    count = dados.get("count")
    features = dados.get("features")
    if not isinstance(operation, str) or not operation:
        raise GeodataIndisponivel("A resposta espacial não informa a operação.")
    if not isinstance(count, int):
        raise GeodataIndisponivel("A resposta espacial não informa a contagem.")
    if not isinstance(features, list):
        raise GeodataIndisponivel("A resposta espacial não traz features como lista.")

    restrictions: list[SpatialRestriction] = []
    for item in features:
        if not isinstance(item, dict):
            raise GeodataIndisponivel("Feature espacial malformada.")
        geometria = item.get("geometry")
        propriedades = item.get("properties") or {}
        if not isinstance(geometria, dict) or "type" not in geometria:
            raise GeodataIndisponivel("Feature espacial sem geometria reconhecível.")
        if not isinstance(propriedades, dict):
            raise GeodataIndisponivel("Feature espacial sem propriedades reconhecíveis.")
        payload = json.dumps(geometria, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
        feature_response_digest = digest_de(
            json.dumps(item, separators=(",", ":"), ensure_ascii=False)
        )
        restrictions.append(
            SpatialRestriction(
                source=source,
                layer=layer,
                feature_id=(
                    int(propriedades["id"]) if isinstance(propriedades.get("id"), int) else None
                ),
                polygon_payload=payload,
                polygon_digest=digest_de(payload),
                response_digest=feature_response_digest,
                version_id=(
                    str(propriedades["version_id"])
                    if propriedades.get("version_id") is not None
                    else None
                ),
                attributes=dict(propriedades),
            )
        )

    if count != len(restrictions):
        raise GeodataIndisponivel(
            "A resposta espacial declara uma contagem diferente do número de features."
        )

    return SpatialRestrictionAssessment(
        source=source,
        layer=layer,
        operation=operation,
        version_ids=tuple(str(item) for item in version_ids),
        restriction_count=count,
        restrictions=tuple(restrictions),
        response_digest=digest_de(texto),
    )


def _instante(valor: Any) -> datetime | None:
    """O provider entrega data sem fuso; o Titan só trabalha em UTC."""
    if not valor:
        return None
    try:
        momento = datetime.fromisoformat(str(valor))
    except ValueError:
        return None
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=UTC)
