"""Roteiro executavel de artefato recebido e lacuna de cobertura (ADR-0042).

python -m uv run --locked python -m apps.validacao.artefato_transferencia
python -m uv run --locked python -m apps.validacao.artefato_transferencia --pausar
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
    transferencia = datetime.now(UTC) - timedelta(days=1)
    cobertura_ate = transferencia - timedelta(hours=10)
    roteiro = Roteiro("ADR-0042 - Artefato recebido e lacuna de cobertura", diario=operador.diario)

    roteiro.passo(
        "1",
        "Operador cadastra propriedade e animal adquirido",
        lambda: _criar_animal(operador, ids),
        201,
        conferir=lambda r: None if ids.get("animal_id") else "animal nao foi criado",
        porque=(
            "O animal de destino e local; a continuidade vem por prova, nao por animal_id global."
        ),
    )
    roteiro.passo(
        "2",
        "Operador cadastra a contraparte de origem",
        lambda: operador.post(
            "/v1/livestock/external-counterparties",
            {
                "name": "Fazenda Origem Transferencia",
                "counterparty_type": "FARM",
                "identifiers": [f"CAR:MT-{uuid4().hex[:12]}"],
            },
        ),
        201,
        conferir=lambda r: None if r["counterparty_id"] else "sem counterparty_id",
        guardar=lambda r: ids.update(counterparty_id=str(r["counterparty_id"])),
        porque="A origem e representacao local, nao acesso ao tenant de outra Organization.",
    )
    roteiro.passo(
        "3",
        "Operador registra o artefato recebido",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/received-transfer-artifacts",
            {
                "source_counterparty_id": ids["counterparty_id"],
                "bundle_digest": "b" * 64,
                "bundle_issued_at": cobertura_ate.isoformat(),
                "transfer_effective_at": transferencia.isoformat(),
                "coverage_known_from": (transferencia - timedelta(days=300)).isoformat(),
                "coverage_known_until": cobertura_ate.isoformat(),
                "issuer_name": "Fazenda Origem Transferencia",
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["coverage"]["gaps"][0]["code"] == "COVERAGE_BEFORE_TRANSFER"
            else "cobertura anterior a transferencia nao virou lacuna"
        ),
        guardar=lambda r: ids.update(artifact_id=str(r["artifact_id"])),
        porque="Pacote integro pode estar desatualizado; a lacuna precisa aparecer.",
    )
    roteiro.passo(
        "4",
        "Operador lista os artefatos recebidos do animal",
        lambda: operador.get(
            f"/v1/livestock/animals/{ids['animal_id']}/received-transfer-artifacts"
        ),
        200,
        conferir=lambda r: (
            None
            if r["items"][0]["artifact_id"] == ids["artifact_id"]
            and r["items"][0]["coverage"]["gaps"][0]["code"] == "COVERAGE_BEFORE_TRANSFER"
            else "listagem nao preservou o artefato e sua lacuna"
        ),
        porque="A auditoria precisa reencontrar o artefato e a cobertura declarada.",
    )
    return roteiro


def _criar_animal(operador: Cliente, ids: dict[str, str]) -> object:
    propriedade = operador.post(
        "/v1/livestock/properties",
        {
            "code": f"PROP-{uuid4().hex[:8]}",
            "name": "Fazenda Destino Artefato",
            "municipality": "Cuiaba",
            "state_code": "MT",
        },
    )
    if propriedade.status != 201:
        return propriedade
    ids["property_id"] = str(propriedade["property_id"])
    animal = operador.post(
        "/v1/livestock/animals",
        {"birth_property_id": ids["property_id"], "sex": "MALE"},
    )
    if animal.status == 201:
        ids["animal_id"] = str(animal["animal_id"])
    return animal


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
