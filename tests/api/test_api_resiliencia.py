"""Dívida do Passo 10.4, paga: rollback, 500 sanitizado e configuração.

Os três tinham código escrito e nenhum teste. Código sem teste não é garantia —
é intenção, e intenção não sobrevive à próxima refatoração.
"""

import os
from collections.abc import Generator
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import Connection, create_engine, text

from apps.api.configuration import (
    VARIAVEIS_OBRIGATORIAS,
    ConfiguracaoIncompleta,
    exigir_configuracao,
    variaveis_ausentes,
)
from apps.api.main import app
from apps.api.problem import unexpected_error_handler

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")


class TestConfiguracaoNoArranque:
    """A API recusa subir sem configuração, em vez de errar na primeira requisição."""

    def test_declara_o_que_falta_nomeando_cada_variavel(self) -> None:
        ausentes = variaveis_ausentes({})

        assert set(ausentes) == set(VARIAVEIS_OBRIGATORIAS)

    def test_variavel_em_branco_conta_como_ausente(self) -> None:
        """Definir vazio é o engano mais comum, e não pode passar por definido."""
        ambiente = dict.fromkeys(VARIAVEIS_OBRIGATORIAS, "   ")

        assert set(variaveis_ausentes(ambiente)) == set(VARIAVEIS_OBRIGATORIAS)

    def test_a_mensagem_diz_qual_variavel_falta_e_para_que_serve(self) -> None:
        ambiente = dict.fromkeys(VARIAVEIS_OBRIGATORIAS, "valor")
        del ambiente["TITAN_OIDC_AUDIENCE"]

        with pytest.raises(ConfiguracaoIncompleta) as erro:
            exigir_configuracao(ambiente)

        mensagem = str(erro.value)
        assert "TITAN_OIDC_AUDIENCE" in mensagem
        assert "audience" in mensagem
        # Só o que falta é citado: listar o que já está definido vira ruído.
        assert "TITAN_DATABASE_URL" not in mensagem

    def test_configuracao_completa_deixa_subir(self) -> None:
        exigir_configuracao(dict.fromkeys(VARIAVEIS_OBRIGATORIAS, "valor"))

    def test_o_arranque_falha_quando_falta_configuracao(self, monkeypatch: MonkeyPatch) -> None:
        """O processo não sobe: é o que troca um erro tardio por um imediato."""
        for nome in VARIAVEIS_OBRIGATORIAS:
            monkeypatch.delenv(nome, raising=False)

        with pytest.raises(ConfiguracaoIncompleta), TestClient(app):
            pass


class TestErroInesperadoSanitizado:
    """Vazar exceção em resposta de API é entregar o mapa da casa a quem bateu."""

    def test_o_corpo_nao_revela_nada_do_que_aconteceu_por_dentro(self) -> None:
        interna = "SELECT segredo FROM tabela_interna -- rastro que não pode vazar"
        aplicacao = FastAPI()
        aplicacao.add_exception_handler(Exception, unexpected_error_handler)

        @aplicacao.get("/quebra")
        def quebra() -> None:
            raise RuntimeError(interna)

        cliente = TestClient(aplicacao, raise_server_exceptions=False)
        resposta = cliente.get("/quebra")

        assert resposta.status_code == 500
        corpo = resposta.json()
        assert corpo["reason_code"] == "ERRO_INTERNO"
        assert interna not in resposta.text
        assert "RuntimeError" not in resposta.text
        assert "Traceback" not in resposta.text
        assert resposta.headers["content-type"].startswith("application/problem+json")


@pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)
class TestTransacaoPorRequisicao:
    """Ou tudo é gravado, ou nada: registro sem a prova correspondente é pior que nada."""

    def test_falha_no_meio_da_requisicao_desfaz_o_que_ja_havia_sido_gravado(self) -> None:
        from apps.api.livestock_dependencies import request_connection

        assert DATABASE_URL is not None
        marcador = "titan-teste-rollback"

        # O gerador é a própria dependência: dirigi-lo à mão exercita o
        # `with connection.begin()` real, que é onde o rollback vive.
        gerador = cast("Generator[Connection, None, None]", request_connection())
        connection = next(gerador)
        # A organização é dona de si mesma (ck_organizations_self_owned).
        connection.execute(
            text(
                "INSERT INTO core_identity.organizations "
                "(organization_id, record_owner_organization_id) "
                "SELECT novo, novo FROM (SELECT gen_random_uuid() AS novo) AS gerado"
            )
        )
        antes = connection.execute(
            text("SELECT count(*) FROM core_identity.organizations")
        ).scalar_one()

        # A requisição falha depois de já ter escrito.
        with pytest.raises(RuntimeError):
            gerador.throw(RuntimeError(marcador))

        # Uma conexão nova não enxerga a escrita: a transação foi desfeita.
        with create_engine(DATABASE_URL).connect() as nova:
            depois = nova.execute(
                text("SELECT count(*) FROM core_identity.organizations")
            ).scalar_one()

        assert depois == antes - 1, "A escrita da requisição que falhou não pode persistir."
