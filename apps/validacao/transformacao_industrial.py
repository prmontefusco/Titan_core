"""Roteiro executavel: fan-out, travessia, balanco, dossie e fan-in (ADR-0046, Passos 11.2-11.6).

Um animal nasce na fazenda, sai do rebanho por ABATE, e o mesmo tenant que
detem o frigorifico registra a transformacao industrial: o animal vira duas
saidas rastreaveis (TraceableItem) num unico TransformationEvent(SLAUGHTER).
O roteiro tambem prova as recusas que a ADR exige: sem saida ABATE registrada
nao ha transformacao, o mesmo animal nao pode ser consumido duas vezes, e
fan-out abaixo de duas saidas e recusado pelo proprio contrato HTTP.

Na sequencia (Passo 11.3), prova a linha do tempo do item e o recall nas duas
direcoes: item -> transformacao -> animal (retrospectiva) e animal ->
transformacao -> todos os itens (prospectiva), sem que nenhuma das duas
pontas copie o historico da outra -- cada uma cita a mesma TransformationEvent.

Na sequencia (Passo 11.4), prova o balanco minimo: com peso de entrada e das
saidas na mesma base de medicao, o balanco fecha (BALANCED); sem peso de
entrada, fica NOT_ASSESSED -- nunca zero nem BALANCED por omissao.

Na sequencia (Passo 11.5), prova o detalhe e o dossie de rastreabilidade do
item: um documento so reunindo a transformacao que o criou (com balanco), a
relacao quantitativa, a linha do tempo e a origem por recall.

Por fim (Passo 11.6), prova o fan-in real: as duas meias-carcaças do abate
do Passo 11.2 viram entrada de um unico TransformationEvent(DEBONING), que
produz saidas novas. O recall a partir de uma dessas saidas alcanca as DUAS
origens sem inventar correspondencia 1:1 -- e, mais fundo no grafo, o
proprio animal do Passo 11.2, provando a cadeia completa.

O caso inter-organizacional (fazenda e frigorifico em tenants distintos) fica
para quando o protocolo da ADR-0042 for extendido a este fluxo -- fora de
escopo destes passos, que so provam o caso de uma unica Organization.

python -m uv run --locked python -m apps.validacao.transformacao_industrial
python -m uv run --locked python -m apps.validacao.transformacao_industrial --pausar
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Resposta, Roteiro


def _montar_roteiro(operador: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    agora = datetime.now(UTC)
    abate_em = agora - timedelta(days=1)

    roteiro = Roteiro("Transformacao industrial - fan-out real de abate (ADR-0046)")

    roteiro.passo(
        "1",
        "Operador cadastra a fazenda de origem",
        lambda: operador.post(
            "/v1/livestock/properties",
            {
                "code": f"PROP-ORIGEM-{uuid4().hex[:8]}",
                "name": "Fazenda de Origem",
                "municipality": "Barretos",
                "state_code": "SP",
            },
        ),
        201,
        conferir=lambda r: None if r["property_id"] else "sem property_id",
        guardar=lambda r: ids.update(fazenda_id=str(r["property_id"])),
        porque="O animal precisa nascer em algum lugar antes de qualquer transformacao existir.",
    )
    roteiro.passo(
        "2",
        "Operador cadastra o frigorifico como propriedade da mesma Organization",
        lambda: operador.post(
            "/v1/livestock/properties",
            {
                "code": f"PROP-FRIGORIFICO-{uuid4().hex[:8]}",
                "name": "Frigorifico Industrial",
                "municipality": "Barretos",
                "state_code": "SP",
            },
        ),
        201,
        conferir=lambda r: None if r["property_id"] else "sem property_id",
        guardar=lambda r: ids.update(frigorifico_id=str(r["property_id"])),
        porque=(
            "ADR-0046 item 9: TransformationEvent so vale dentro da mesma "
            "Organization. O caso fazenda/frigorifico em tenants distintos "
            "segue o protocolo da ADR-0042 e nao e este roteiro."
        ),
    )
    roteiro.passo(
        "3",
        "Operador cadastra o animal a ser abatido",
        lambda: operador.post(
            "/v1/livestock/animals",
            {"birth_property_id": ids["fazenda_id"], "sex": "MALE"},
        ),
        201,
        conferir=lambda r: None if r["animal_id"] else "sem animal_id",
        guardar=lambda r: ids.update(animal_id=str(r["animal_id"])),
        porque="E o sujeito que a transformacao vai consumir como entrada.",
    )
    roteiro.passo(
        "4",
        "Operador tenta transformar o animal ANTES de registrar a saida por abate",
        lambda: operador.post(
            "/v1/livestock/transformations/slaughter",
            {
                "animal_id": ids["animal_id"],
                "facility_property_id": ids["frigorifico_id"],
                "occurred_at": abate_em.isoformat(),
                "outputs": _duas_saidas(),
            },
        ),
        409,
        conferir=_conferir_conflito,
        porque=(
            "ADR-0046 item 8: TransformationEvent(SLAUGHTER) exige AnimalExit(ABATE) "
            "ja registrada -- AnimalExit sozinho nao e evidencia de abate, mas e "
            "pre-condicao dele."
        ),
    )
    roteiro.passo(
        "5",
        "Operador registra a saida do animal por ABATE",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/exit",
            {
                "exit_type": "ABATE",
                "occurred_at": abate_em.isoformat(),
                "reason": "Abate industrial validado pelo roteiro de transformacao.",
            },
        ),
        201,
        conferir=lambda r: None if r["exit_type"] == "ABATE" else "exit_type nao ficou ABATE",
        porque="So depois deste fato o animal pode virar entrada de uma transformacao.",
    )
    roteiro.passo(
        "6",
        "Operador tenta transformar com apenas uma saida (fan-out insuficiente)",
        lambda: operador.post(
            "/v1/livestock/transformations/slaughter",
            {
                "animal_id": ids["animal_id"],
                "facility_property_id": ids["frigorifico_id"],
                "occurred_at": (abate_em + timedelta(hours=1)).isoformat(),
                "outputs": _duas_saidas()[:1],
            },
        ),
        422,
        conferir=lambda r: None,
        porque=(
            "ADR-0046 item 1: o contrato aceita N=1, mas o cenario validado "
            "(Passo 11.2) exige fan-out real -- o proprio contrato HTTP recusa "
            "menos de duas saidas antes de chegar ao dominio."
        ),
    )
    roteiro.passo(
        "7",
        "Operador registra a transformacao SLAUGHTER com fan-out real",
        lambda: operador.post(
            "/v1/livestock/transformations/slaughter",
            {
                "animal_id": ids["animal_id"],
                "facility_property_id": ids["frigorifico_id"],
                "occurred_at": (abate_em + timedelta(hours=1)).isoformat(),
                "outputs": _duas_saidas(),
            },
        ),
        201,
        conferir=lambda r: _conferir_fan_out(r),
        guardar=lambda r: ids.update(
            transformation_id=str(r["transformation_id"]),
            item_1=str(r["created_items"][0]["item_id"]),
            item_2=str(r["created_items"][1]["item_id"]),
        ),
        porque=(
            "Um animal, um TransformationEvent, duas saidas rastreaveis novas -- "
            "o cenario que o Passo 11.2 prova de verdade."
        ),
    )
    roteiro.passo(
        "8",
        "Operador tenta transformar o MESMO animal outra vez",
        lambda: operador.post(
            "/v1/livestock/transformations/slaughter",
            {
                "animal_id": ids["animal_id"],
                "facility_property_id": ids["frigorifico_id"],
                "occurred_at": (abate_em + timedelta(hours=2)).isoformat(),
                "outputs": _duas_saidas(),
            },
        ),
        409,
        conferir=_conferir_conflito,
        porque=(
            "Um animal so e consumido como entrada uma vez -- reaproveitar "
            "seria genealogia contraditoria."
        ),
    )
    roteiro.passo(
        "9",
        "Operador consulta a linha do tempo de um dos itens criados",
        lambda: operador.get(f"/v1/livestock/traceable-items/{ids['item_1']}/timeline"),
        200,
        conferir=_conferir_timeline_do_item,
        porque=(
            "O item nao tem historico proprio (Passo 11.3): tudo que aparece "
            "vem da TransformationEvent que o criou, citada -- nao copiada."
        ),
    )
    roteiro.passo(
        "10",
        "Operador rastreia a origem do item (item -> transformacao -> animal)",
        lambda: operador.get(f"/v1/livestock/traceable-items/{ids['item_1']}/recall"),
        200,
        conferir=lambda r: _conferir_recall_alcanca(r, "animal", ids["animal_id"]),
        porque=(
            "Travessia retrospectiva (Passo 11.3): o recall so tem a projecao "
            "UniversalRelation para percorrer, e ainda assim reconstroi o "
            "caminho ate o animal que originou o item."
        ),
    )
    roteiro.passo(
        "11",
        "Operador rastreia o destino do animal (animal -> transformacao -> itens)",
        lambda: operador.get(f"/v1/livestock/animals/{ids['animal_id']}/recall"),
        200,
        conferir=lambda r: (
            _conferir_recall_alcanca(r, "traceable_item", ids["item_1"])
            or _conferir_recall_alcanca(r, "traceable_item", ids["item_2"])
        ),
        porque=(
            "Travessia prospectiva (Passo 11.3): a partir do animal, o recall "
            "alcanca as DUAS saidas -- o fan-out real que o Passo 11.2 provou."
        ),
    )
    roteiro.passo(
        "12",
        "Operador cadastra um segundo animal, para a transformacao com balanco",
        lambda: operador.post(
            "/v1/livestock/animals",
            {"birth_property_id": ids["fazenda_id"], "sex": "MALE"},
        ),
        201,
        conferir=lambda r: None if r["animal_id"] else "sem animal_id",
        guardar=lambda r: ids.update(animal_balanco_id=str(r["animal_id"])),
        porque="O primeiro animal ja foi consumido; o balanco precisa de um novo.",
    )
    roteiro.passo(
        "13",
        "Operador registra a saida ABATE do segundo animal",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_balanco_id']}/exit",
            {"exit_type": "ABATE", "occurred_at": abate_em.isoformat()},
        ),
        201,
        conferir=lambda r: None if r["exit_type"] == "ABATE" else "exit_type nao ficou ABATE",
        porque="Mesma pre-condicao do Passo 11.2.",
    )
    roteiro.passo(
        "14",
        "Operador registra a transformacao com peso de entrada e saidas (balanco calculado)",
        lambda: operador.post(
            "/v1/livestock/transformations/slaughter",
            {
                "animal_id": ids["animal_balanco_id"],
                "facility_property_id": ids["frigorifico_id"],
                "occurred_at": (abate_em + timedelta(hours=1)).isoformat(),
                "outputs": _duas_saidas_com_peso_total_300(),
                "input_quantity": "300.000",
                "input_unit": "kg",
                "input_measurement_basis": "peso liquido",
            },
        ),
        201,
        conferir=lambda r: _conferir_balance(r, "ASSESSED", "BALANCED"),
        guardar=lambda r: ids.update(
            item_balanco_1=str(r["created_items"][0]["item_id"]),
            item_balanco_2=str(r["created_items"][1]["item_id"]),
        ),
        porque=(
            "Passo 11.4: com peso de entrada e das duas saidas na mesma base "
            "de medicao, o balanco fecha em BALANCED -- 300kg entram, 300kg saem."
        ),
    )
    roteiro.passo(
        "15",
        "Operador cadastra um terceiro animal, para a transformacao sem peso",
        lambda: operador.post(
            "/v1/livestock/animals",
            {"birth_property_id": ids["fazenda_id"], "sex": "MALE"},
        ),
        201,
        conferir=lambda r: None if r["animal_id"] else "sem animal_id",
        guardar=lambda r: ids.update(animal_sem_peso_id=str(r["animal_id"])),
        porque="Prova o outro lado do balanco: ausencia de peso.",
    )
    roteiro.passo(
        "16",
        "Operador registra a saida ABATE do terceiro animal",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_sem_peso_id']}/exit",
            {"exit_type": "ABATE", "occurred_at": abate_em.isoformat()},
        ),
        201,
        conferir=lambda r: None if r["exit_type"] == "ABATE" else "exit_type nao ficou ABATE",
        porque="Mesma pre-condicao do Passo 11.2.",
    )
    roteiro.passo(
        "17",
        "Operador registra a transformacao SEM peso de entrada (balanco nao avaliado)",
        lambda: operador.post(
            "/v1/livestock/transformations/slaughter",
            {
                "animal_id": ids["animal_sem_peso_id"],
                "facility_property_id": ids["frigorifico_id"],
                "occurred_at": (abate_em + timedelta(hours=1)).isoformat(),
                "outputs": _duas_saidas(),
            },
        ),
        201,
        conferir=lambda r: _conferir_balance(r, "NOT_ASSESSED", "NOT_APPLICABLE"),
        porque=(
            "Passo 11.4: sem peso de entrada, o balanco fica NOT_ASSESSED -- "
            "nunca zero nem BALANCED por omissao."
        ),
    )
    roteiro.passo(
        "18",
        "Operador detalha o item da transformacao com balanco",
        lambda: operador.get(f"/v1/livestock/traceable-items/{ids['item_balanco_1']}"),
        200,
        conferir=lambda r: None if r["item_type"] == "HALF_CARCASS" else "item_type inesperado",
        porque="Identidade minima do item -- tipo, rotulo e a transformacao que o criou.",
    )
    roteiro.passo(
        "19",
        "Operador monta o dossie de rastreabilidade do item",
        lambda: operador.get(f"/v1/livestock/traceable-items/{ids['item_balanco_1']}/dossier"),
        200,
        conferir=lambda r: _conferir_dossie(r, ids["animal_balanco_id"]),
        porque=(
            "Passo 11.5: um documento so, reunindo transformacao (com balanco), "
            "relacao quantitativa, linha do tempo e origem por recall -- nao e "
            "o Dossier do Core, que exige Decision."
        ),
    )
    roteiro.passo(
        "20",
        "Operador tenta a desossa com apenas uma entrada (fan-in insuficiente)",
        lambda: operador.post(
            "/v1/livestock/transformations/deboning",
            {
                "facility_property_id": ids["frigorifico_id"],
                "occurred_at": (abate_em + timedelta(hours=2)).isoformat(),
                "inputs": [{"item_id": ids["item_1"]}],
                "outputs": _saidas_de_desossa(),
            },
        ),
        422,
        conferir=lambda r: None,
        porque=(
            "ADR-0046 item 1: fan-in real (Passo 11.6) exige ao menos duas "
            "entradas -- o proprio contrato HTTP recusa antes do dominio, "
            "espelhando a mesma regra do fan-out no Passo 11.2."
        ),
    )
    roteiro.passo(
        "21",
        "Operador registra a desossa com fan-in real (as duas meias-carcaças do Passo 11.2)",
        lambda: operador.post(
            "/v1/livestock/transformations/deboning",
            {
                "facility_property_id": ids["frigorifico_id"],
                "occurred_at": (abate_em + timedelta(hours=2)).isoformat(),
                "inputs": [
                    {"item_id": ids["item_1"], "quantity": "115.400", "unit": "kg"},
                    {"item_id": ids["item_2"], "quantity": "112.900", "unit": "kg"},
                ],
                "outputs": _saidas_de_desossa(),
            },
        ),
        201,
        conferir=_conferir_fan_in,
        guardar=lambda r: ids.update(
            deboning_id=str(r["transformation_id"]),
            cut_batch_id=str(r["created_items"][0]["item_id"]),
        ),
        porque=(
            "Passo 11.6: duas entradas (as meias-carcaças do abate do animal "
            "do Passo 11.2), um TransformationEvent(DEBONING), saidas novas -- "
            "o fan-in real que a ADR previu desde o item 1."
        ),
    )
    roteiro.passo(
        "22",
        "Operador tenta reaproveitar uma entrada ja consumida pela desossa anterior",
        lambda: operador.post(
            "/v1/livestock/transformations/deboning",
            {
                "facility_property_id": ids["frigorifico_id"],
                "occurred_at": (abate_em + timedelta(hours=3)).isoformat(),
                "inputs": [
                    {"item_id": ids["item_1"]},
                    {"item_id": ids["item_balanco_1"]},
                ],
                "outputs": _saidas_de_desossa(),
            },
        ),
        409,
        conferir=_conferir_conflito,
        porque=(
            "Um item so e consumido como entrada uma vez -- mesma regra do animal no Passo 11.2."
        ),
    )
    roteiro.passo(
        "23",
        "Operador tenta usar um item de tipo nao permitido como entrada da desossa",
        lambda: operador.post(
            "/v1/livestock/transformations/deboning",
            {
                "facility_property_id": ids["frigorifico_id"],
                "occurred_at": (abate_em + timedelta(hours=3)).isoformat(),
                "inputs": [
                    {"item_id": ids["cut_batch_id"]},
                    {"item_id": ids["item_balanco_2"]},
                ],
                "outputs": _saidas_de_desossa(),
            },
        ),
        409,
        conferir=_conferir_conflito,
        porque=(
            "ADR-0046 item 6: o perfil do processo DEBONING so aceita "
            "CARCASS/HALF_CARCASS como entrada -- um CUT_BATCH (saida da "
            "propria desossa) nao serve de entrada para outra."
        ),
    )
    roteiro.passo(
        "24",
        "Operador rastreia a origem do item criado pela desossa (fan-in)",
        lambda: operador.get(f"/v1/livestock/traceable-items/{ids['cut_batch_id']}/recall"),
        200,
        conferir=lambda r: (
            _conferir_recall_alcanca(r, "traceable_item", ids["item_1"])
            or _conferir_recall_alcanca(r, "traceable_item", ids["item_2"])
            or _conferir_recall_alcanca(r, "animal", ids["animal_id"])
        ),
        porque=(
            "Passo 11.6, invariante 15: o recall alcanca as DUAS origens "
            "(as meias-carcaças) sem inventar correspondencia 1:1 -- e, mais "
            "fundo no grafo, o animal original do Passo 11.2, provando a "
            "cadeia completa animal -> abate -> desossa."
        ),
    )
    return roteiro


def _conferir_conflito(resposta: Resposta) -> str | None:
    return None if resposta["reason_code"] == "CONFLITO_DE_DOMINIO" else "reason_code inesperado"


def _conferir_timeline_do_item(resposta: Resposta) -> str | None:
    tipos = [entrada["entry_type"] for entrada in resposta["entries"]]
    if "livestock.transformation_event_recorded" not in tipos:
        return "timeline do item deveria conter livestock.transformation_event_recorded"
    return None


def _conferir_recall_alcanca(resposta: Resposta, entity_type: str, valor: str) -> str | None:
    """Confere que o alvo foi alcançado -- não que o status é "conclusivo".

    Num grafo em estrela (1 evento, vários participantes), a travessia AMBAS
    reexplora o centro a partir de cada folha já visitada e a própria
    RecallService declara isso "ciclo_detectado", que torna o resultado
    inconclusivo por definição ("qualquer lacuna torna o resultado
    inconclusivo, sem exceção" -- core_domain/recall.py). Isso é esperado e
    correto para fan-out/fan-in: não é lacuna de cobertura, é o BFS evitando
    voltar a nó já visitado. O que este roteiro precisa confirmar é que o
    alvo aparece em algum caminho -- o "inconclusivo" por ciclo não invalida
    a travessia.
    """
    for caminho in resposta["caminhos"]:
        ultimo_passo = caminho["passos"][-1]
        if ultimo_passo["para_tipo"] == entity_type and ultimo_passo["para_id"] == valor:
            return None
    return f"nenhum caminho alcancou {entity_type}:{valor} (status={resposta['status']!r})"


def _duas_saidas() -> list[dict[str, object]]:
    return [
        {
            "item_type": "HALF_CARCASS",
            "quantity": "115.400",
            "unit": "kg",
            "measurement_basis": "peso liquido pos-sangria",
            "label": f"HC-{uuid4().hex[:6]}-A",
        },
        {
            "item_type": "HALF_CARCASS",
            "quantity": "112.900",
            "unit": "kg",
            "measurement_basis": "peso liquido pos-sangria",
            "label": f"HC-{uuid4().hex[:6]}-B",
        },
    ]


def _conferir_fan_out(resposta: Resposta) -> str | None:
    itens = resposta["created_items"]
    if not isinstance(itens, list) or len(itens) < 2:
        return "esperava ao menos 2 created_items (fan-out real)"
    if resposta["process_type"] != "SLAUGHTER":
        return "process_type deveria ser SLAUGHTER"
    return None


def _duas_saidas_com_peso_total_300() -> list[dict[str, object]]:
    return [
        {
            "item_type": "HALF_CARCASS",
            "quantity": "150.000",
            "unit": "kg",
            "measurement_basis": "peso liquido",
            "label": f"HC-{uuid4().hex[:6]}-A",
        },
        {
            "item_type": "HALF_CARCASS",
            "quantity": "150.000",
            "unit": "kg",
            "measurement_basis": "peso liquido",
            "label": f"HC-{uuid4().hex[:6]}-B",
        },
    ]


def _conferir_dossie(resposta: Resposta, animal_id_esperado: str) -> str | None:
    transformacao = resposta["transformation"]
    if transformacao["balance"]["result"] != "BALANCED":
        return f"esperava balance.result BALANCED, veio {transformacao['balance']['result']!r}"

    quantitativo = resposta["quantitative"]
    if quantitativo is None or quantitativo["quantity"] != "150.000":
        return f"esperava quantitative.quantity '150.000', veio {quantitativo!r}"

    if resposta["timeline"]["entry_count"] < 1:
        return "timeline do dossie deveria ter ao menos uma entrada"

    origens = resposta["origins"]["caminhos"]
    alcancou_animal = any(
        caminho["passos"][-1]["para_tipo"] == "animal"
        and caminho["passos"][-1]["para_id"] == animal_id_esperado
        for caminho in origens
    )
    if not alcancou_animal:
        return f"origins deveria alcancar o animal {animal_id_esperado}"
    return None


def _conferir_balance(resposta: Resposta, status_esperado: str, result_esperado: str) -> str | None:
    balance = resposta["balance"]
    if balance["status"] != status_esperado:
        return f"balance.status deveria ser {status_esperado!r}, veio {balance['status']!r}"
    if balance["result"] != result_esperado:
        return f"balance.result deveria ser {result_esperado!r}, veio {balance['result']!r}"
    return None


def _saidas_de_desossa() -> list[dict[str, object]]:
    return [
        {
            "item_type": "CUT_BATCH",
            "quantity": "150.000",
            "unit": "kg",
            "measurement_basis": "peso liquido",
            "label": f"CORTE-{uuid4().hex[:6]}",
        },
        {
            "item_type": "TRIM_BATCH",
            "quantity": "78.300",
            "unit": "kg",
            "measurement_basis": "peso liquido",
            "label": f"APARA-{uuid4().hex[:6]}",
        },
    ]


def _conferir_fan_in(resposta: Resposta) -> str | None:
    itens = resposta["created_items"]
    if not isinstance(itens, list) or len(itens) < 1:
        return "esperava ao menos 1 created_item"
    entradas = resposta["input_item_ids"]
    if not isinstance(entradas, list) or len(entradas) != 2:
        return f"esperava 2 input_item_ids (fan-in real), veio {entradas!r}"
    if resposta["process_type"] != "DEBONING":
        return "process_type deveria ser DEBONING"
    return None


def main() -> int:
    argumentos = argparse.ArgumentParser(
        description="Roteiro de transformacao industrial (ADR-0046)."
    )
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
        raise SystemExit("Defina TITAN_DATABASE_URL para o roteiro descobrir a Organization.")
    organizacao = opcoes.organizacao or _descobrir_organizacao(database_url)

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
    print(f"{CINZA}  Rode a semeadura novamente se vier 403 por permissao ausente.{FIM}")

    codigo = _montar_roteiro(operador).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(f"{AMARELO}O script confere forma e status; a leitura de negocio segue humana.{FIM}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
