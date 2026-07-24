"""Superfície HTTP pública, congelada deliberadamente (Passos 7.10 e 10.4).

Um endpoint novo aqui é uma decisão, não um efeito colateral: quem acrescentar
rota sem atualizar esta lista quebra o portão.

O Passo 10.4a abriu a primeira rota de domínio da vertical — `POST
/v1/livestock/animals`, endpoint-prova da fundação HTTP. As rotas de domínio do
**Core** seguem fechadas: a API mínima do Marco 10 é da vertical, e expor
`/v1/decisions` ou `/v1/evidences` seria decisão à parte, que ninguém tomou.
"""

from typing import Any

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)

SUPERFICIE_ESPERADA = {
    # Técnico e verificação externa.
    ("/health", "get"),
    ("/technical/authentication", "get"),
    ("/v1/verification/bundles", "post"),
    # Vertical Livestock — Passo 10.4a, endpoint-prova da fundação HTTP.
    ("/v1/livestock/animals", "post"),
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


def test_endpoints_de_dominio_do_core_continuam_fechados() -> None:
    """O Marco 10 expõe a vertical, não o Core.

    Publicar `/v1/decisions` ou `/v1/evidences` daria a terceiros acesso direto às
    primitivas do Core sem passar por caso de uso algum. Se um deles surgir, este
    teste falha e obriga a decisão a passar pelo plano.
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

    assert not vazados, "Endpoints de domínio do Core expostos: " + ", ".join(vazados)
