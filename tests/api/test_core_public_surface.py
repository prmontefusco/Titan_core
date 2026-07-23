"""Superfície HTTP pública do Core no fechamento do Marco 7 (Passo 7.10).

A API de domínio pertence ao Passo 10.4 — "endpoints estritamente necessários
para operar o cenário já implementado". Este teste fixa o que o Core expõe hoje
para que endpoint de domínio não apareça por acidente antes daquele passo: um
endpoint novo aqui é uma decisão, não um efeito colateral.
"""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)

# Somente superfície técnica e verificação externa. Nada de domínio.
SUPERFICIE_ESPERADA = {
    ("/health", "get"),
    ("/technical/authentication", "get"),
    ("/v1/verification/bundles", "post"),
}


def _operacoes() -> set[tuple[str, str]]:
    esquema = client.get("/openapi.json").json()
    return {
        (caminho, metodo) for caminho, operacoes in esquema["paths"].items() for metodo in operacoes
    }


def test_superficie_publica_do_core_esta_congelada() -> None:
    assert _operacoes() == SUPERFICIE_ESPERADA


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
