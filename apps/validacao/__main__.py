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


def _descobrir_organizacao(database_url: str) -> str:
    """A Organization em que o usuário de demonstração de fato opera.

    Não é a operadora — a operadora é onde a identidade vive, e é justamente
    onde ele **não** opera. Quem responde é o vínculo, e o vínculo mais recente
    é o da última semeadura.
    """
    engine = create_engine(database_url)
    with engine.connect() as conexao:
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
    sonda = cliente.get("/v1/livestock/animals/00000000-0000-4000-8000-000000000000/ancestry")
    if sonda.status != 403:
        return
    raise SystemExit(
        f"{AMARELO}O papel desta Organization não tem as permissões da genealogia.{FIM}\n"
        "Os papéis guardam as permissões que existiam quando foram semeados, e este\n"
        "passo acrescentou duas. Semeie de novo e reinicie a API com a operadora nova:\n"
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

    return roteiro


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
