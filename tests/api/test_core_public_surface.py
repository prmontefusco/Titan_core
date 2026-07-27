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
    # Core - governanca auditavel de regras (ADR-0043).
    ("/v1/rule-governance/rule-identities", "post"),
    ("/v1/rule-governance/rule-identities/{rule_identity_id}/versions", "post"),
    ("/v1/rule-governance/rule-identities/{rule_identity_id}/adoptions", "post"),
    ("/v1/rule-governance/rule-identities/{rule_identity_id}/adoptions/replace", "post"),
    ("/v1/rule-governance/rule-identities/{rule_identity_id}/timeline", "get"),
    # Vertical Livestock — API mínima do fluxo aprovado (Passos 10.4a e 10.4b).
    ("/v1/livestock/animals", "post"),
    ("/v1/livestock/medications", "post"),
    ("/v1/livestock/medication-batches", "post"),
    ("/v1/livestock/prescriptions", "post"),
    ("/v1/livestock/sanitary-campaigns", "post"),
    ("/v1/livestock/treatments", "post"),
    ("/v1/livestock/treatments/{application_id}/corrections", "post"),
    ("/v1/livestock/animals/{animal_id}/eligibility", "post"),
    ("/v1/livestock/animals/{animal_id}/eligibility/market-matrix", "post"),
    # Elegibilidade de lote (rule-carencia-lote): bloqueia o lote inteiro se
    # qualquer animal membro estiver em carência. Sem dossiê -- o template hoje
    # só monta documento para sujeito do tipo animal.
    ("/v1/livestock/lots/{lot_id}/eligibility", "post"),
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
    ("/v1/livestock/prescriptions/{prescription_id}", "get"),
    ("/v1/livestock/sanitary-campaigns", "get"),
    ("/v1/livestock/sanitary-campaigns/{campaign_id}", "get"),
    ("/v1/livestock/animals/{animal_id}/sanitary-requirements/{campaign_code}", "get"),
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
    # Contraparte externa (ADR-0042). E cadastro local da Organization, nao
    # referencia direta para outro tenant.
    ("/v1/livestock/external-counterparties", "get"),
    ("/v1/livestock/external-counterparties", "post"),
    (
        "/v1/livestock/external-counterparties/{counterparty_id}/establishment-qualifications",
        "post",
    ),
    ("/v1/livestock/animals/{animal_id}/received-transfer-artifacts", "get"),
    ("/v1/livestock/animals/{animal_id}/received-transfer-artifacts", "post"),
    ("/v1/livestock/animals/{animal_id}/imported-facts", "get"),
    ("/v1/livestock/animals/{animal_id}/imported-facts", "post"),
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
    # Geometria da propriedade (Passo 17.1, ADR-0026). Leitura e escrita têm
    # permissão própria: o polígono revela onde a operação fica, e ler o cadastro
    # da propriedade não implica ler o limite dela.
    ("/v1/livestock/properties/{property_id}/geometry", "post"),
    ("/v1/livestock/properties/{property_id}/geometry", "get"),
    ("/v1/livestock/properties/{property_id}/geometry/history", "get"),
    # As camadas do imovel: perimetro, reserva legal, APP, hidrografia. Camadas
    # territoriais (embargo, terra indigena, desmatamento) NAO vivem aqui.
    ("/v1/livestock/properties/{property_id}/geometry/layers", "get"),
    # Importação do CAR (Passo 17.2). A prévia consulta e não grava: serve para
    # pré-preencher o cadastro, e o que o operador confirmar entra como
    # declaração dele. A importação grava, com proveniência SICAR_CAR.
    ("/v1/livestock/properties/car-preview", "get"),
    ("/v1/livestock/properties/{property_id}/geometry/import-car", "post"),
    # Importação de asserções de qualificação de estabelecimento (Passo 17.3a,
    # ADR-0045). SourceArtifact + Assertion bitemporal: a mesma source_version
    # importada 2x é idempotente; ausência em snapshot completo produz UNKNOWN,
    # nunca NOT_QUALIFIED diretamente.
    ("/v1/livestock/establishments/qualification-assertions/import", "post"),
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


def test_nenhuma_rota_de_governanca_de_regras_permite_edicao_destrutiva() -> None:
    proibidos = {
        (caminho, metodo)
        for caminho, metodo in _operacoes()
        if caminho.startswith("/v1/rule-governance/") and metodo in {"put", "patch", "delete"}
    }

    assert not proibidos, f"Rotas destrutivas na governanca de regras: {proibidos}"


def test_toda_rota_protegida_declara_autenticacao_e_negacoes() -> None:
    """Contrato que nao publica negacao faz o integrador descobrir por tentativa."""
    esquema = _esquema()

    for caminho, operacoes in esquema["paths"].items():
        if not (caminho.startswith("/v1/livestock/") or caminho.startswith("/v1/rule-governance/")):
            continue
        for metodo, operacao in operacoes.items():
            rotulo = f"{metodo.upper()} {caminho}"
            assert operacao.get("security"), f"{rotulo} nao declara autenticacao."
            respostas = operacao["responses"]
            assert "401" in respostas, f"{rotulo} nao declara 401."
            assert "403" in respostas, f"{rotulo} nao declara 403."
