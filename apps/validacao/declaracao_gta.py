"""Roteiro executavel de declaracao documental de GTA.

SPEC: docs/specs/approved/2026-09-15-declaracao-gta-documental.md
PLAN: docs/plans/GTA_DECLARACAO_BUILD_PLAN.md

python -m uv run --locked python -m apps.validacao.declaracao_gta
python -m uv run --locked python -m apps.validacao.declaracao_gta --pausar
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro

_TRANSFERENCIA = datetime.now(UTC) - timedelta(days=1)


def _payload_gta_valido() -> dict[str, object]:
    return {
        "gta_number": f"MS-{uuid4().hex[:9]}",
        "issuing_state": "MS",
        "issuing_agency": "IAGRO",
        "issued_at": "2026-09-10",
        "origin_description": "Fazenda Santa Rita, Ribas do Rio Pardo/MS",
        "destination_description": "Fazenda Boa Vista, Campo Grande/MS",
        "purpose": "recria",
        "animal_count": 40,
    }


def _pedido_aquisicao(
    contraparte_id: str, bundle_digest: str, payload: dict[str, object]
) -> dict[str, object]:
    return {
        "source_counterparty_id": contraparte_id,
        "bundle_digest": bundle_digest,
        "bundle_issued_at": _TRANSFERENCIA.isoformat(),
        "transfer_effective_at": _TRANSFERENCIA.isoformat(),
        "coverage_known_from": (_TRANSFERENCIA - timedelta(days=180)).isoformat(),
        "coverage_known_until": _TRANSFERENCIA.isoformat(),
        "issuer_name": "IAGRO",
        "imported_facts": [
            {
                "fact_type": "livestock.gta_declared",
                "occurred_at": _TRANSFERENCIA.isoformat(),
                "asserted_by": "IAGRO",
                "confidence_tier": "DOCUMENTED",
                "payload": payload,
            }
        ],
    }


def _montar_roteiro(operador: Cliente, auditor: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("Declaracao documental de GTA", diario=operador.diario)

    roteiro.passo(
        "1",
        "Operador cadastra propriedade, animal e contraparte de origem",
        lambda: _preparar_cenario(operador, ids),
        201,
        conferir=lambda r: (
            None
            if ids.get("animal_id") and ids.get("animal_id_2") and ids.get("counterparty_id")
            else "cenario nao foi criado por completo"
        ),
        porque=(
            "A GTA declara terceiro (fazenda de origem) e o animal que a recebeu; "
            "dois animais provam que a mesma guia pode cobrir varios."
        ),
    )
    roteiro.passo(
        "2",
        "Operador declara a GTA com payload completo",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/documentary-acquisitions",
            _pedido_aquisicao(ids["counterparty_id"], "e" * 64, _payload_gta_valido()),
        ),
        201,
        conferir=lambda r: (
            None
            if r["imported_facts"][0]["fact_type"] == "livestock.gta_declared"
            else "fato declarado nao preservou o fact_type de GTA"
        ),
        guardar=lambda r: ids.update(artifact_id=str(r["artifact"]["artifact_id"])),
        porque="Payload completo e valido deve ser aceito, sem inventar campo algum.",
    )
    roteiro.passo(
        "3",
        "Guia sem numero e recusada, sem persistir nada",
        lambda: _declarar_gta_com_campo_ausente(operador, ids, "gta_number"),
        422,
        conferir=lambda r: (
            None
            if r["reason_code"] == "PAYLOAD_GTA_INVALIDO" and "gta_number" in r["detail"]
            else "recusa nao nomeou o campo ausente"
        ),
        porque="Declarar 'GTA' sem numero e o problema que esta SPEC existe para impedir.",
    )
    roteiro.passo(
        "4",
        "UF do orgao emissor em minusculo e recusada",
        lambda: _declarar_gta_com_valor(operador, ids, "issuing_state", "ms"),
        422,
        conferir=lambda r: (
            None
            if r["reason_code"] == "PAYLOAD_GTA_INVALIDO" and "issuing_state" in r["detail"]
            else "recusa nao nomeou issuing_state"
        ),
        porque="Forma da UF importa para nao virar dado inconsistente na proveniencia.",
    )
    roteiro.passo(
        "5",
        "Quantidade de animais zero e recusada",
        lambda: _declarar_gta_com_valor(operador, ids, "animal_count", 0),
        422,
        conferir=lambda r: (
            None
            if r["reason_code"] == "PAYLOAD_GTA_INVALIDO" and "animal_count" in r["detail"]
            else "recusa nao nomeou animal_count"
        ),
        porque="Guia sem quantidade positiva de animais nao e uma guia valida.",
    )
    roteiro.passo(
        "6",
        "Fato declarado aparece na consulta de fatos importados do animal",
        lambda: operador.get(f"/v1/livestock/animals/{ids['animal_id']}/imported-facts"),
        200,
        conferir=lambda r: (
            None
            if any(item["fact_type"] == "livestock.gta_declared" for item in r["items"])
            else "GTA declarada no passo 2 nao aparece na consulta"
        ),
        porque="Proveniencia que nao pode ser reencontrada nao serve para auditoria.",
    )
    roteiro.passo(
        "7",
        "Mesma GTA cobre um segundo animal, sem conflito",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id_2']}/documentary-acquisitions",
            _pedido_aquisicao(ids["counterparty_id"], "e" * 64, _payload_gta_valido()),
        ),
        201,
        conferir=lambda r: (
            None
            if r["imported_facts"][0]["fact_type"] == "livestock.gta_declared"
            else "segundo animal nao recebeu a declaracao"
        ),
        porque=("Uma GTA real cobre um lote; a unicidade e por animal, nao por numero de guia."),
    )
    roteiro.passo(
        "8",
        "Auditor nao consegue declarar GTA (sem permissao de escrita)",
        lambda: auditor.post(
            f"/v1/livestock/animals/{ids['animal_id']}/documentary-acquisitions",
            _pedido_aquisicao(ids["counterparty_id"], "e" * 64, _payload_gta_valido()),
        ),
        403,
        conferir=lambda r: (
            None if r["reason_code"] == "PERMISSAO_AUSENTE" else "negacao nao veio como esperado"
        ),
        porque="Ler proveniencia nao concede autoridade para declara-la.",
    )
    return roteiro


def _declarar_gta_com_campo_ausente(operador: Cliente, ids: dict[str, str], campo: str) -> object:
    payload = _payload_gta_valido()
    del payload[campo]
    return operador.post(
        f"/v1/livestock/animals/{ids['animal_id']}/documentary-acquisitions",
        _pedido_aquisicao(ids["counterparty_id"], "f" * 64, payload),
    )


def _declarar_gta_com_valor(
    operador: Cliente, ids: dict[str, str], campo: str, valor: object
) -> object:
    payload = _payload_gta_valido()
    payload[campo] = valor
    return operador.post(
        f"/v1/livestock/animals/{ids['animal_id']}/documentary-acquisitions",
        _pedido_aquisicao(ids["counterparty_id"], "f" * 64, payload),
    )


def _preparar_cenario(operador: Cliente, ids: dict[str, str]) -> object:
    propriedade = operador.post(
        "/v1/livestock/properties",
        {
            "code": f"PROP-{uuid4().hex[:8]}",
            "name": "Fazenda Destino GTA",
            "municipality": "Campo Grande",
            "state_code": "MS",
        },
    )
    if propriedade.status != 201:
        return propriedade
    ids["property_id"] = str(propriedade["property_id"])

    animal_1 = operador.post(
        "/v1/livestock/animals",
        {"birth_property_id": ids["property_id"], "sex": "MALE"},
    )
    if animal_1.status != 201:
        return animal_1
    ids["animal_id"] = str(animal_1["animal_id"])

    animal_2 = operador.post(
        "/v1/livestock/animals",
        {"birth_property_id": ids["property_id"], "sex": "MALE"},
    )
    if animal_2.status != 201:
        return animal_2
    ids["animal_id_2"] = str(animal_2["animal_id"])

    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        {
            "name": "Fazenda Santa Rita",
            "counterparty_type": "FARM",
            "identifiers": [f"CAR:MS-{uuid4().hex[:12]}"],
        },
    )
    if contraparte.status == 201:
        ids["counterparty_id"] = str(contraparte["counterparty_id"])
    return contraparte


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro de declaracao documental de GTA.")
    argumentos.add_argument("--pausar", action="store_true")
    argumentos.add_argument("--organizacao", default="")
    opcoes = argumentos.parse_args()

    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = _ambiente("TITAN_DATABASE_URL", "")
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
    diario: list[Requisicao] = []
    operador = Cliente(
        base_url=api,
        token=admin.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO,
            username="titan_operador",
            senha=SENHA_DEMONSTRACAO,
        ),
        organization_id=organizacao,
        rotulo="operador",
        diario=diario,
    )
    auditor = Cliente(
        base_url=api,
        token=admin.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO,
            username="titan_auditor",
            senha=SENHA_DEMONSTRACAO,
        ),
        organization_id=organizacao,
        rotulo="auditor",
        diario=diario,
    )

    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  API          : {api}")
    print(f"  Keycloak     : {keycloak_url} (realm {realm})")
    print(f"  Organization : {organizacao}")
    print(f"{CINZA}  Rode a semeadura novamente se vier 403 por permissao ausente.{FIM}")

    codigo = _montar_roteiro(operador, auditor).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(
            f"{AMARELO}Nenhuma integracao com sistema estadual de e-GTA ou com NF-e foi feita "
            f"aqui -- e declaracao documental, conforme a SPEC.{FIM}"
        )
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
