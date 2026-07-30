"""Interpretação da resposta do provider de CAR (Passo 17.2, ADR-0026).

A interpretação vive fora do transporte justamente para ser exercitada sem rede.
O que estes testes protegem: o material recebido é identificado por digest, a
data do CAR não é confundida com a da importação, e nada do que vem é lido como
conformidade.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime
from email.message import Message
from io import BytesIO
from typing import cast

import pytest

from packages.livestock_domain.geometry import digest_de
from packages.livestock_infrastructure.geodata import (
    GeodataCarClient,
    GeodataIndisponivel,
    GeodataNaoConfigurado,
    interpretar_resposta,
    interpretar_restricoes_espaciais,
)

# Uma resposta como a que o Titan_geodata devolve de verdade.
RESPOSTA: dict[str, object] = {
    "cod_imovel": "MS-5007554-1EF4AA06D08041829247C61FE4412C4F",
    "layer": "AREA_IMOVEL",
    "state": "MS",
    "polygon": {
        "type": "MultiPolygon",
        "coordinates": [
            [
                [
                    [-52.921492357, -21.217839008],
                    [-52.920605849, -21.217944691],
                    [-52.919416869, -21.217970347],
                    [-52.921492357, -21.217839008],
                ]
            ]
        ],
    },
    "properties": {
        "nom_tema": "Area do Imovel",
        "num_area": 1363.93,
        "mod_fiscal": 38.97,
        "ind_status": "AT",
        "ind_tipo": "IRU",
        "des_condic": "Aguardando analise",
        "municipio": "Santa Rita do Pardo",
        "cod_estado": "MS",
        "dat_criaca": "2018-07-05T00:00:00",
        "dat_atuali": "2023-07-06T00:00:00",
    },
}

RESPOSTA_IBAMA: dict[str, object] = {
    "operation": "intersects",
    "dataset": {
        "source": "IBAMA",
        "layer": "IBAMA_EMBARGOS",
        "version_ids": ["ibama_v1"],
    },
    "count": 1,
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [
                        [
                            [-54.5, -21.5],
                            [-54.5, -20.5],
                            [-53.5, -20.5],
                            [-53.5, -21.5],
                            [-54.5, -21.5],
                        ]
                    ]
                ],
            },
            "properties": {
                "id": 10,
                "version_id": "ibama_v1",
                "num_tad": "9999/2026",
                "uf_sigla": "MS",
                "municipio": "Dourados",
                "nom_embarg": "Fazenda Exemplo",
                "area_ha": 150.5,
            },
        }
    ],
}


def _bruto(dados: Mapping[str, object] | None = None) -> bytes:
    return json.dumps(dados if dados is not None else RESPOSTA).encode("utf-8")


def _bruto_ibama(dados: Mapping[str, object] | None = None) -> bytes:
    return json.dumps(dados if dados is not None else RESPOSTA_IBAMA).encode("utf-8")


def test_a_resposta_e_interpretada_sem_perder_nada() -> None:
    imovel = interpretar_resposta(_bruto())

    assert imovel.cod_imovel == RESPOSTA["cod_imovel"]
    assert imovel.state == "MS"
    assert imovel.layer == "AREA_IMOVEL"
    assert imovel.attributes["mod_fiscal"] == 38.97


def test_os_dois_digests_respondem_perguntas_diferentes() -> None:
    """Um diz qual é o limite; o outro, qual foi o material recebido."""
    imovel = interpretar_resposta(_bruto())

    assert imovel.polygon_digest == digest_de(imovel.polygon_payload)
    assert imovel.response_digest != imovel.polygon_digest
    assert len(imovel.response_digest) == 64


def test_o_poligono_e_serializado_de_forma_deterministica() -> None:
    """Mesmo conteúdo, mesmos bytes — senão o digest deixaria de identificar."""
    primeiro = interpretar_resposta(_bruto())
    embaralhado: dict[str, object] = dict(RESPOSTA)
    poligono = RESPOSTA["polygon"]
    assert isinstance(poligono, dict)
    embaralhado["polygon"] = dict(reversed(list(poligono.items())))

    assert interpretar_resposta(_bruto(embaralhado)).polygon_digest == primeiro.polygon_digest


def test_a_data_do_car_vira_captured_at_em_utc() -> None:
    """`dat_atuali` é quando o CAR mudou, não quando foi importado."""
    imovel = interpretar_resposta(_bruto())

    assert imovel.captured_at == datetime(2023, 7, 6, tzinfo=UTC)


def test_os_atributos_uteis_ao_cadastro_sao_expostos() -> None:
    imovel = interpretar_resposta(_bruto())

    assert imovel.municipality == "Santa Rita do Pardo"
    assert imovel.state_code == "MS"
    assert imovel.area_hectares == 1363.93


def test_a_condicao_do_cadastro_e_exposta_sem_ser_interpretada() -> None:
    """Diz onde o cadastro está na fila do SICAR, e não se a fazenda é regular."""
    imovel = interpretar_resposta(_bruto())

    assert imovel.registry_condition == "Aguardando analise"


def test_data_ausente_nao_inventa_captured_at() -> None:
    sem_data: dict[str, object] = dict(RESPOSTA)
    sem_data["properties"] = {"municipio": "Ponta Pora"}

    assert interpretar_resposta(_bruto(sem_data)).captured_at is None


def test_data_malformada_nao_derruba_a_importacao() -> None:
    """Uma data que não se sabe ler vira ausência declarada, e não exceção."""
    torta: dict[str, object] = dict(RESPOSTA)
    torta["properties"] = {"dat_atuali": "ontem de manha"}

    assert interpretar_resposta(_bruto(torta)).captured_at is None


def test_resposta_sem_geometria_e_recusada() -> None:
    sem_poligono: dict[str, object] = {"cod_imovel": "X", "state": "MS", "properties": {}}

    with pytest.raises(GeodataIndisponivel, match="geometria"):
        interpretar_resposta(_bruto(sem_poligono))


def test_resposta_que_nao_e_json_e_recusada() -> None:
    with pytest.raises(GeodataIndisponivel, match="JSON"):
        interpretar_resposta(b"<html>erro do proxy</html>")


def test_restricoes_espaciais_sao_interpretadas_sem_julgamento() -> None:
    assessment = interpretar_restricoes_espaciais(_bruto_ibama())

    assert assessment.source == "IBAMA"
    assert assessment.layer == "IBAMA_EMBARGOS"
    assert assessment.operation == "intersects"
    assert assessment.version_ids == ("ibama_v1",)
    assert assessment.restriction_count == 1
    assert assessment.restrictions[0].attributes["nom_embarg"] == "Fazenda Exemplo"
    assert assessment.restrictions[0].polygon_digest == digest_de(
        assessment.restrictions[0].polygon_payload
    )


def test_resposta_espacial_com_contagem_incoerente_e_recusada() -> None:
    torta = dict(RESPOSTA_IBAMA)
    torta["count"] = 2

    with pytest.raises(GeodataIndisponivel, match="contagem"):
        interpretar_restricoes_espaciais(_bruto_ibama(torta))


def test_cliente_sem_configuracao_e_recusado_na_construcao() -> None:
    """Falhar ao construir evita descobrir a falta de chave na primeira consulta."""
    with pytest.raises(GeodataNaoConfigurado):
        GeodataCarClient(base_url="", api_key="")

    with pytest.raises(GeodataNaoConfigurado):
        GeodataCarClient(base_url="http://x", api_key="   ")


@pytest.mark.parametrize(("codigo", "uf"), [("", "MS"), ("MS-1", "M"), ("MS-1", "")])
def test_parametros_malformados_sao_recusados(codigo: str, uf: str) -> None:
    cliente = GeodataCarClient(base_url="http://provider.invalido", api_key="chave")

    with pytest.raises(ValueError):
        cliente.fetch(codigo, uf)


def test_poligono_malformado_e_recusado_antes_da_rede() -> None:
    cliente = GeodataCarClient(base_url="http://provider.invalido", api_key="chave")

    with pytest.raises(ValueError, match="Polygon ou MultiPolygon"):
        cliente.fetch_ibama_overlaps(
            polygon_payload=json.dumps({"type": "Point", "coordinates": [-53.9, -21.9]})
        )


def test_cliente_envia_post_para_o_endpoint_espacial(monkeypatch: pytest.MonkeyPatch) -> None:
    pedido_capturado: dict[str, object] = {}

    class _Resposta:
        def __enter__(self) -> "_Resposta":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return _bruto_ibama()

    def _urlopen(request: object, timeout: int) -> _Resposta:
        pedido_capturado["request"] = request
        pedido_capturado["timeout"] = timeout
        return _Resposta()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    cliente = GeodataCarClient(base_url="http://provider.invalido", api_key="chave")

    assessment = cliente.fetch_ibama_overlaps(
        polygon_payload=json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [[-54.0, -22.0], [-54.0, -21.0], [-53.0, -21.0], [-53.0, -22.0], [-54.0, -22.0]]
                ],
            }
        )
    )

    request = pedido_capturado["request"]
    assert isinstance(request, urllib.request.Request)
    assert request.full_url == "http://provider.invalido/api/v1/ibama/spatial/polygon"
    assert request.get_method() == "POST"
    assert request.headers["X-api-key"] == "chave"
    assert pedido_capturado["timeout"] == cliente.timeout_seconds
    body = json.loads(cast(bytes, request.data).decode("utf-8"))
    assert body["srid"] == 4326
    assert body["geometry"]["type"] == "Polygon"
    assert assessment.restriction_count == 1


def test_erro_http_da_consulta_espacial_vira_indisponibilidade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _urlopen(_: object, timeout: int) -> object:
        raise urllib.error.HTTPError(
            url="http://provider.invalido/api/v1/ibama/spatial/polygon",
            code=503,
            msg="Service Unavailable",
            hdrs=Message(),
            fp=BytesIO(b'{"detail":"temporariamente fora"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    cliente = GeodataCarClient(base_url="http://provider.invalido", api_key="chave")

    with pytest.raises(GeodataIndisponivel, match="consulta espacial do IBAMA"):
        cliente.fetch_ibama_overlaps(
            polygon_payload=json.dumps(
                {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-54.0, -22.0],
                            [-54.0, -21.0],
                            [-53.0, -21.0],
                            [-53.0, -22.0],
                            [-54.0, -22.0],
                        ]
                    ],
                }
            )
        )
