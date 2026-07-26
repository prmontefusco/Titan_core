"""Roteiro executavel da contraparte externa e saida estruturada (ADR-0042).

python -m uv run --locked python -m apps.validacao.contraparte_externa
python -m uv run --locked python -m apps.validacao.contraparte_externa --pausar
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _montar_roteiro(operador: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("ADR-0042 - Contraparte externa e saida estruturada", diario=operador.diario)

    roteiro.passo(
        "1",
        "Operador cadastra uma propriedade para o animal",
        lambda: operador.post(
            "/v1/livestock/properties",
            {
                "code": f"PROP-{uuid4().hex[:8]}",
                "name": "Fazenda Origem Validacao",
                "municipality": "Cuiaba",
                "state_code": "MT",
            },
        ),
        201,
        conferir=lambda r: None if r["property_id"] else "sem property_id",
        guardar=lambda r: ids.update(property_id=str(r["property_id"])),
        porque="O animal continua pertencendo a uma Organization; destino externo nao muda isso.",
    )
    roteiro.passo(
        "2",
        "Operador cadastra animal vivo",
        lambda: operador.post(
            "/v1/livestock/animals",
            {"birth_property_id": ids["property_id"], "sex": "MALE"},
        ),
        201,
        conferir=lambda r: None if r["animal_id"] else "sem animal_id",
        guardar=lambda r: ids.update(animal_id=str(r["animal_id"])),
        porque="A saida estruturada continua sendo fato sobre um animal local.",
    )
    roteiro.passo(
        "3",
        "Operador cadastra contraparte externa local",
        lambda: operador.post(
            "/v1/livestock/external-counterparties",
            {
                "name": "Fazenda Destino Validacao",
                "counterparty_type": "FARM",
                "identifiers": [f"CAR:MT-{uuid4().hex[:12]}"],
                "notes": "Contraparte ficticia para validacao manual.",
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["counterparty_id"] and r["counterparty_type"] == "FARM"
            else "contraparte nao veio na forma esperada"
        ),
        guardar=lambda r: ids.update(counterparty_id=str(r["counterparty_id"])),
        porque="Contraparte e cadastro local do operador, nao uma Organization do Titan.",
    )
    roteiro.passo(
        "4",
        "Operador registra venda apontando para a contraparte",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/exit",
            {
                "exit_type": "VENDA",
                "occurred_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                "reason": "Venda para recria.",
                "destination_counterparty_id": ids["counterparty_id"],
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["destination_counterparty_id"] == ids["counterparty_id"]
            else "saida nao preservou destination_counterparty_id"
        ),
        porque="A venda e um fato consumado; ela nao depende de aceite do destino.",
    )
    roteiro.passo(
        "5",
        "Operador consulta o detalhe do animal com a saida estruturada",
        lambda: operador.get(f"/v1/livestock/animals/{ids['animal_id']}"),
        200,
        conferir=lambda r: (
            None
            if r["saida"]["destination_counterparty_id"] == ids["counterparty_id"]
            else "detalhe nao trouxe a contraparte na saida"
        ),
        porque="A auditoria precisa reconstruir para quem a custodia foi declarada.",
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro da ADR-0042.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir a Organization.")
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
