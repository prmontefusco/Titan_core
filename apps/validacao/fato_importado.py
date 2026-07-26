"""Roteiro executavel de fato importado com autoria preservada (ADR-0042).

python -m uv run --locked python -m apps.validacao.fato_importado
python -m uv run --locked python -m apps.validacao.fato_importado --pausar
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
    roteiro = Roteiro("ADR-0042 - Fato importado preserva autoria", diario=operador.diario)

    roteiro.passo(
        "1",
        "Operador prepara animal, contraparte e artefato",
        lambda: _criar_cenario(operador, ids, transferencia),
        201,
        conferir=lambda r: None if ids.get("artifact_id") else "cenario incompleto",
        porque="Fato importado sempre nasce de artefato recebido, nunca solto.",
    )
    roteiro.passo(
        "2",
        "Operador registra fato importado do artefato",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/imported-facts",
            {
                "source_artifact_id": ids["artifact_id"],
                "fact_type": "livestock.treatment_applied",
                "occurred_at": (transferencia - timedelta(days=30)).isoformat(),
                "asserted_by": "Fazenda Origem Importada",
                "confidence_tier": "CRYPTOGRAPHICALLY_ATTESTED",
                "payload": {"withdrawal_period_days": 45, "substance": "produto ficticio"},
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["origin"] == "IMPORTED_ASSERTION"
            and r["asserted_by"] == "Fazenda Origem Importada"
            and r["source_artifact_id"] == ids["artifact_id"]
            else "fato importado nao preservou origem, autoria ou artefato"
        ),
        guardar=lambda r: ids.update(imported_fact_id=str(r["imported_fact_id"])),
        porque="Importar nao reescreve autoria: o destino recebeu, mas nao afirmou o fato.",
    )
    roteiro.passo(
        "3",
        "Operador lista os fatos importados do animal",
        lambda: operador.get(f"/v1/livestock/animals/{ids['animal_id']}/imported-facts"),
        200,
        conferir=lambda r: (
            None
            if r["items"][0]["imported_fact_id"] == ids["imported_fact_id"]
            and r["items"][0]["origin"] == "IMPORTED_ASSERTION"
            else "listagem nao preservou o fato importado"
        ),
        porque="A auditoria precisa reencontrar quem afirmou, quem recebeu e a prova fonte.",
    )
    roteiro.passo(
        "4",
        "Operador executa elegibilidade usando o fato importado",
        lambda: operador.post(f"/v1/livestock/animals/{ids['animal_id']}/eligibility"),
        201,
        conferir=lambda r: (
            None
            if r["result"] == "rejeitada" and r["reasons"]
            else "elegibilidade nao considerou a carencia importada"
        ),
        porque=(
            "O fato importado nao fica apenas arquivado: ele alimenta a decisao, "
            "mantendo a autoria no snapshot auditavel."
        ),
    )
    return roteiro


def _criar_cenario(operador: Cliente, ids: dict[str, str], transferencia: datetime) -> object:
    propriedade = operador.post(
        "/v1/livestock/properties",
        {
            "code": f"PROP-{uuid4().hex[:8]}",
            "name": "Fazenda Destino Fato Importado",
            "municipality": "Cuiaba",
            "state_code": "MT",
        },
    )
    if propriedade.status != 201:
        return propriedade
    animal = operador.post(
        "/v1/livestock/animals",
        {"birth_property_id": propriedade["property_id"], "sex": "MALE"},
    )
    if animal.status != 201:
        return animal
    ids["animal_id"] = str(animal["animal_id"])
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        {"name": "Fazenda Origem Importada", "counterparty_type": "FARM"},
    )
    if contraparte.status != 201:
        return contraparte
    artefato = operador.post(
        f"/v1/livestock/animals/{ids['animal_id']}/received-transfer-artifacts",
        {
            "source_counterparty_id": contraparte["counterparty_id"],
            "bundle_digest": "d" * 64,
            "bundle_issued_at": transferencia.isoformat(),
            "transfer_effective_at": transferencia.isoformat(),
            "coverage_known_until": transferencia.isoformat(),
            "issuer_name": "Fazenda Origem Importada",
        },
    )
    if artefato.status == 201:
        ids["artifact_id"] = str(artefato["artifact_id"])
    return artefato


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
