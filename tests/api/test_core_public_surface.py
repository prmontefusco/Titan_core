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
    # Vertical Livestock — API mínima do fluxo aprovado (Passos 10.4a e 10.4b).
    # A lista é fechada por decisão: `POST /v1/livestock/prescriptions` NÃO entra,
    # porque `prescription_id` é opcional em TreatmentApplication e nenhuma regra
    # do cenário aprovado depende de prescrição. Ver nota de rumo NR-4.
    ("/v1/livestock/animals", "post"),
    ("/v1/livestock/medications", "post"),
    ("/v1/livestock/medication-batches", "post"),
    ("/v1/livestock/treatments", "post"),
    ("/v1/livestock/treatments/{application_id}/corrections", "post"),
    ("/v1/livestock/animals/{animal_id}/eligibility", "post"),
    ("/v1/livestock/animals/{animal_id}/timeline", "get"),
    ("/v1/livestock/dossiers/{dossier_id}", "get"),
    # Leitura acrescentada pelo Marco 12: sem listagem, nenhuma interface funciona.
    ("/v1/livestock/animals", "get"),
    ("/v1/livestock/animals/{animal_id}", "get"),
    ("/v1/livestock/properties", "get"),
    ("/v1/livestock/properties/{property_id}", "get"),
    ("/v1/livestock/medications", "get"),
    ("/v1/livestock/medications/{medication_id}", "get"),
    ("/v1/livestock/medication-batches", "get"),
    ("/v1/livestock/medication-batches/{batch_id}", "get"),
    ("/v1/livestock/treatments", "get"),
    ("/v1/livestock/treatments/{application_id}", "get"),
    ("/v1/livestock/lots", "get"),
    ("/v1/livestock/lots/{lot_id}", "get"),
    ("/v1/livestock/lots/{lot_id}/members", "get"),
    ("/v1/livestock/veterinarians", "get"),
    ("/v1/livestock/veterinarians/{veterinarian_id}", "get"),
    ("/v1/livestock/movements", "get"),
    ("/v1/livestock/movements/{movement_id}", "get"),
    ("/v1/livestock/dossiers", "get"),
    # Escrita das entidades que o Marco 10 deixou fora da API.
    ("/v1/livestock/properties", "post"),
    ("/v1/livestock/lots", "post"),
    ("/v1/livestock/lots/{lot_id}/members", "post"),
    ("/v1/livestock/lots/{lot_id}/removals", "post"),
    ("/v1/livestock/veterinarians", "post"),
    ("/v1/livestock/veterinarians/{veterinarian_id}/verification", "post"),
    ("/v1/livestock/movements", "post"),
    # Saída do rebanho (Passo 13.1). É POST, e não DELETE: o animal não é apagado,
    # ganha um fato terminal que o tira do rebanho ativo sem tirá-lo da história.
    ("/v1/livestock/animals/{animal_id}/exit", "post"),
    # Genealogia (Passo 13.2). A maternidade é uma rota só porque é um ato só,
    # ainda que grave dois vínculos: o genético, que define a linhagem, e o
    # gestacional, que responde pela receptora na transferência de embrião.
    ("/v1/livestock/animals/{animal_id}/maternity", "post"),
    ("/v1/livestock/animals/{animal_id}/paternity", "post"),
    ("/v1/livestock/animals/{animal_id}/ancestry", "get"),
    ("/v1/livestock/animals/{animal_id}/descendants", "get"),
    # Histórico reprodutivo é rota própria, e não filtro da descendência: uma
    # receptora gestou bezerros que não descendem dela.
    ("/v1/livestock/animals/{animal_id}/reproduction", "get"),
    # Reprodução (Passo 13.3, ADR-0040). São duas rotas porque são dois fatos de
    # natureza distinta: o parto produz indivíduos rastreáveis, a perda gestacional
    # encerra a gestação sem produzir nenhum.
    ("/v1/livestock/reproductive-events/parturitions", "post"),
    ("/v1/livestock/reproductive-events/pregnancy-losses", "post"),
    ("/v1/livestock/animals/{animal_id}/reproductive-events", "get"),
    ("/v1/livestock/animals/{animal_id}/origin", "get"),
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


def test_nenhuma_rota_da_vertical_permite_edicao_destrutiva() -> None:
    """Append-only não é convenção: é ausência de rota que sobrescreva ou apague.

    Expor um PUT ou DELETE aqui ofereceria no HTTP uma operação que o domínio
    recusa — e a recusa é o ponto do Marco 9.
    """
    proibidos = {
        (caminho, metodo)
        for caminho, metodo in _operacoes()
        if caminho.startswith("/v1/livestock/") and metodo in {"put", "patch", "delete"}
    }

    assert not proibidos, f"Rotas destrutivas na vertical: {proibidos}"


def test_toda_rota_da_vertical_declara_autenticacao_e_negacoes() -> None:
    """Contrato que não publica a negação faz o integrador descobrir por tentativa.

    A segurança precisa constar do esquema também porque é ela que faz o Swagger
    anexar o token — sem isso, o botão Authorize não tem efeito na requisição.
    """
    esquema = _esquema()

    for caminho, operacoes in esquema["paths"].items():
        if not caminho.startswith("/v1/livestock/"):
            continue
        for metodo, operacao in operacoes.items():
            rotulo = f"{metodo.upper()} {caminho}"
            assert operacao.get("security"), f"{rotulo} não declara autenticação."
            respostas = operacao["responses"]
            assert "401" in respostas, f"{rotulo} não declara 401."
            assert "403" in respostas, f"{rotulo} não declara 403."
