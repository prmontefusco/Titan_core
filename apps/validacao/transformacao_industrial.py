"""Roteiro executavel: fan-out real de abate (ADR-0046, Passo 11.2).

Um animal nasce na fazenda, sai do rebanho por ABATE, e o mesmo tenant que
detem o frigorifico registra a transformacao industrial: o animal vira duas
saidas rastreaveis (TraceableItem) num unico TransformationEvent(SLAUGHTER).
O roteiro tambem prova as recusas que a ADR exige: sem saida ABATE registrada
nao ha transformacao, o mesmo animal nao pode ser consumido duas vezes, e
fan-out abaixo de duas saidas e recusado pelo proprio contrato HTTP.

O caso inter-organizacional (fazenda e frigorifico em tenants distintos) fica
para quando o protocolo da ADR-0042 for extendido a este fluxo -- fora de
escopo do Passo 11.2, que so prova o caso de uma unica Organization.

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
    return roteiro


def _conferir_conflito(resposta: Resposta) -> str | None:
    return None if resposta["reason_code"] == "CONFLITO_DE_DOMINIO" else "reason_code inesperado"


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
