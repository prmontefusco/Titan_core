"""Superfície HTTP pública do Core no fechamento do Marco 7 (Passo 7.10).

A API de domínio pertence ao Passo 10.4 — "endpoints estritamente necessários
para operar o cenário já implementado". Este teste fixa o que o Core expõe hoje
para que endpoint de domínio não apareça por acidente antes daquele passo: um
endpoint novo aqui é uma decisão, não um efeito colateral.
"""

from typing import Any

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)

# Somente superfície técnica e verificação externa. Nada de domínio.
SUPERFICIE_ESPERADA = {
    ("/health", "get"),
    ("/technical/authentication", "get"),
    ("/v1/verification/bundles", "post"),
}


def _esquema() -> dict[str, Any]:
    esquema: dict[str, Any] = client.get("/openapi.json").json()
    return esquema


def _operacoes() -> set[tuple[str, str]]:
    esquema = _esquema()
    return {
        (caminho, metodo) for caminho, operacoes in esquema["paths"].items() for metodo in operacoes
    }


def test_superficie_publica_do_core_esta_congelada() -> None:
    assert _operacoes() == SUPERFICIE_ESPERADA


class TestContratoPublicado:
    """O contrato precisa estar na documentação que o integrador consulta.

    Estas três lacunas passaram despercebidas pelo portão automático e só
    apareceram na validação manual: os testes cobriam o **comportamento** do
    endpoint, e ninguém verificava o que o OpenAPI **publica** sobre ele.
    """

    def test_aviso_de_material_sensivel_consta_da_documentacao_publica(self) -> None:
        """Requisito textual da ADR-0039, que exige o aviso na documentação pública."""
        descricao = _esquema()["paths"]["/v1/verification/bundles"]["post"]["description"]

        assert "verificador local" in descricao
        assert "sensíveis" in descricao

    def test_schema_do_corpo_e_publicado_e_resolvivel(self) -> None:
        """A ADR-0010 exigia schemas públicos; o handler lê o corpo cru e o
        FastAPI não os infere sozinho."""
        esquema = _esquema()
        operacao = esquema["paths"]["/v1/verification/bundles"]["post"]
        referencia = operacao["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        nome = referencia.rsplit("/", 1)[-1]
        componentes = esquema["components"]["schemas"]

        assert nome in componentes, "O $ref do corpo aponta para componente inexistente."
        # A referência aninhada também precisa resolver, senão o Swagger quebra.
        aninhado = componentes[nome]["properties"]["trust_anchors"]["items"]["$ref"]
        assert aninhado.rsplit("/", 1)[-1] in componentes

    def test_rota_protegida_declara_a_negacao(self) -> None:
        respostas = _esquema()["paths"]["/technical/authentication"]["get"]["responses"]

        assert "401" in respostas


def test_swagger_descreve_a_superficie_para_validacao_manual() -> None:
    """O plano valida o Core por testes, API e Swagger: a UI precisa responder."""
    resposta = client.get("/docs")

    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]


def test_endpoints_de_dominio_ainda_nao_existem() -> None:
    """Guarda explícita do portão do Marco 7.

    Se um endpoint de domínio surgir antes do Passo 10.4, este teste falha e
    obriga a decisão a passar pelo plano em vez de entrar despercebida.
    """
    caminhos = {caminho for caminho, _ in _operacoes()}
    proibidos = (
        "/v1/organizations",
        "/v1/events",
        "/v1/evidences",
        "/v1/relations",
        "/v1/policies",
        "/v1/rules",
        "/v1/evaluations",
        "/v1/decisions",
        "/v1/nonconformities",
        "/v1/recalls",
        "/v1/dossiers",
        "/v1/synchronization",
    )
    vazados = [prefixo for prefixo in proibidos if any(c.startswith(prefixo) for c in caminhos)]

    assert not vazados, "Endpoints de domínio expostos antes do Passo 10.4: " + ", ".join(vazados)
