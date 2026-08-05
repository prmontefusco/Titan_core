"""Roteiro executavel da aquisicao documental composta (ADR-0042).

python -m uv run --locked python -m apps.validacao.aquisicao_documental
python -m uv run --locked python -m apps.validacao.aquisicao_documental --pausar
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
    roteiro = Roteiro("ADR-0042 - Aquisicao documental composta", diario=operador.diario)

    roteiro.passo(
        "1",
        "Operador prepara animal de destino e contraparte de origem",
        lambda: _criar_cenario(operador, ids),
        201,
        conferir=lambda r: (
            None
            if ids.get("animal_id") and ids.get("counterparty_id")
            else "cenario nao criou animal e contraparte"
        ),
        porque=(
            "A continuidade nasce de prova recebida pela Organization atual, nunca de acesso ao "
            "tenant da origem."
        ),
    )
    roteiro.passo(
        "2",
        "Operador registra a aquisicao documental com artefato e fato importado",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/documentary-acquisitions",
            {
                "source_counterparty_id": ids["counterparty_id"],
                "bundle_digest": "e" * 64,
                "bundle_issued_at": transferencia.isoformat(),
                "transfer_effective_at": transferencia.isoformat(),
                "coverage_known_from": (transferencia - timedelta(days=180)).isoformat(),
                "coverage_known_until": transferencia.isoformat(),
                "issuer_name": "Fazenda Origem Documental",
                "imported_facts": [
                    {
                        "fact_type": "livestock.treatment_applied",
                        "occurred_at": (transferencia - timedelta(days=30)).isoformat(),
                        "asserted_by": "Fazenda Origem Documental",
                        "confidence_tier": "CRYPTOGRAPHICALLY_ATTESTED",
                        "payload": {
                            "withdrawal_period_days": 45,
                            "substance": "produto ficticio",
                        },
                    }
                ],
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["artifact"]["issuer_name"] == "Fazenda Origem Documental"
            and r["imported_facts"][0]["origin"] == "IMPORTED_ASSERTION"
            and r["imported_facts"][0]["source_artifact_id"] == r["artifact"]["artifact_id"]
            else "aquisicao composta nao preservou artefato, origem e vinculo do fato"
        ),
        guardar=lambda r: ids.update(
            artifact_id=str(r["artifact"]["artifact_id"]),
            imported_fact_id=str(r["imported_facts"][0]["imported_fact_id"]),
        ),
        porque=(
            "O caso de uso aprovado e minimo: um orchestration service explicito sobre conceitos "
            "ja existentes, sem aggregate novo."
        ),
    )
    roteiro.passo(
        "3",
        "Operador relista os artefatos do animal",
        lambda: operador.get(
            f"/v1/livestock/animals/{ids['animal_id']}/received-transfer-artifacts"
        ),
        200,
        conferir=lambda r: (
            None
            if r["items"][0]["artifact_id"] == ids["artifact_id"]
            and r["items"][0]["coverage"]["known_until"]
            else "artefato composto nao reapareceu na consulta"
        ),
        porque="A auditoria precisa reencontrar a cobertura declarada sem recalculo silencioso.",
    )
    roteiro.passo(
        "4",
        "Operador relista os fatos importados do animal",
        lambda: operador.get(f"/v1/livestock/animals/{ids['animal_id']}/imported-facts"),
        200,
        conferir=lambda r: (
            None
            if r["items"][0]["imported_fact_id"] == ids["imported_fact_id"]
            and r["items"][0]["asserted_by"] == "Fazenda Origem Documental"
            else "fato importado nao preservou autoria externa"
        ),
        porque=(
            "Importar nao transforma a Organization de destino em autora do tratamento recebido."
        ),
    )
    roteiro.passo(
        "5",
        "Operador executa elegibilidade para provar que o fato importado entra na decisao",
        lambda: operador.post(f"/v1/livestock/animals/{ids['animal_id']}/eligibility"),
        201,
        conferir=lambda r: (
            None if r["result"] == "rejeitada" and r["reasons"] else "elegibilidade ignorou o fato"
        ),
        porque=(
            "O historico importado nao e apenas arquivo: ele compoe o snapshot auditavel usado na "
            "decisao."
        ),
    )
    return roteiro


def _criar_cenario(operador: Cliente, ids: dict[str, str]) -> object:
    propriedade = operador.post(
        "/v1/livestock/properties",
        {
            "code": f"PROP-{uuid4().hex[:8]}",
            "name": "Fazenda Destino Aquisicao Documental",
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
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        {
            "name": "Fazenda Origem Documental",
            "counterparty_type": "FARM",
            "identifiers": [f"CAR:MT-{uuid4().hex[:12]}"],
        },
    )
    if contraparte.status == 201:
        ids["animal_id"] = str(animal["animal_id"])
        ids["counterparty_id"] = str(contraparte["counterparty_id"])
    return contraparte


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro da aquisicao documental composta.")
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
