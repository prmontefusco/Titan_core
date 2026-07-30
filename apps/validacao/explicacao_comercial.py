"""Roteiro executavel da explicacao comercial orientada a mercado.

python -m uv run --locked python -m apps.validacao.explicacao_comercial
python -m uv run --locked python -m apps.validacao.explicacao_comercial --pausar
"""

import argparse
import os
import sys
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.matriz_elegibilidade_mercados import _preparar_regras_de_mercado
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro
from packages.livestock_application.market_eligibility import MarketEligibilityPurpose


def _criar_animal(operador: Cliente, ids: dict[str, str]) -> object:
    codigo = uuid4().hex[:8]
    propriedade = operador.post(
        "/v1/livestock/properties",
        {
            "code": f"PROP-{codigo}",
            "name": "Fazenda Explicacao Comercial",
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


def _criar_lote(operador: Cliente, ids: dict[str, str]) -> object:
    for chave in ("animal_lote_1", "animal_lote_2"):
        animal = operador.post(
            "/v1/livestock/animals",
            {"birth_property_id": ids["property_id"], "sex": "MALE"},
        )
        if animal.status != 201:
            return animal
        ids[chave] = str(animal["animal_id"])
    lote = operador.post(
        "/v1/livestock/lots",
        {
            "property_id": ids["property_id"],
            "code": f"LOT-{uuid4().hex[:8]}",
            "name": "Lote Explicacao Comercial",
        },
    )
    if lote.status != 201:
        return lote
    ids["lot_id"] = str(lote["lot_id"])
    for chave in ("animal_lote_1", "animal_lote_2"):
        vinculo = operador.post(
            f"/v1/livestock/lots/{ids['lot_id']}/members",
            {"animal_id": ids[chave]},
        )
        if vinculo.status != 201:
            return vinculo
    return lote


def _montar_roteiro(operador: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("Explicacao comercial executiva por mercado", diario=operador.diario)
    roteiro.passo(
        "1",
        "Operador cria o animal base da explicacao",
        lambda: _criar_animal(operador, ids),
        201,
        conferir=lambda r: None if ids.get("animal_id") else "animal base nao foi criado",
        porque="A explicacao executiva precisa nascer de um sujeito real da vertical.",
    )
    roteiro.passo(
        "2",
        "Operador pede a explicacao comercial do animal para China e EUA",
        lambda: operador.post(
            "/v1/livestock/market-eligibility/commercial-explanations",
            {
                "animal_id": ids["animal_id"],
                "markets": [
                    MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                    MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
                ],
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["subject_type"] == "animal"
            and r["commercial_outlook"] == "PARCIALMENTE_COMERCIALIZAVEL"
            and "China" in r["narrative"]
            and "Estados Unidos" in r["narrative"]
            and r["recommended_next_action"]
            == "Selecionar e qualificar o estabelecimento exigido para os mercados condicionados."
            else "a explicacao comercial do animal nao resumiu corretamente os mercados"
        ),
        porque=(
            "A resposta precisa falar a lingua do negocio: onde pode vender, "
            "onde nao pode e qual a proxima acao para desbloquear."
        ),
    )
    roteiro.passo(
        "3",
        "Operador cria o lote com dois animais vigentes",
        lambda: _criar_lote(operador, ids),
        201,
        conferir=lambda r: None if ids.get("lot_id") else "lote nao foi criado",
        porque="O mesmo tipo de leitura executiva precisa existir tambem para o conjunto.",
    )
    roteiro.passo(
        "4",
        "Operador pede a explicacao comercial do lote para China e EUA",
        lambda: operador.post(
            "/v1/livestock/market-eligibility/commercial-explanations",
            {
                "lot_id": ids["lot_id"],
                "markets": [
                    MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                    MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
                ],
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["subject_type"] == "lot"
            and r["commercial_outlook"] == "PARCIALMENTE_COMERCIALIZAVEL"
            and "O lote pode ser comercializado" in r["narrative"]
            and r["recommended_next_action"]
            == "Selecionar e qualificar o estabelecimento exigido para os mercados condicionados."
            else "a explicacao comercial do lote nao resumiu corretamente o conjunto"
        ),
        porque=(
            "O lote precisa devolver a mesma resposta executiva, so que agora "
            "agregando os animais vigentes do conjunto."
        ),
    )
    roteiro.passo(
        "5",
        "Operador tenta pedir a explicacao sem informar sujeito",
        lambda: operador.post("/v1/livestock/market-eligibility/commercial-explanations", {}),
        422,
        conferir=lambda r: (
            None if r["reason_code"] == "ENTRADA_INVALIDA" else "entrada invalida nao foi recusada"
        ),
        porque="A API nao pode adivinhar se a pergunta e sobre um animal ou sobre um lote.",
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro da explicacao comercial executiva.")
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
