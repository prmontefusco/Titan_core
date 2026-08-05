"""Roteiro de validação manual do Passo 13.2, executável de ponta a ponta.

    python -m uv run --locked python -m apps.validacao
    python -m uv run --locked python -m apps.validacao --pausar

Cria os animais, registra a genealogia, consulta a árvore e exercita cada
negação — imprimindo, a cada passo, o que pediu, o que esperava e o que veio.

**Não substitui o julgamento de quem valida.** O script confere status e forma da
resposta; se o comportamento faz sentido para o negócio é pergunta que continua
sendo humana, e por isso cada passo carrega uma linha dizendo por que existe.

Descobre sozinho a Organization e a propriedade, para que nenhum identificador
precise ser copiado à mão: confundir a operadora com a Organization A já custou
duas rodadas de diagnóstico às cegas na validação do Passo 13.1.
"""

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.runner import (
    AMARELO,
    CINZA,
    FIM,
    NEGRITO,
    Cliente,
    Requisicao,
    Resposta,
    Roteiro,
)

CLIENTE_DE_VALIDACAO = "titan-validacao"

ONTEM = (datetime.now(UTC) - timedelta(days=1)).isoformat()
ANTEONTEM = (datetime.now(UTC) - timedelta(days=2)).isoformat()


def _ambiente(nome: str, padrao: str) -> str:
    return os.environ.get(nome, "").strip() or padrao


@dataclass
class Rebanho:
    """Os identificadores que os passos vão criando uns para os outros."""

    ids: dict[str, str] = field(default_factory=dict)

    def guardar(self, apelido: str) -> object:
        def guardador(resposta: Resposta) -> None:
            self.ids[apelido] = str(resposta["animal_id"])

        return guardador

    def __getitem__(self, apelido: str) -> str:
        return self.ids[apelido]


def _descobrir_organizacao(
    database_url: str,
    *,
    issuer: str | None = None,
    subject: str | None = None,
) -> str:
    """A Organization em que o usuário de demonstração de fato opera.

    Não é a operadora — a operadora é onde a identidade vive, e é justamente
    onde ele **não** opera. Quando o principal é conhecido, responde o vínculo
    mais recente desse usuário; sem isso, cai no atalho histórico do vínculo
    ativo mais recente do banco.
    """
    engine = create_engine(database_url)
    with engine.connect() as conexao:
        if issuer and subject:
            linha = conexao.execute(
                text(
                    "SELECT memberships.organization_id "
                    "FROM core_identity.memberships AS memberships "
                    "JOIN core_identity.external_identities AS external_identities "
                    "  ON external_identities.internal_principal_id = memberships.user_id "
                    "WHERE external_identities.issuer = :issuer "
                    "  AND external_identities.subject = :subject "
                    "  AND memberships.status = 'ATIVA' "
                    "ORDER BY memberships.valid_from DESC LIMIT 1"
                ),
                {"issuer": issuer, "subject": subject},
            ).fetchone()
        else:
            linha = conexao.execute(
                text(
                    "SELECT organization_id FROM core_identity.memberships "
                    "WHERE status = 'ATIVA' ORDER BY valid_from DESC LIMIT 1"
                )
            ).fetchone()
    engine.dispose()
    if linha is None:
        raise SystemExit(
            "Nenhum vínculo ativo no banco. Rode a semeadura antes:\n"
            "  $env:TITAN_SEED_CONFIRM = '1'; python -m uv run --locked python -m apps.seed"
        )
    return str(linha[0])


def _exigir_permissoes_do_passo(cliente: Cliente) -> None:
    """Sonda antes de começar, porque o sintoma engana.

    Os papéis são semeados com as permissões que existiam **naquele momento**. Um
    passo que acrescenta permissão não alcança papel já criado: o operador de uma
    semeadura anterior recebe 403 em toda escrita nova, e o 403 fala de permissão
    quando o que falta é semeadura. Descobrir isso no primeiro passo do roteiro
    custa a leitura de vinte respostas vermelhas.
    """
    inexistente = "00000000-0000-4000-8000-000000000000"
    sondas = [
        cliente.get(f"/v1/livestock/animals/{inexistente}/{rota}")
        for rota in ("ancestry", "origin")
    ]
    sondas.append(cliente.get(f"/v1/livestock/properties/{inexistente}/geometry"))
    if all(sonda.status != 403 for sonda in sondas):
        return
    raise SystemExit(
        f"{AMARELO}O papel desta Organization não tem as permissões deste roteiro.{FIM}\n"
        "Os papéis guardam as permissões que existiam quando foram semeados, e os\n"
        "passos 13.2 e 13.3 acrescentaram quatro. Semeie de novo e reinicie a API\n"
        "com a operadora nova:\n"
        "  $env:TITAN_SEED_CONFIRM = '1'; python -m uv run --locked python -m apps.seed"
    )


def _propriedade(cliente: Cliente) -> str:
    resposta = cliente.get("/v1/livestock/properties?limit=1")
    if resposta.status != 200 or not resposta["items"]:
        raise SystemExit(
            f"Não achei propriedade nesta Organization (status {resposta.status}).\n"
            "Rode a semeadura, ou confira se a API subiu com a configuração certa."
        )
    return str(resposta["items"][0]["property_id"])


def _montar_roteiro(operador: Cliente, auditor: Cliente, propriedade: str) -> Roteiro:
    rebanho = Rebanho()
    roteiro = Roteiro("Passo 13.2 — Genealogia", diario=operador.diario)

    elenco = (
        ("BEZERRO", "MALE"),
        ("DOADORA", "FEMALE"),
        ("RECEPTORA", "FEMALE"),
        ("TOURO-1", "MALE"),
        ("TOURO-2", "MALE"),
        ("TOURO-3", "MALE"),
        ("TOURO-4", "MALE"),
        ("OUTRA-VACA", "FEMALE"),
    )
    for ordem, (apelido, sexo) in enumerate(elenco, start=1):
        roteiro.passo(
            f"1.{ordem}",
            f"Cadastrar {apelido} ({sexo})",
            lambda s=sexo: operador.post(
                "/v1/livestock/animals",
                {"birth_property_id": propriedade, "sex": s, "breed": "Nelore"},
            ),
            201,
            guardar=rebanho.guardar(apelido),
        )

    # -- A maternidade dupla ------------------------------------------------

    roteiro.passo(
        "2.1",
        "Registrar maternidade com transferência de embrião",
        lambda: operador.post(
            f"/v1/livestock/animals/{rebanho['BEZERRO']}/maternity",
            {
                "genetic_mother_id": rebanho["DOADORA"],
                "gestational_mother_id": rebanho["RECEPTORA"],
                "occurred_at": ONTEM,
                "confidence": "DECLARADO",
            },
        ),
        201,
        conferir=lambda r: (
            None
            if {item["role"] for item in r.corpo} == {"MAE_GENETICA", "MAE_GESTACIONAL"}
            else f"papéis vieram {[item['role'] for item in r.corpo]}"
        ),
        porque="Um ato do operador, dois fatos: quem deu o óvulo e quem gestou.",
    )

    roteiro.passo(
        "2.2",
        "A árvore sobe pela doadora",
        lambda: operador.get(f"/v1/livestock/animals/{rebanho['BEZERRO']}/ancestry"),
        200,
        conferir=lambda r: (
            None
            if {ramo["link"]["parent_id"] for ramo in r["parents"]} == {rebanho["DOADORA"]}
            else "a ascendência não é exatamente a doadora"
        ),
        porque="A receptora não pode aparecer: quem gestou não transmitiu genes.",
    )

    roteiro.passo(
        "2.3",
        "A receptora responde pelo histórico reprodutivo",
        lambda: operador.get(f"/v1/livestock/animals/{rebanho['RECEPTORA']}/reproduction"),
        200,
        conferir=lambda r: (
            None
            if [item["offspring_id"] for item in r.corpo] == [rebanho["BEZERRO"]]
            else "o bezerro gestado não apareceu"
        ),
        porque="Ela gestou, e isso é fato dela — ainda que não seja ancestral.",
    )

    roteiro.passo(
        "2.4",
        "A receptora não tem descendência",
        lambda: operador.get(f"/v1/livestock/animals/{rebanho['RECEPTORA']}/descendants"),
        200,
        conferir=lambda r: None if r.corpo == [] else f"veio {r.corpo}",
        porque="2.3 e 2.4 são a mesma vaca em duas perguntas. Colapsá-las é o erro.",
    )

    roteiro.passo(
        "2.5",
        "O parto aparece na linha do tempo da receptora",
        lambda: auditor.get(f"/v1/livestock/animals/{rebanho['RECEPTORA']}/timeline"),
        200,
        conferir=lambda r: (
            None
            if any(
                entrada["entry_type"] == "livestock.parentage_registered"
                for entrada in r["entries"]
            )
            else "o parto não entrou na história dela"
        ),
        porque="A relação é o agregado do evento, e as duas pontas a citam.",
    )

    # -- O touro do lote ----------------------------------------------------

    for indice in (1, 2, 3):
        roteiro.passo(
            f"3.{indice}",
            f"Registrar TOURO-{indice} como pai possível (DECLARADO)",
            lambda i=indice: operador.post(
                f"/v1/livestock/animals/{rebanho['BEZERRO']}/paternity",
                {
                    "father_id": rebanho[f"TOURO-{i}"],
                    "occurred_at": ONTEM,
                    "confidence": "DECLARADO",
                },
            ),
            201,
            porque="Monta natural com vários reprodutores é caso reconhecido.",
        )

    roteiro.passo(
        "3.4",
        "Os três pais possíveis respondem à consulta",
        lambda: operador.get(f"/v1/livestock/animals/{rebanho['BEZERRO']}/ancestry"),
        200,
        conferir=lambda r: (
            None
            if {ramo["link"]["parent_id"] for ramo in r["parents"]}
            == {rebanho["DOADORA"], rebanho["TOURO-1"], rebanho["TOURO-2"], rebanho["TOURO-3"]}
            else "a ascendência não traz a doadora e os três touros"
        ),
        porque="É a pergunta que um campo de texto não responderia.",
    )

    # -- As negações --------------------------------------------------------

    roteiro.passo(
        "4.1",
        "Um quarto pai, agora DOCUMENTADO, é recusado",
        lambda: operador.post(
            f"/v1/livestock/animals/{rebanho['BEZERRO']}/paternity",
            {
                "father_id": rebanho["TOURO-4"],
                "occurred_at": ONTEM,
                "confidence": "DOCUMENTADO",
            },
        ),
        409,
        conferir=lambda r: (
            None if r["reason_code"] == "CONFLITO_DE_DOMINIO" else f"reason_code={r['reason_code']}"
        ),
        porque="Prova ao lado de palpite deixaria de ser prova.",
    )

    roteiro.passo(
        "4.2",
        "Uma segunda mãe genética é recusada",
        lambda: operador.post(
            f"/v1/livestock/animals/{rebanho['BEZERRO']}/maternity",
            {
                "genetic_mother_id": rebanho["OUTRA-VACA"],
                "occurred_at": ONTEM,
                "confidence": "DECLARADO",
            },
        ),
        409,
        porque="Duas mães genéticas é contradição, e não dado incompleto.",
    )

    roteiro.passo(
        "4.3",
        "Um touro como mãe é recusado",
        lambda: operador.post(
            f"/v1/livestock/animals/{rebanho['BEZERRO']}/maternity",
            {
                "genetic_mother_id": rebanho["TOURO-1"],
                "occurred_at": ONTEM,
                "confidence": "DECLARADO",
            },
        ),
        409,
        porque="Nomear alguém como mãe é afirmar que é fêmea.",
    )

    roteiro.passo(
        "4.4",
        "Um animal não é progenitor de si mesmo",
        lambda: operador.post(
            f"/v1/livestock/animals/{rebanho['DOADORA']}/maternity",
            {
                "genetic_mother_id": rebanho["DOADORA"],
                "occurred_at": ONTEM,
                "confidence": "DECLARADO",
            },
        ),
        409,
    )

    roteiro.passo(
        "4.5",
        "O ciclo direto é barrado",
        lambda: operador.post(
            f"/v1/livestock/animals/{rebanho['DOADORA']}/maternity",
            {
                "genetic_mother_id": rebanho["BEZERRO"],
                "occurred_at": ANTEONTEM,
                "confidence": "DECLARADO",
            },
        ),
        409,
        porque="O bezerro já descende da doadora; o inverso não pode existir.",
    )

    roteiro.passo(
        "4.6",
        "Genealogia no futuro é recusada",
        lambda: operador.post(
            f"/v1/livestock/animals/{rebanho['BEZERRO']}/paternity",
            {
                "father_id": rebanho["TOURO-4"],
                "occurred_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                "confidence": "DECLARADO",
            },
        ),
        409,
    )

    roteiro.passo(
        "4.7",
        "Animal inexistente responde 404",
        lambda: operador.post(
            "/v1/livestock/animals/00000000-0000-4000-8000-000000000000/maternity",
            {
                "genetic_mother_id": rebanho["DOADORA"],
                "occurred_at": ONTEM,
                "confidence": "DECLARADO",
            },
        ),
        404,
    )

    roteiro.passo(
        "5.1",
        "O auditor não declara linhagem",
        lambda: auditor.post(
            f"/v1/livestock/animals/{rebanho['BEZERRO']}/maternity",
            {
                "genetic_mother_id": rebanho["DOADORA"],
                "occurred_at": ONTEM,
                "confidence": "DECLARADO",
            },
        ),
        403,
        porque="Declarar linhagem é escrita, e é ela que dá valor ao registro.",
    )

    roteiro.passo(
        "5.2",
        "O auditor lê a genealogia",
        lambda: auditor.get(f"/v1/livestock/animals/{rebanho['BEZERRO']}/ancestry"),
        200,
        porque="Ler é o que o auditor faz; a negação vale só para a escrita.",
    )

    _acrescentar_reproducao(roteiro, operador, auditor, propriedade, rebanho)
    _acrescentar_geometria(roteiro, operador, auditor, rebanho)
    disponivel, motivo = _provider_configurado(operador)
    if disponivel:
        _acrescentar_car(roteiro, operador, rebanho)
    else:
        print(f"{AMARELO}  Parte 8 (importação do CAR) omitida.{FIM}")
        print(
            f"{CINZA}  Confira TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY na janela da "
            f"API — são lidas por ela, e não por este script.{FIM}"
        )
        if motivo:
            print(f"{CINZA}  O provider respondeu: {motivo[:220]}{FIM}")
    return roteiro


def _provider_configurado(cliente: Cliente) -> tuple[bool, str]:
    """A integração é opcional, e o roteiro não falha por ela estar ausente.

    Trata **duas** ausências, e não uma: provider não configurado (503) e provider
    que responde mas recusa — chave inválida, fora do ar, sem rota. Nos dois casos
    os passos seguintes falhariam todos pelo mesmo motivo, e cinco vermelhos que
    dizem a mesma coisa ensinam a ignorar vermelho.
    """
    sonda = cliente.get("/v1/livestock/properties/car-preview?cod_imovel=SONDA&state=MS")
    if sonda.status in (502, 503):
        motivo = str(sonda.corpo.get("detail", "")) if isinstance(sonda.corpo, dict) else ""
        return False, motivo
    return True, ""


QUADRADO = {
    "type": "Polygon",
    "coordinates": [
        [[-47.9, -15.8], [-47.8, -15.8], [-47.8, -15.7], [-47.9, -15.7], [-47.9, -15.8]]
    ],
}

MAIOR = {
    "type": "Polygon",
    "coordinates": [
        [[-47.95, -15.85], [-47.75, -15.85], [-47.75, -15.65], [-47.95, -15.65], [-47.95, -15.85]]
    ],
}

# Os lados se cruzam no meio: sintaticamente perfeita, topologicamente inválida.
AMPULHETA = {
    "type": "Polygon",
    "coordinates": [
        [[-47.9, -15.8], [-47.8, -15.7], [-47.8, -15.8], [-47.9, -15.7], [-47.9, -15.8]]
    ],
}


def _acrescentar_geometria(
    roteiro: Roteiro, operador: Cliente, auditor: Cliente, rebanho: Rebanho
) -> None:
    """Passo 17.1 — a primeira coluna espacial do Titan (ADR-0026).

    Cria a **própria** propriedade em vez de reusar a da semeadura: os passos
    afirmam "sem geometria" e "vira versão 2", e reusar faria o roteiro passar
    só na primeira execução — o que ensinaria a ignorar vermelho.
    """
    roteiro.passo(
        "7.0",
        "Cadastrar a propriedade que vai receber o limite",
        lambda: operador.post(
            "/v1/livestock/properties",
            {
                "code": f"GEO-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
                "name": "Fazenda do roteiro",
                "municipality": "Brasilia",
                "state_code": "DF",
            },
        ),
        201,
        guardar=lambda r: rebanho.ids.update({"PROPRIEDADE": str(r["property_id"])}),
    )

    def propriedade() -> str:
        return rebanho["PROPRIEDADE"]

    roteiro.passo(
        "7.1",
        "Propriedade sem geometria responde nulo",
        lambda: operador.get(f"/v1/livestock/properties/{propriedade()}/geometry"),
        200,
        conferir=lambda r: None if r.corpo is None else "já havia geometria registrada",
        porque="Lacuna declarada, e não erro: a propriedade opera sem limite.",
    )

    roteiro.passo(
        "7.2",
        "Registrar o limite da propriedade",
        lambda: operador.post(
            f"/v1/livestock/properties/{propriedade()}/geometry",
            {"source": "DECLARADA", "geojson": QUADRADO},
        ),
        201,
        conferir=lambda r: (
            None if len(str(r["source_digest"])) == 64 else "o digest não veio completo"
        ),
        porque="O digest identifica o material exatamente como foi recebido.",
    )

    roteiro.passo(
        "7.3",
        "Geometria com lados que se cruzam é recusada",
        lambda: operador.post(
            f"/v1/livestock/properties/{propriedade()}/geometry",
            {"source": "DECLARADA", "geojson": AMPULHETA},
        ),
        409,
        conferir=lambda r: (
            None if "ntersection" in str(r["detail"]) else "o motivo do PostGIS não veio"
        ),
        porque="Só o PostGIS pega isso — e o motivo diz onde o anel se rompe.",
    )

    roteiro.passo(
        "7.4",
        "Ponto não é limite de propriedade",
        lambda: operador.post(
            f"/v1/livestock/properties/{propriedade()}/geometry",
            {"source": "DECLARADA", "geojson": {"type": "Point", "coordinates": [-47.9, -15.8]}},
        ),
        409,
    )

    roteiro.passo(
        "7.5",
        "Geometria do SICAR sem o código do imóvel é recusada",
        lambda: operador.post(
            f"/v1/livestock/properties/{propriedade()}/geometry",
            {"source": "SICAR_CAR", "geojson": QUADRADO},
        ),
        409,
        porque="Sem o código, a importação não é reproduzível.",
    )

    roteiro.passo(
        "7.6",
        "Registrar de novo cria versão 2",
        lambda: operador.post(
            f"/v1/livestock/properties/{propriedade()}/geometry",
            {"source": "DECLARADA", "geojson": MAIOR},
        ),
        201,
        conferir=lambda r: None if r["version"] == 2 else f"veio versão {r['version']}",
        porque="Nunca substitui: a versão 1 é o que reproduz a avaliação antiga.",
    )

    roteiro.passo(
        "7.7",
        "O histórico traz as duas versões, com a primeira intacta",
        lambda: operador.get(f"/v1/livestock/properties/{propriedade()}/geometry/history"),
        200,
        conferir=lambda r: (
            None
            if [item["version"] for item in r.corpo] == [1, 2]
            and r.corpo[0]["geojson"]["coordinates"] == QUADRADO["coordinates"]
            else "o histórico não preservou a versão 1 como ela entrou"
        ),
        porque="É o que responde qual polígono uma avaliação passada usou.",
    )

    roteiro.passo(
        "7.8",
        "A vigente é a última registrada",
        lambda: operador.get(f"/v1/livestock/properties/{propriedade()}/geometry"),
        200,
        conferir=lambda r: None if r["version"] == 2 else "a vigente não é a versão 2",
    )

    roteiro.passo(
        "7.9",
        "O auditor lê o limite, mas não o declara",
        lambda: auditor.post(
            f"/v1/livestock/properties/{propriedade()}/geometry",
            {"source": "DECLARADA", "geojson": QUADRADO},
        ),
        403,
        porque="O polígono revela onde a operação fica; escrita é do operador.",
    )


# Um imóvel real do SICAR em Santa Rita do Pardo (MS), com 1.363,93 ha e cadastro
# atualizado em 2023 — a defasagem faz parte do que o roteiro demonstra.
CAR_DE_TESTE = "MS-5007554-1EF4AA06D08041829247C61FE4412C4F"
UF_DE_TESTE = "MS"


def _acrescentar_car(roteiro: Roteiro, operador: Cliente, rebanho: Rebanho) -> None:
    """Passo 17.2 — importacao do CAR pelo Titan_geodata.

    Cria a **propria** propriedade, como a Parte 7: reusar aquela faria o passo
    da data de captura ler a geometria declarada da Parte 7 e afirmar sobre ela
    algo que so vale para a importada.
    """

    def propriedade() -> str:
        return rebanho["PROPRIEDADE_CAR"]

    roteiro.passo(
        "8.0",
        "Cadastrar a propriedade que vai receber o CAR",
        lambda: operador.post(
            "/v1/livestock/properties",
            {
                "code": f"CAR-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
                "name": "Fazenda do CAR",
                "municipality": "Santa Rita do Pardo",
                "state_code": "MS",
            },
        ),
        201,
        guardar=lambda r: rebanho.ids.update({"PROPRIEDADE_CAR": str(r["property_id"])}),
    )

    consulta = f"cod_imovel={CAR_DE_TESTE}&state={UF_DE_TESTE}"

    def _conferir_importacao(r: Resposta) -> str | None:
        """A importação devolve o lote, não uma geometria.

        Conferir `r["source"]` no topo era o formato de antes das camadas — e a
        asserção que envelhece cala junto com o código que ela deveria vigiar.
        """
        gravadas = r["gravadas"]
        perimetro = [g for g in gravadas if g["layer"] == "AREA_IMOVEL"]
        if len(perimetro) != 1:
            return f"esperava exatamente um perímetro, vieram {len(perimetro)}"
        fontes = {g["source"] for g in gravadas}
        if fontes != {"SICAR_CAR"}:
            return f"as fontes vieram {sorted(fontes)}"
        sem_motivo = [c["layer"] for c in r["recusadas"] if not c.get("motivo")]
        if sem_motivo:
            return f"recusa sem motivo em {sem_motivo}"
        return None

    roteiro.passo(
        "8.1",
        "Consultar o CAR sem gravar nada",
        lambda: operador.get(f"/v1/livestock/properties/car-preview?{consulta}"),
        200,
        conferir=lambda r: (
            None
            if r["municipality"] and r["area_hectares"]
            else "a prévia não trouxe município e área"
        ),
        porque="Serve para pré-preencher o cadastro; quem confirma é o operador.",
    )

    roteiro.passo(
        "8.2",
        "A condição do cadastro vem sem ser interpretada",
        lambda: operador.get(f"/v1/livestock/properties/car-preview?{consulta}"),
        200,
        conferir=lambda r: None if r["registry_condition"] else "a condição do cadastro não veio",
        porque="Diz onde o cadastro está na fila do SICAR, não se a fazenda é regular.",
    )

    roteiro.passo(
        "8.3",
        "Importar o limite do CAR",
        lambda: operador.post(
            f"/v1/livestock/properties/{propriedade()}/geometry/import-car",
            {"cod_imovel": CAR_DE_TESTE, "state": UF_DE_TESTE},
        ),
        201,
        conferir=_conferir_importacao,
        porque=(
            "O perímetro é obrigatório; as demais camadas vêm juntas, e camada "
            "quebrada é recusada com motivo em vez de derrubar as boas."
        ),
    )

    roteiro.passo(
        "8.4",
        "captured_at é a data do CAR, não a da importação",
        lambda: operador.get(f"/v1/livestock/properties/{propriedade()}/geometry"),
        200,
        conferir=lambda r: (
            None
            if r["source"] == "SICAR_CAR"
            and r["captured_at"]
            and r["captured_at"] < r["imported_at"]
            else f"fonte={r['source']} captured_at={r['captured_at']}"
        ),
        porque="Este cadastro é de 2023: confundir os dois faria o dado parecer novo.",
    )

    roteiro.passo(
        "8.5",
        "CAR inexistente responde 404",
        lambda: operador.post(
            f"/v1/livestock/properties/{propriedade()}/geometry/import-car",
            {"cod_imovel": "MS-0000000-NAOEXISTE", "state": UF_DE_TESTE},
        ),
        404,
    )


def _acrescentar_reproducao(
    roteiro: Roteiro,
    operador: Cliente,
    auditor: Cliente,
    propriedade: str,
    rebanho: Rebanho,
) -> None:
    """Passo 13.3 — o parto como origem da identidade (ADR-0040)."""

    roteiro.passo(
        "6.1",
        "Cadastrar a MATRIZ do parto",
        lambda: operador.post(
            "/v1/livestock/animals",
            {"birth_property_id": propriedade, "sex": "FEMALE", "breed": "Nelore"},
        ),
        201,
        guardar=rebanho.guardar("MATRIZ"),
    )

    roteiro.passo(
        "6.2",
        "Parto gemelar: um vivo e um natimorto",
        lambda: operador.post(
            "/v1/livestock/reproductive-events/parturitions",
            {
                "dam_id": rebanho["MATRIZ"],
                "occurred_at": ONTEM,
                "sire_id": rebanho["TOURO-1"],
                "offspring": [
                    {"outcome": "NASCIDO_VIVO", "sex": "MALE", "breed": "Nelore"},
                    {"outcome": "NATIMORTO", "sex": "FEMALE"},
                ],
            },
        ),
        201,
        conferir=lambda r: (
            None
            if {cria["outcome"] for cria in r["offspring"]} == {"NASCIDO_VIVO", "NATIMORTO"}
            else "os dois resultados não vieram no mesmo evento"
        ),
        porque="Dois partos perderiam o vínculo obstétrico que explica o natimorto.",
        guardar=lambda r: rebanho.ids.update(
            {
                "PARTO": str(r["event_id"]),
                "BEZERRO-VIVO": str(
                    next(c for c in r["offspring"] if c["outcome"] == "NASCIDO_VIVO")["animal_id"]
                ),
                "NATIMORTO": str(
                    next(c for c in r["offspring"] if c["outcome"] == "NATIMORTO")["animal_id"]
                ),
            }
        ),
    )

    roteiro.passo(
        "6.3",
        "A cria já nasce com a linhagem pronta",
        lambda: operador.get(f"/v1/livestock/animals/{rebanho['BEZERRO-VIVO']}/ancestry"),
        200,
        conferir=lambda r: (
            None
            if rebanho["MATRIZ"] in {ramo["link"]["parent_id"] for ramo in r["parents"]}
            else "a mãe não apareceu na ascendência"
        ),
        porque="Um ato, uma transação: não há janela com o bezerro sem linhagem.",
    )

    roteiro.passo(
        "6.4",
        "O natimorto NÃO aparece no rebanho ativo",
        lambda: operador.get("/v1/livestock/animals?limit=200"),
        200,
        conferir=lambda r: (
            None
            if rebanho["NATIMORTO"] not in {item["animal_id"] for item in r["items"]}
            else "o natimorto apareceu como se estivesse pastando"
        ),
        porque="Ele é rastreável, mas nunca entrou no ciclo operacional.",
    )

    roteiro.passo(
        "6.5",
        "E não tem registro de saída",
        lambda: operador.get(f"/v1/livestock/animals/{rebanho['NATIMORTO']}"),
        200,
        conferir=lambda r: (
            None
            if r["saida"] is None and r["birth_outcome"] == "NATIMORTO"
            else "o natimorto recebeu saída, ou o resultado do nascimento não bate"
        ),
        porque="MORTE diria que nasceu vivo e morreu depois. Não foi o que houve.",
    )

    roteiro.passo(
        "6.6",
        "O natimorto conserva a linhagem",
        lambda: operador.get(f"/v1/livestock/animals/{rebanho['NATIMORTO']}/ancestry"),
        200,
        conferir=lambda r: None if r["parents"] else "o natimorto ficou sem ascendência",
        porque="É o que permite investigar de qual matriz e de qual touro ele veio.",
    )

    roteiro.passo(
        "6.7",
        "A origem do bezerro é o parto",
        lambda: auditor.get(f"/v1/livestock/animals/{rebanho['BEZERRO-VIVO']}/origin"),
        200,
        conferir=lambda r: (
            None
            if r["event_id"] == rebanho["PARTO"]
            else "a origem não aponta para o parto que o criou"
        ),
        porque="O nascimento é a origem comprovável da identidade, não um campo.",
    )

    roteiro.passo(
        "6.8",
        "Aborto: encerra a gestação sem criar animal",
        lambda: operador.post(
            "/v1/livestock/reproductive-events/pregnancy-losses",
            {
                "dam_id": rebanho["MATRIZ"],
                "occurred_at": ANTEONTEM,
                "gestational_age_days": 170,
                "gestational_age_basis": "ESTIMATED",
            },
        ),
        201,
        conferir=lambda r: None if r["offspring"] == [] else "o aborto inventou um indivíduo",
        porque="Um feto sem identidade atribuível não vira entidade rastreável.",
    )

    roteiro.passo(
        "6.9",
        "Idade gestacional sem base declarada é recusada",
        lambda: operador.post(
            "/v1/livestock/reproductive-events/pregnancy-losses",
            {"dam_id": rebanho["MATRIZ"], "occurred_at": ANTEONTEM, "gestational_age_days": 90},
        ),
        409,
        porque="Declarar idade sem dizer como se chegou a ela é inventar precisão.",
    )

    roteiro.passo(
        "6.10",
        "O histórico reprodutivo da matriz traz os dois desfechos",
        lambda: auditor.get(f"/v1/livestock/animals/{rebanho['MATRIZ']}/reproductive-events"),
        200,
        conferir=lambda r: (
            None
            if {evento["event_type"] for evento in r.corpo} == {"PARTO", "ABORTO"}
            else f"vieram {[e['event_type'] for e in r.corpo]}"
        ),
        porque="É a base do índice: cada gestação contada pelo que de fato foi.",
    )

    roteiro.passo(
        "6.11",
        "Um macho não pare",
        lambda: operador.post(
            "/v1/livestock/reproductive-events/parturitions",
            {
                "dam_id": rebanho["TOURO-1"],
                "occurred_at": ONTEM,
                "offspring": [{"outcome": "NASCIDO_VIVO", "sex": "MALE"}],
            },
        ),
        409,
    )

    roteiro.passo(
        "6.12",
        "O auditor não registra parto",
        lambda: auditor.post(
            "/v1/livestock/reproductive-events/parturitions",
            {
                "dam_id": rebanho["MATRIZ"],
                "occurred_at": ONTEM,
                "offspring": [{"outcome": "NASCIDO_VIVO", "sex": "MALE"}],
            },
        ),
        403,
        porque="Quem registra o parto decide o que passa a existir no rebanho.",
    )


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro de validação do Passo 13.2.")
    argumentos.add_argument(
        "--pausar", action="store_true", help="Espera ENTER entre um passo e o seguinte."
    )
    argumentos.add_argument(
        "--organizacao", default="", help="Organization A. Sem isto, descobre pelo vínculo ativo."
    )
    opcoes = argumentos.parse_args()

    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url and not opcoes.organizacao:
        raise SystemExit(
            "Defina TITAN_DATABASE_URL (para descobrir a Organization) ou passe --organizacao."
        )

    organizacao = opcoes.organizacao or _descobrir_organizacao(database_url)

    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)

    # Um diário só para os dois: o relato precisa mostrar as chamadas na ordem em
    # que aconteceram, e não separadas por quem as fez.
    diario: list[Requisicao] = []

    def cliente(username: str, rotulo: str) -> Cliente:
        return Cliente(
            base_url=api,
            token=admin.token_de_usuario(
                client_id=CLIENTE_DE_VALIDACAO, username=username, senha=SENHA_DEMONSTRACAO
            ),
            organization_id=organizacao,
            rotulo=rotulo,
            diario=diario,
        )

    operador = cliente("titan_operador", "operador")
    auditor = cliente("titan_auditor", "auditor")

    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  API           : {api}")
    print(f"  Keycloak      : {keycloak_url} (realm {realm})")
    print(f"  Organization  : {organizacao}")
    _exigir_permissoes_do_passo(operador)
    propriedade = _propriedade(operador)
    print(f"  Propriedade   : {propriedade}")
    print(
        f"{CINZA}  Os dois usuários entram pelo cliente '{CLIENTE_DE_VALIDACAO}', criado neste\n"
        f"  realm local porque o do Swagger não concede token sem navegador.{FIM}"
    )

    codigo = _montar_roteiro(operador, auditor, propriedade).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(
            f"{AMARELO}O script confere status e forma da resposta.{FIM} O que ele não julga é se "
            "a regra faz sentido para o negócio — essa leitura continua sendo sua."
        )
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
