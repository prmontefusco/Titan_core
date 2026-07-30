"""Roteiro executavel do endpoint orientado a mercado.

python -m uv run --locked python -m apps.validacao.mercados_orientados
python -m uv run --locked python -m apps.validacao.mercados_orientados --pausar
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
            "name": "Fazenda Mercados",
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


def _mercados_resolvidos(items: list[dict[str, object]], esperados: set[str]) -> bool:
    return {str(item.get("market")) for item in items} == esperados


def _montar_roteiro(operador: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro(
        "Endpoint orientado a mercado",
        diario=operador.diario,
    )
    roteiro.passo(
        "1",
        "Operador cria a propriedade e o animal base",
        lambda: _criar_animal(operador, ids),
        201,
        conferir=lambda r: None if ids.get("animal_id") else "animal nao foi criado",
        porque="O endpoint novo continua avaliando um sujeito real da vertical.",
    )
    roteiro.passo(
        "2",
        "Operador pede somente China e EUA",
        lambda: operador.post(
            "/v1/livestock/market-eligibility/evaluations",
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
            if r["requested_markets"]
            == [
                MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
            ]
            and r["commercial_outlook"] == "PARCIALMENTE_COMERCIALIZAVEL"
            and r["can_sell_to_any_requested_market"] is True
            and "ao menos um mercado solicitado elegivel" in r["executive_summary"]
            and r["eligible_markets"] == [MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code]
            and r["blocked_markets"] == []
            and r["conditioned_markets"] == [MarketEligibilityPurpose.EXPORTACAO_CHINA.code]
            and r["indeterminate_markets"] == []
            and r["missing_markets"] == []
            and r["required_subjects"]
            == [
                {
                    "market": MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                    "subject_key": "slaughterhouse",
                    "subject_label": "estabelecimento",
                }
            ]
            and bool(r["market_gaps"])
            and r["market_gaps"][0]["market"] == MarketEligibilityPurpose.EXPORTACAO_CHINA.code
            and r["market_gaps"][0]["code"] == "DEPENDENCIA_DE_SUJEITO_NAO_ESCOLHIDO"
            and _mercados_resolvidos(
                r["markets"],
                {
                    MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                    MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
                },
            )
            else "a resposta nao refletiu os mercados solicitados"
        ),
        porque=(
            "O cliente passa a pensar no objetivo comercial; o servidor resolve "
            "internamente o conjunto de regras esperado para cada mercado."
        ),
    )
    roteiro.passo(
        "3",
        "Operador tenta um mercado inexistente",
        lambda: operador.post(
            "/v1/livestock/market-eligibility/evaluations",
            {
                "animal_id": ids["animal_id"],
                "markets": ["exportacao-marte"],
            },
        ),
        422,
        conferir=lambda r: (
            None if r["reason_code"] == "ENTRADA_INVALIDA" else "mercado invalido nao foi recusado"
        ),
        porque="Mercado desconhecido precisa falhar fechado, e nao virar perfil vazio.",
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro do endpoint orientado a mercado.")
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
