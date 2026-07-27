"""Roteiro executavel: lote com tratamento heterogeneo ate o frigorifico.

Tres animais na mesma fazenda de recria e engorda. Um recebe vacina e
medicamento corretos; outro recebe vacina registrada sem vinculo com a
campanha (erro de registro) e medicamento recente, ainda em carencia; o
terceiro nao recebe nenhuma aplicacao. O lote inteiro fica bloqueado
enquanto o animal em carencia permanece nele (rule-carencia-lote); removido,
o lote e reavaliado e aprovado. A matriz de mercado roda por animal,
mostrando resultados heterogeneos dentro do mesmo lote. Os elegiveis seguem
para o frigorifico; o excluido do lote continua rastreavel, nao apagado.

A proveniencia externa (fazenda de origem, artefato recebido, fato
importado) ja e demonstrada em ponta a ponta por simulacao_comercial.py;
este roteiro nao a repete -- o foco aqui e o lote e o tratamento
heterogeneo dentro dele.

python -m uv run --locked python -m apps.validacao.lote_comercial
python -m uv run --locked python -m apps.validacao.lote_comercial --pausar
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.matriz_elegibilidade_mercados import _preparar_regras_de_mercado
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Roteiro
from packages.livestock_application.market_eligibility import MarketEligibilityPurpose

_CAMPANHA_CODE = f"febre-aftosa-2026-{uuid4().hex[:8]}"


def _montar_roteiro(operador: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    agora = datetime.now(UTC)
    # Medicamento com 30 dias de carencia: aplicado ha 40 dias ja esta fora
    # da carencia (elegivel); aplicado ha 5 dias ainda esta dentro (bloqueia).
    aplicado_ha_muito = agora - timedelta(days=40)
    aplicado_ha_pouco = agora - timedelta(days=5)

    roteiro = Roteiro(
        "Lote com tratamento heterogeneo - da recria ao frigorifico",
    )

    roteiro.passo(
        "1",
        "Operador cadastra a fazenda de recria e engorda",
        lambda: operador.post(
            "/v1/livestock/properties",
            {
                "code": f"PROP-LOTE-{uuid4().hex[:8]}",
                "name": "Fazenda Recria e Engorda",
                "municipality": "Campo Grande",
                "state_code": "MS",
            },
        ),
        201,
        conferir=lambda r: None if r["property_id"] else "sem property_id",
        guardar=lambda r: ids.update(property_id=str(r["property_id"])),
        porque=(
            "A proveniencia externa (fazenda de origem, aquisicao) ja foi "
            "provada em simulacao_comercial.py; aqui os animais ja chegaram "
            "para recria e engorda, e o foco e o lote."
        ),
    )
    roteiro.passo(
        "2",
        "Operador cria os tres animais do lote",
        lambda: _criar_tres_animais(operador, ids),
        201,
        conferir=lambda r: (
            None
            if all(ids.get(k) for k in ("animal_correto", "animal_errado", "animal_ausente"))
            else "nem todos os tres animais foram criados"
        ),
        porque="O lote precisa de mais de um animal para o bloqueio coletivo fazer sentido.",
    )
    roteiro.passo(
        "3",
        "Operador cria o lote de recria e engorda",
        lambda: operador.post(
            "/v1/livestock/lots",
            {
                "code": f"LOTE-{uuid4().hex[:8]}",
                "name": "Lote Recria e Engorda 2026",
                "property_id": ids["property_id"],
                "lot_type": "OPERATIONAL",
            },
        ),
        201,
        conferir=lambda r: None if r["lot_id"] else "sem lot_id",
        guardar=lambda r: ids.update(lot_id=str(r["lot_id"])),
        porque=(
            "Recria e engorda agrupa animais de origens e tratamentos "
            "distintos sob um destino comum."
        ),
    )
    roteiro.passo(
        "4",
        "Operador adiciona os tres animais ao lote",
        lambda: _adicionar_tres_ao_lote(operador, ids),
        201,
        conferir=lambda r: None,
        porque=(
            "Os tres passam a compartilhar o mesmo desfecho comercial ate "
            "serem tratados de forma diferente."
        ),
    )
    roteiro.passo(
        "5",
        "Operador declara a campanha sanitaria oficial",
        lambda: operador.post(
            "/v1/livestock/sanitary-campaigns",
            {
                "code": _CAMPANHA_CODE,
                "name": "Campanha Febre Aftosa 2026",
                "starts_at": (agora - timedelta(days=180)).isoformat(),
                "ends_at": (agora + timedelta(days=180)).isoformat(),
                "disease": "Febre Aftosa",
                "authority": "MAPA",
            },
        ),
        201,
        conferir=lambda r: (
            None if r["code"] == _CAMPANHA_CODE else "campanha nao preservou o codigo"
        ),
        guardar=lambda r: ids.update(campaign_id=str(r["campaign_id"])),
        porque="Sem campanha declarada, exigibilidade sanitaria nao tem o que exigir.",
    )
    roteiro.passo(
        "6",
        "Operador cadastra o medicamento e o lote do medicamento",
        lambda: _cadastrar_medicamento_e_lote(operador, ids),
        201,
        conferir=lambda r: None if ids.get("batch_medicamento_id") else "sem lote de medicamento",
        porque="A carencia farmacologica precisa de um produto com prazo declarado.",
    )
    roteiro.passo(
        "7",
        "Operador cadastra a vacina e o lote da vacina",
        lambda: _cadastrar_vacina_e_lote(operador, ids),
        201,
        conferir=lambda r: None if ids.get("batch_vacina_id") else "sem lote de vacina",
        porque=(
            "Vacina e medicamento sao produtos distintos (IMMUNOBIOLOGICAL vs "
            "PHARMACOLOGICAL); a vacina tem carencia zero para nao interferir "
            "no bloqueio farmacologico que este roteiro quer isolar."
        ),
    )
    roteiro.passo(
        "8",
        "Animal correto: vacina vinculada a campanha e medicamento ha 40 dias",
        lambda: _aplicar_tratamento_correto(operador, ids, aplicado_ha_muito),
        201,
        conferir=lambda r: (
            None
            if r["sanitary_campaign_id"] == ids["campaign_id"]
            else "vacina nao ficou vinculada a campanha"
        ),
        porque=(
            "O animal tratado direitinho e a referencia contra a qual os outros dois se comparam."
        ),
    )
    roteiro.passo(
        "9",
        "Animal errado: vacina SEM vinculo com a campanha e medicamento ha 5 dias",
        lambda: _aplicar_tratamento_errado(operador, ids, aplicado_ha_pouco),
        201,
        conferir=lambda r: (
            None
            if r["sanitary_campaign_id"] is None
            else "vacina errada nao deveria ter vinculo com a campanha"
        ),
        porque=(
            "Erro de registro real: a vacina foi aplicada, mas quem lancou "
            "esqueceu de vincular a campanha -- para a exigibilidade sanitaria, "
            "isso conta como se a campanha nao tivesse sido atendida. O "
            "medicamento recente ainda esta dentro da carencia de 30 dias."
        ),
    )
    roteiro.passo(
        "10",
        "Operador confere a exigibilidade sanitaria dos tres animais",
        lambda: _conferir_exigibilidade_sanitaria(operador, ids),
        200,
        conferir=lambda r: None,
        porque=(
            "correto=ATENDIDA, errado=AUSENTE (vinculo errado nao conta), "
            "ausente=AUSENTE (nenhuma aplicacao) -- tres respostas diferentes "
            "para tres historias diferentes."
        ),
    )
    roteiro.passo(
        "11",
        "Operador avalia a elegibilidade do lote com o animal em carencia dentro",
        lambda: operador.post(f"/v1/livestock/lots/{ids['lot_id']}/eligibility", {}),
        201,
        conferir=lambda r: (
            None
            if r["result"] == "rejeitada"
            else f"esperava lote rejeitado, veio result={r['result']!r}"
        ),
        porque=(
            "rule-carencia-lote bloqueia o lote inteiro enquanto qualquer "
            "membro estiver em carencia -- o lote nao se comercializa em "
            "pedacos por omissao."
        ),
    )
    roteiro.passo(
        "12",
        "Operador remove o animal em carencia do lote",
        lambda: operador.post(
            f"/v1/livestock/lots/{ids['lot_id']}/removals",
            {"animal_id": ids["animal_errado"], "reason": "Animal em carencia farmacologica."},
        ),
        201,
        conferir=lambda r: (
            None if r["animal_id"] == ids["animal_errado"] else "removeu o animal errado"
        ),
        porque=(
            "Remover fecha a vigencia do vinculo e acrescenta um fato -- o "
            "vinculo anterior permanece na historia, por isso e POST e nao DELETE."
        ),
    )
    roteiro.passo(
        "13",
        "Operador reavalia o lote sem o animal em carencia",
        lambda: operador.post(f"/v1/livestock/lots/{ids['lot_id']}/eligibility", {}),
        201,
        conferir=lambda r: (
            None
            if r["result"] == "aprovada"
            else f"esperava lote aprovado, veio result={r['result']!r}"
        ),
        porque="Sem o animal bloqueador, o lote volta a ser comercializavel.",
    )
    roteiro.passo(
        "14",
        "Operador roda a matriz de mercado do animal correto",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_correto']}/eligibility/market-matrix", {}
        ),
        201,
        conferir=lambda r: _checar_matriz_sem_carencia(r["markets"]),
        porque="Fora da carencia, EUA promove direto a ELEGIVEL; China so falta o frigorifico.",
    )
    roteiro.passo(
        "15",
        "Operador roda a matriz de mercado do animal sem nenhuma aplicacao",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_ausente']}/eligibility/market-matrix", {}
        ),
        201,
        conferir=lambda r: _checar_matriz_sem_carencia(r["markets"]),
        porque=(
            "Ausencia de tratamento nao e carencia: registro existente vale "
            "mais que registro ausente. O resultado farmacologico e igual ao "
            "do animal tratado direitinho -- a diferenca entre eles esta na "
            "exigibilidade sanitaria do passo 10, nao aqui."
        ),
    )
    roteiro.passo(
        "16",
        "Operador roda a matriz do animal excluido do lote, ainda em carencia",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_errado']}/eligibility/market-matrix", {}
        ),
        201,
        conferir=lambda r: _checar_matriz_com_carencia(r["markets"]),
        porque=(
            "Excluir do lote nao apaga o animal: ele continua rastreavel, e a "
            "matriz mostra exatamente por que ele nao pode ser comercializado "
            "agora -- nao um vazio, uma razao."
        ),
    )
    roteiro.passo(
        "17",
        "Operador cadastra o frigorifico e sua qualificacao para a China",
        lambda: _cadastrar_frigorifico_qualificado(operador, ids, agora),
        201,
        conferir=lambda r: (
            None
            if r["status"] == "HABILITADO"
            else "qualificacao do frigorifico nao foi registrada"
        ),
        porque="Sem habilitacao explicita, nenhum animal deste lote promove a ELEGIVEL na China.",
    )
    roteiro.passo(
        "18",
        "Operador vende os dois animais elegiveis para o frigorifico",
        lambda: _abater_elegiveis(operador, ids, agora),
        201,
        conferir=lambda r: None,
        porque=(
            "Apenas quem passou na elegibilidade segue para o frigorifico -- "
            "o excluido do lote fica de fora."
        ),
    )
    roteiro.passo(
        "19",
        "Operador lista o rebanho e confere quem foi vendido e quem ficou",
        lambda: operador.get("/v1/livestock/animals?incluir_saidos=true&limit=200"),
        200,
        conferir=lambda r: _conferir_desfecho_final(r["items"], ids),
        porque=(
            "O frigorifico recebeu dois animais rastreaveis ate a fazenda de "
            "recria; o terceiro continua no rebanho, em carencia, sem "
            "desfecho comercial ainda."
        ),
    )
    return roteiro


def _criar_tres_animais(operador: Cliente, ids: dict[str, str]) -> object:
    chaves = ("animal_correto", "animal_errado", "animal_ausente")
    resposta = None
    for chave in chaves:
        resposta = operador.post(
            "/v1/livestock/animals",
            {"birth_property_id": ids["property_id"], "sex": "MALE"},
        )
        if resposta.status != 201:
            return resposta
        ids[chave] = str(resposta["animal_id"])
    return resposta


def _adicionar_tres_ao_lote(operador: Cliente, ids: dict[str, str]) -> object:
    resposta = None
    for chave in ("animal_correto", "animal_errado", "animal_ausente"):
        resposta = operador.post(
            f"/v1/livestock/lots/{ids['lot_id']}/members",
            {"animal_id": ids[chave]},
        )
        if resposta.status != 201:
            return resposta
    return resposta


def _cadastrar_medicamento_e_lote(operador: Cliente, ids: dict[str, str]) -> object:
    medicamento = operador.post(
        "/v1/livestock/medications",
        {
            "trade_name": f"Ivomec Gold Lote {uuid4().hex[:8]}",
            "active_ingredient": "Ivermectina",
            "manufacturer": "Boehringer",
            "withdrawal_period_days": 30,
            "product_class": "PHARMACOLOGICAL",
        },
    )
    if medicamento.status != 201:
        return medicamento
    ids["medicamento_id"] = str(medicamento["medication_id"])
    lote = operador.post(
        "/v1/livestock/medication-batches",
        {
            "medication_id": ids["medicamento_id"],
            "batch_number": f"LOTE-MED-{uuid4().hex[:8]}",
            "expiry_date": "2027-12-31T00:00:00Z",
        },
    )
    if lote.status == 201:
        ids["batch_medicamento_id"] = str(lote["batch_id"])
    return lote


def _cadastrar_vacina_e_lote(operador: Cliente, ids: dict[str, str]) -> object:
    vacina = operador.post(
        "/v1/livestock/medications",
        {
            "trade_name": f"Aftogan Lote {uuid4().hex[:8]}",
            "active_ingredient": "Vacina inativada febre aftosa",
            "manufacturer": "Biogenese",
            "withdrawal_period_days": 0,
            "product_class": "IMMUNOBIOLOGICAL",
        },
    )
    if vacina.status != 201:
        return vacina
    ids["vacina_id"] = str(vacina["medication_id"])
    lote = operador.post(
        "/v1/livestock/medication-batches",
        {
            "medication_id": ids["vacina_id"],
            "batch_number": f"LOTE-VAC-{uuid4().hex[:8]}",
            "expiry_date": "2027-12-31T00:00:00Z",
        },
    )
    if lote.status == 201:
        ids["batch_vacina_id"] = str(lote["batch_id"])
    return lote


def _aplicar_tratamento_correto(operador: Cliente, ids: dict[str, str], quando: datetime) -> object:
    vacina = operador.post(
        "/v1/livestock/treatments",
        {
            "animal_id": ids["animal_correto"],
            "medication_batch_id": ids["batch_vacina_id"],
            "applied_at": quando.isoformat(),
            "sanitary_campaign_id": ids["campaign_id"],
        },
    )
    if vacina.status != 201:
        return vacina
    medicamento = operador.post(
        "/v1/livestock/treatments",
        {
            "animal_id": ids["animal_correto"],
            "medication_batch_id": ids["batch_medicamento_id"],
            "applied_at": quando.isoformat(),
        },
    )
    return vacina if medicamento.status != 201 else vacina


def _aplicar_tratamento_errado(operador: Cliente, ids: dict[str, str], quando: datetime) -> object:
    # A vacina foi aplicada de verdade, mas quem registrou esqueceu de vincular
    # a campanha -- erro de lancamento, nao de aplicacao. Para a exigibilidade
    # sanitaria (que so conta aplicacao vinculada a campanha), isso equivale a
    # nao ter sido aplicada.
    vacina = operador.post(
        "/v1/livestock/treatments",
        {
            "animal_id": ids["animal_errado"],
            "medication_batch_id": ids["batch_vacina_id"],
            "applied_at": quando.isoformat(),
        },
    )
    if vacina.status != 201:
        return vacina
    medicamento = operador.post(
        "/v1/livestock/treatments",
        {
            "animal_id": ids["animal_errado"],
            "medication_batch_id": ids["batch_medicamento_id"],
            "applied_at": quando.isoformat(),
        },
    )
    return vacina if medicamento.status != 201 else vacina


def _conferir_exigibilidade_sanitaria(operador: Cliente, ids: dict[str, str]) -> object:
    esperado = {
        "animal_correto": "ATENDIDA",
        "animal_errado": "AUSENTE",
        "animal_ausente": "AUSENTE",
    }
    ultima = None
    for chave, status_esperado in esperado.items():
        ultima = operador.get(
            f"/v1/livestock/animals/{ids[chave]}/sanitary-requirements/{_CAMPANHA_CODE}"
        )
        if ultima.status != 200 or ultima["status"] != status_esperado:
            return ultima
    return ultima


def _checar_matriz_sem_carencia(markets: list[dict[str, object]]) -> str | None:
    por_mercado = {str(item["market"]): item for item in markets}
    eua = MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code
    china = MarketEligibilityPurpose.EXPORTACAO_CHINA.code
    if por_mercado.get(eua, {}).get("status") != "ELEGIVEL":
        return "EUA deveria estar ELEGIVEL fora da carencia"
    if por_mercado.get(china, {}).get("status") != "CONDICIONADO":
        return "China deveria estar CONDICIONADO (falta frigorifico) fora da carencia"
    return None


def _checar_matriz_com_carencia(markets: list[dict[str, object]]) -> str | None:
    por_mercado = {str(item["market"]): item for item in markets}
    eua = MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code
    if por_mercado.get(eua, {}).get("status") != "NAO_ELEGIVEL":
        return "EUA deveria estar NAO_ELEGIVEL dentro da carencia"
    return None


def _cadastrar_frigorifico_qualificado(
    operador: Cliente, ids: dict[str, str], agora: datetime
) -> object:
    frigorifico = operador.post(
        "/v1/livestock/external-counterparties",
        {
            "name": "Frigorifico Lote Comercial",
            "counterparty_type": "SLAUGHTERHOUSE",
            "identifiers": [f"SIF:{uuid4().hex[:8].upper()}"],
            "notes": "Frigorifico ficticio para o roteiro de lote comercial.",
        },
    )
    if frigorifico.status != 201:
        return frigorifico
    ids["slaughterhouse_id"] = str(frigorifico["counterparty_id"])
    return operador.post(
        f"/v1/livestock/external-counterparties/{ids['slaughterhouse_id']}/establishment-qualifications",
        {
            "market_purpose": MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
            "status": "HABILITADO",
            "source_name": "lista-sif-ficticia",
            "source_version": "2026-07",
            "assessed_at": agora.isoformat(),
        },
    )


def _abater_elegiveis(operador: Cliente, ids: dict[str, str], agora: datetime) -> object:
    resposta = None
    for chave in ("animal_correto", "animal_ausente"):
        resposta = operador.post(
            f"/v1/livestock/animals/{ids[chave]}/exit",
            {
                "exit_type": "ABATE",
                "occurred_at": agora.isoformat(),
                "reason": "Abate comercial validado pelo roteiro de lote.",
                "destination_counterparty_id": ids["slaughterhouse_id"],
            },
        )
        if resposta.status != 201:
            return resposta
    return resposta


def _conferir_desfecho_final(items: list[dict[str, object]], ids: dict[str, str]) -> str | None:
    por_animal = {str(item.get("animal_id")): item for item in items}

    for chave in ("animal_correto", "animal_ausente"):
        item = por_animal.get(ids[chave])
        saida = item.get("saida") if item else None
        if not (
            isinstance(saida, dict)
            and saida.get("exit_type") == "ABATE"
            and saida.get("destination_counterparty_id") == ids["slaughterhouse_id"]
        ):
            return f"{chave} deveria aparecer abatido para o frigorifico"

    excluido = por_animal.get(ids["animal_errado"])
    if excluido is None or excluido.get("saida") is not None:
        return "animal excluido do lote nao deveria ter saida registrada"
    return None


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro do lote comercial heterogeneo.")
    argumentos.add_argument("--pausar", action="store_true")
    argumentos.add_argument("--organizacao", default="")
    opcoes = argumentos.parse_args()

    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit(
            "Defina TITAN_DATABASE_URL para o roteiro preparar regras e descobrir a Organization."
        )
    organizacao = opcoes.organizacao or _descobrir_organizacao(database_url)
    _preparar_regras_de_mercado(database_url, organizacao)

    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)

    operador = Cliente(
        base_url=api,
        token=admin.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO,
            username="titan_operador",
            senha=SENHA_DEMONSTRACAO,
        ),
        organization_id=organizacao,
        rotulo="operador",
    )

    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  API          : {api}")
    print(f"  Keycloak     : {keycloak_url} (realm {realm})")
    print(f"  Organization : {organizacao}")
    print(f"  Campanha     : {_CAMPANHA_CODE}")
    print(f"{CINZA}  Rode a semeadura novamente se vier 403 por permissao ausente.{FIM}")

    codigo = _montar_roteiro(operador).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(f"{AMARELO}O script confere forma e status; a leitura de negocio segue humana.{FIM}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
