"""Interpretação da resposta do provider de CAR (Passo 17.2, ADR-0026).

A interpretação vive fora do transporte justamente para ser exercitada sem rede.
O que estes testes protegem: o material recebido é identificado por digest, a
data do CAR não é confundida com a da importação, e nada do que vem é lido como
conformidade.
"""

import json
from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from packages.livestock_domain.geometry import digest_de
from packages.livestock_infrastructure.geodata import (
    GeodataCarClient,
    GeodataIndisponivel,
    GeodataNaoConfigurado,
    interpretar_resposta,
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


def _bruto(dados: Mapping[str, object] | None = None) -> bytes:
    return json.dumps(dados if dados is not None else RESPOSTA).encode("utf-8")


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
