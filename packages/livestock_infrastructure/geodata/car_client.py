"""Cliente do Titan_geodata para consulta de imovel no CAR (Passo 17.2, ADR-0026).

O Titan_geodata e o **provider externo substituivel por contrato versionado** que a
ADR-0026 previa. Ele e a autoridade das camadas; o Titan consome e guarda o que
usou, para que a reprodutibilidade seja responsabilidade sua e nao do provedor.

Usa apenas a biblioteca padrao, pelo mesmo criterio do cliente do Keycloak:
acrescentar dependencia HTTP de producao por causa de uma integracao de leitura
seria caro pelo motivo errado.

**O que este cliente nao faz:** julgar. `des_condic` diz onde o cadastro esta na
fila do SICAR - "Aguardando analise", "Analisado, aguardando atendimento a
notificacao" - e isso e estado de processo, nunca conformidade ambiental.
Converte-lo em decisao faria o Titan emitir conclusao que ninguem apurou.
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
CAMINHO_FARM = "/api/v1/sicar/farm"
CAMINHO_IBAMA_POLIGONO = "/api/v1/ibama/spatial/polygon"


class CarNaoEncontrado(LookupError):
    """O codigo informado nao corresponde a imovel na base consultada."""


class GeodataIndisponivel(RuntimeError):
    """O provider nao respondeu, ou respondeu o que nao se sabe interpretar."""


class GeodataNaoConfigurado(RuntimeError):
    """Falta endereco ou chave para consultar o provider."""


@dataclass(frozen=True, slots=True)
class CarProperty:
    """O imovel como o provider o descreveu, sem interpretacao.

    `polygon_payload` e o que vira geometria e sobre o que o digest dela e
    calculado. `response_digest` identifica a **resposta inteira** - os dois
    respondem perguntas diferentes: um diz qual e o limite, o outro diz qual foi
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
        """Quando o CAR foi atualizado - e nao quando foi importado.

        A ADR-0026 separa instante de observacao de instante de ingestao, e a
        diferenca aqui e grande: ha cadastro com dado de cinco anos atras.
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
        """Estado do cadastro na fila do SICAR - nunca conformidade ambiental."""
        valor = self.attributes.get("des_condic")
        return str(valor) if valor else None


@dataclass(frozen=True, slots=True)
class CarLayer:
    """Uma camada do imovel - perimetro, reserva legal, APP, hidrografia.

    **Camadas nao sao versoes umas das outras.** Sao naturezas diferentes sobre o
    mesmo imovel, e o que as separa e o `layer`.
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


@dataclass(frozen=True, slots=True)
class TerritorialTimelineYear:
    """Um ano da serie temporal devolvida pelo provider territorial."""

    year: int | None
    feature_count: int
    overlap_area_hectares: float | None
    source_area_hectares: float | None
    version_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TerritorialTimelineAssessment:
    """Resultado cru de uma camada territorial sensivel ao tempo."""

    source: str
    layer: str
    property_area_hectares: float | None
    year_from: int | None
    year_to: int | None
    years: tuple[TerritorialTimelineYear, ...]
    response_digest: str


@dataclass(frozen=True, slots=True)
class TerritorialOverlapAssessment:
    """Resultado cru de uma camada territorial atual baseada em sobreposicao."""

    source: str
    layer: str
    label: str
    feature_count: int
    area_hectares: float | None
    source_area_hectares: float | None
    version_ids: tuple[str, ...]
    response_digest: str


class CarLookupPort(Protocol):
    def fetch(self, cod_imovel: str, state: str) -> CarProperty: ...

    def fetch_layers(self, cod_imovel: str, state: str) -> list[CarLayer]: ...

    def fetch_ibama_overlaps(
        self, *, polygon_payload: str, srid: int = 4326
    ) -> SpatialRestrictionAssessment: ...

    def fetch_prodes_timeline(
        self,
        *,
        cod_imovel: str,
        state: str,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> TerritorialTimelineAssessment: ...

    def fetch_deter_timeline(
        self,
        *,
        cod_imovel: str,
        state: str,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> TerritorialTimelineAssessment: ...

    def fetch_funai_overlap(
        self,
        *,
        cod_imovel: str,
        state: str,
    ) -> TerritorialOverlapAssessment: ...


@dataclass(frozen=True, slots=True)
class GeodataCarClient(CarLookupPort):
    """Adapter HTTP. Troca-lo por outro provider nao deve tocar na Application."""

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
        return interpretar_resposta(self._pedir_farm(cod_imovel, state))

    def fetch_layers(self, cod_imovel: str, state: str) -> list[CarLayer]:
        """Todas as camadas que o provider tem para o imovel.

        A reserva legal e as APPs vem do proprio CAR: sao areas onde a legislacao
        restringe atividade, e chegam sem depender de camada de embargo alguma.
        """
        bruto = self._pedir_farm(cod_imovel, state)
        try:
            dados = json.loads(bruto)
        except json.JSONDecodeError as erro:
            raise GeodataIndisponivel("O provider nao devolveu JSON.") from erro
        if isinstance(dados, dict) and isinstance(dados.get("layers"), list):
            return [interpretar_camada(item) for item in dados["layers"]]
        if isinstance(dados, list):
            return [interpretar_camada(item) for item in dados]
        raise GeodataIndisponivel("A lista de camadas nao veio como lista.")

    def fetch_ibama_overlaps(
        self, *, polygon_payload: str, srid: int = 4326
    ) -> SpatialRestrictionAssessment:
        """Consulta embargos do IBAMA sobre um poligono informado."""
        if not polygon_payload.strip():
            raise ValueError("polygon_payload nao pode ser vazio.")
        if srid <= 0:
            raise ValueError("srid deve ser positivo.")
        try:
            geometry = json.loads(polygon_payload)
        except json.JSONDecodeError as erro:
            raise ValueError("polygon_payload deve ser um GeoJSON valido.") from erro
        if not isinstance(geometry, dict) or geometry.get("type") not in {
            "Polygon",
            "MultiPolygon",
        }:
            raise ValueError("polygon_payload deve descrever Polygon ou MultiPolygon.")

        url = f"{self.base_url.rstrip('/')}{CAMINHO_IBAMA_POLIGONO}"
        pedido = urllib.request.Request(
            url,
            headers={
                "X-API-Key": self.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
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
                f"Provider inacessivel em {self.base_url}: {erro.reason}"
            ) from erro
        return interpretar_restricoes_espaciais(bruto)

    def fetch_prodes_timeline(
        self,
        *,
        cod_imovel: str,
        state: str,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> TerritorialTimelineAssessment:
        """Consulta a serie temporal territorial do PRODES para um imovel."""
        if year_from is not None and year_to is not None and year_from > year_to:
            raise ValueError("year_from deve ser menor ou igual a year_to.")
        bruto = self._pedir_timeline(
            cod_imovel=cod_imovel,
            state=state,
            layer="TB_PRODES",
            year_from=year_from,
            year_to=year_to,
        )
        return interpretar_timeline_territorial(bruto)

    def fetch_deter_timeline(
        self,
        *,
        cod_imovel: str,
        state: str,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> TerritorialTimelineAssessment:
        """Consulta a serie temporal territorial do DETER para um imovel."""
        if year_from is not None and year_to is not None and year_from > year_to:
            raise ValueError("year_from deve ser menor ou igual a year_to.")
        bruto = self._pedir_timeline(
            cod_imovel=cod_imovel,
            state=state,
            layer="TB_DETER",
            year_from=year_from,
            year_to=year_to,
        )
        return interpretar_timeline_territorial(bruto)

    def fetch_funai_overlap(
        self,
        *,
        cod_imovel: str,
        state: str,
    ) -> TerritorialOverlapAssessment:
        """Consulta a sobreposicao territorial atual da FUNAI para um imovel."""
        for layer in self.fetch_layers(cod_imovel, state):
            if layer.layer == "FUNAI_TI":
                return TerritorialOverlapAssessment(
                    source="FUNAI",
                    layer=layer.layer,
                    label=layer.label,
                    feature_count=layer.feature_count or 0,
                    area_hectares=layer.area_hectares,
                    source_area_hectares=layer.area_hectares,
                    version_ids=(),
                    response_digest=layer.polygon_digest,
                )
        return TerritorialOverlapAssessment(
            source="FUNAI",
            layer="FUNAI_TI",
            label="Terras Indigenas (FUNAI)",
            feature_count=0,
            area_hectares=None,
            source_area_hectares=None,
            version_ids=(),
            response_digest=digest_de("FUNAI_TI:ausente"),
        )

    def _pedir(self, caminho: str, state: str, cod_imovel: str) -> bytes:
        uf = state.strip().upper()
        if not cod_imovel.strip():
            raise ValueError("cod_imovel nao pode ser vazio.")
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
                    f"Imovel '{cod_imovel}' nao encontrado em {uf} na base consultada."
                ) from erro
            corpo = erro.read().decode("utf-8", errors="replace")[:300]
            raise GeodataIndisponivel(
                f"O provider devolveu {erro.code} para '{cod_imovel}': {corpo}"
                f" (chave usada: {self.chave_mascarada})"
            ) from erro
        except urllib.error.URLError as erro:
            raise GeodataIndisponivel(
                f"Provider inacessivel em {self.base_url}: {erro.reason}"
            ) from erro

    def _pedir_farm(self, cod_imovel: str, state: str) -> bytes:
        codigo = cod_imovel.strip()
        uf = state.strip().upper()
        if not codigo:
            raise ValueError("cod_imovel nao pode ser vazio.")
        if len(uf) != 2:
            raise ValueError("state deve ter duas letras.")

        url = (
            f"{self.base_url.rstrip('/')}{CAMINHO_FARM}?"
            f"{urllib.parse.urlencode({'cod_imovel': codigo, 'state': uf})}"
        )
        pedido = urllib.request.Request(
            url,
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(pedido, timeout=self.timeout_seconds) as resposta:
                return resposta.read()
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                raise CarNaoEncontrado(
                    f"Imovel '{codigo}' nao encontrado em {uf} na base consultada."
                ) from erro
            corpo = erro.read().decode("utf-8", errors="replace")[:300]
            raise GeodataIndisponivel(
                f"O provider devolveu {erro.code} para '{codigo}': {corpo}"
                f" (chave usada: {self.chave_mascarada})"
            ) from erro
        except urllib.error.URLError as erro:
            raise GeodataIndisponivel(
                f"Provider inacessivel em {self.base_url}: {erro.reason}"
            ) from erro

    def _pedir_timeline(
        self,
        *,
        cod_imovel: str,
        state: str,
        layer: str,
        year_from: int | None,
        year_to: int | None,
    ) -> bytes:
        codigo = cod_imovel.strip()
        uf = state.strip().upper()
        camada = layer.strip().upper()
        if not codigo:
            raise ValueError("cod_imovel nao pode ser vazio.")
        if len(uf) != 2:
            raise ValueError("state deve ter duas letras.")
        if not camada:
            raise ValueError("layer nao pode ser vazia.")

        parametros: dict[str, str | int] = {"cod_imovel": codigo, "state": uf, "layer": camada}
        if year_from is not None:
            parametros["year_from"] = year_from
        if year_to is not None:
            parametros["year_to"] = year_to
        url = (
            f"{self.base_url.rstrip('/')}/api/v1/sicar/farm/timeline?"
            f"{urllib.parse.urlencode(parametros)}"
        )
        pedido = urllib.request.Request(
            url,
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(pedido, timeout=self.timeout_seconds) as resposta:
                return resposta.read()
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                raise CarNaoEncontrado(
                    f"Imovel '{codigo}' nao encontrado em {uf} na base consultada."
                ) from erro
            corpo = erro.read().decode("utf-8", errors="replace")[:300]
            raise GeodataIndisponivel(
                f"O provider devolveu {erro.code} na timeline territorial '{camada}': {corpo}"
                f" (chave usada: {self.chave_mascarada})"
            ) from erro
        except urllib.error.URLError as erro:
            raise GeodataIndisponivel(
                f"Provider inacessivel em {self.base_url}: {erro.reason}"
            ) from erro


def interpretar_camada(item: Any) -> CarLayer:
    """Uma entrada da lista de camadas, recusando o que nao se sabe ler."""
    if not isinstance(item, dict):
        raise GeodataIndisponivel("Entrada de camada malformada.")
    geometria = item.get("geometry")
    if not isinstance(geometria, dict) or "type" not in geometria:
        raise GeodataIndisponivel(
            f"A camada '{item.get('layer')}' nao traz geometria reconhecivel."
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
    """Traduz a resposta do provider, recusando o que nao se sabe ler.

    Fica fora do cliente para poder ser exercitada sem rede, e para que trocar o
    transporte nao exija reescrever a interpretacao.
    """
    texto = bruto.decode("utf-8")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise GeodataIndisponivel("O provider nao devolveu JSON.") from erro

    poligono = dados.get("polygon")
    layer = str(dados.get("layer", ""))
    attributes = dict(dados.get("properties") or {})
    propriedade = dados.get("property")
    if isinstance(propriedade, dict):
        poligono = propriedade.get("polygon")
        layer = str(propriedade.get("layer", layer))
        attributes = dict(propriedade.get("properties") or attributes)

    if not isinstance(poligono, dict) or "type" not in poligono:
        raise GeodataIndisponivel("A resposta nao traz geometria reconhecivel no campo 'polygon'.")

    # Serializacao canonica: o mesmo conteudo produz sempre os mesmos bytes, e e
    # sobre eles que o digest da geometria e calculado.
    payload = json.dumps(poligono, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    return CarProperty(
        cod_imovel=str(dados.get("cod_imovel", "")),
        state=str(dados.get("state", "")).upper(),
        layer=layer,
        polygon_payload=payload,
        polygon_digest=digest_de(payload),
        response_digest=digest_de(texto),
        attributes=attributes,
    )


def interpretar_restricoes_espaciais(bruto: bytes) -> SpatialRestrictionAssessment:
    """Traduz a resposta espacial do provider em tipos do Titan."""
    texto = bruto.decode("utf-8")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise GeodataIndisponivel("O provider nao devolveu JSON.") from erro

    dataset = dados.get("dataset")
    if not isinstance(dataset, dict):
        raise GeodataIndisponivel("A resposta espacial nao traz metadados do dataset.")
    source = dataset.get("source")
    layer = dataset.get("layer")
    version_ids = dataset.get("version_ids") or []
    if not isinstance(source, str) or not source:
        raise GeodataIndisponivel("A resposta espacial nao informa a fonte.")
    if not isinstance(layer, str) or not layer:
        raise GeodataIndisponivel("A resposta espacial nao informa a camada.")
    if not isinstance(version_ids, list):
        raise GeodataIndisponivel("version_ids precisa ser uma lista.")

    operation = dados.get("operation")
    count = dados.get("count")
    features = dados.get("features")
    if not isinstance(operation, str) or not operation:
        raise GeodataIndisponivel("A resposta espacial nao informa a operacao.")
    if not isinstance(count, int):
        raise GeodataIndisponivel("A resposta espacial nao informa a contagem.")
    if not isinstance(features, list):
        raise GeodataIndisponivel("A resposta espacial nao traz features como lista.")

    restrictions: list[SpatialRestriction] = []
    for item in features:
        if not isinstance(item, dict):
            raise GeodataIndisponivel("Feature espacial malformada.")
        geometria = item.get("geometry")
        propriedades = item.get("properties") or {}
        if not isinstance(geometria, dict) or "type" not in geometria:
            raise GeodataIndisponivel("Feature espacial sem geometria reconhecivel.")
        if not isinstance(propriedades, dict):
            raise GeodataIndisponivel("Feature espacial sem propriedades reconheciveis.")
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
            "A resposta espacial informa uma contagem incoerente com as features."
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


def interpretar_timeline_territorial(bruto: bytes) -> TerritorialTimelineAssessment:
    """Traduz a timeline territorial do provider em tipos do Titan."""
    texto = bruto.decode("utf-8")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise GeodataIndisponivel("O provider nao devolveu JSON.") from erro

    source = dados.get("source")
    layer = dados.get("layer")
    years = dados.get("years")
    if not isinstance(source, str) or not source:
        raise GeodataIndisponivel("A timeline territorial nao informa a fonte.")
    if not isinstance(layer, str) or not layer:
        raise GeodataIndisponivel("A timeline territorial nao informa a camada.")
    if not isinstance(years, list):
        raise GeodataIndisponivel("A timeline territorial nao traz anos como lista.")

    parsed_years: list[TerritorialTimelineYear] = []
    for item in years:
        if not isinstance(item, dict):
            raise GeodataIndisponivel("Ano da timeline territorial malformado.")
        year = item.get("year")
        feature_count = item.get("feature_count")
        version_ids = item.get("version_ids") or []
        if year is not None and not isinstance(year, int):
            raise GeodataIndisponivel("year precisa ser inteiro ou nulo.")
        if not isinstance(feature_count, int):
            raise GeodataIndisponivel("feature_count precisa ser inteiro.")
        if not isinstance(version_ids, list):
            raise GeodataIndisponivel("version_ids precisa ser lista.")
        overlap_area = item.get("overlap_area_hectares")
        source_area = item.get("source_area_hectares")
        parsed_years.append(
            TerritorialTimelineYear(
                year=year,
                feature_count=feature_count,
                overlap_area_hectares=(
                    float(overlap_area) if isinstance(overlap_area, int | float) else None
                ),
                source_area_hectares=(
                    float(source_area) if isinstance(source_area, int | float) else None
                ),
                version_ids=tuple(str(version_id) for version_id in version_ids),
            )
        )

    property_area = dados.get("property_area_hectares")
    year_from = dados.get("year_from")
    year_to = dados.get("year_to")
    if year_from is not None and not isinstance(year_from, int):
        raise GeodataIndisponivel("year_from precisa ser inteiro ou nulo.")
    if year_to is not None and not isinstance(year_to, int):
        raise GeodataIndisponivel("year_to precisa ser inteiro ou nulo.")

    return TerritorialTimelineAssessment(
        source=source,
        layer=layer,
        property_area_hectares=(
            float(property_area) if isinstance(property_area, int | float) else None
        ),
        year_from=year_from,
        year_to=year_to,
        years=tuple(parsed_years),
        response_digest=digest_de(texto),
    )


def _instante(valor: Any) -> datetime | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        instante = valor
    elif isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            return None
        texto = texto.replace("Z", "+00:00")
        try:
            instante = datetime.fromisoformat(texto)
        except ValueError:
            return None
    else:
        return None
    if instante.tzinfo is None:
        return instante.replace(tzinfo=UTC)
    return instante.astimezone(UTC)
