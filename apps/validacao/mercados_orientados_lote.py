"""Roteiro executavel do endpoint orientado a mercado para lote.

python -m uv run --locked python -m apps.validacao.mercados_orientados_lote
python -m uv run --locked python -m apps.validacao.mercados_orientados_lote --pausar
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.matriz_elegibilidade_mercados import _preparar_regras_de_mercado
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro
from packages.livestock_application.market_eligibility import MarketEligibilityPurpose


def _criar_cenario(operador: Cliente, ids: dict[str, str]) -> object:
    codigo = uuid4().hex[:8]
    propriedade = operador.post(
        "/v1/livestock/properties",
        {
            "code": f"PROP-{codigo}",
            "name": "Fazenda Lote Mercados",
            "municipality": "Cuiaba",
            "state_code": "MT",
        },
    )
    if propriedade.status != 201:
        return propriedade
    ids["property_id"] = str(propriedade["property_id"])
    for chave in ("animal_1", "animal_2"):
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
            "name": "Lote Mercado",
        },
    )
    if lote.status != 201:
        return lote
    ids["lot_id"] = str(lote["lot_id"])
    for chave in ("animal_1", "animal_2"):
        vinculo = operador.post(
            f"/v1/livestock/lots/{ids['lot_id']}/members",
            {"animal_id": ids[chave]},
        )
        if vinculo.status != 201:
            return vinculo
    return lote


def _criar_contraparte_externa(operador: Cliente, ids: dict[str, str]) -> object:
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        {
            "name": "Frigorifico Lote Validacao",
            "counterparty_type": "SLAUGHTERHOUSE",
        },
    )
    if contraparte.status == 201:
        ids["slaughterhouse_id"] = str(contraparte["counterparty_id"])
    return contraparte


def _registrar_qualificacao(operador: Cliente, ids: dict[str, str]) -> object:
    return operador.post(
        f"/v1/livestock/external-counterparties/{ids['slaughterhouse_id']}/establishment-qualifications",
        {
            "market_purpose": MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
            "status": "HABILITADO",
            "source_name": "lista-sif-ficticia",
            "source_version": "2026-07",
            "assessed_at": datetime.now(UTC).isoformat(),
        },
    )


def _montar_roteiro(operador: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("Endpoint orientado a mercado para lote", diario=operador.diario)
    roteiro.passo(
        "1",
        "Operador cria propriedade, dois animais e o lote vigente",
        lambda: _criar_cenario(operador, ids),
        201,
        conferir=lambda r: None if ids.get("lot_id") else "lote nao foi criado",
        porque="A avaliacao comercial do lote nasce da composicao vigente dele.",
    )
    roteiro.passo(
        "2",
        "Operador pede China e EUA para o lote",
        lambda: operador.post(
            "/v1/livestock/market-eligibility/lots/evaluations",
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
            if r["member_count"] == 2
            and r["commercial_outlook"] == "PARCIALMENTE_COMERCIALIZAVEL"
            and r["eligible_markets"] == [MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code]
            and r["conditioned_markets"] == [MarketEligibilityPurpose.EXPORTACAO_CHINA.code]
            and r["required_subjects"]
            == [
                {
                    "market": MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                    "subject_key": "slaughterhouse",
                    "subject_label": "estabelecimento",
                }
            ]
            else "a resposta nao refletiu a agregacao comercial esperada do lote"
        ),
        porque=(
            "O lote precisa responder comercialmente como conjunto: EUA libera, "
            "China continua condicionada enquanto faltar o frigorifico."
        ),
    )
    roteiro.passo(
        "3",
        "Operador cadastra o frigorifico e registra a qualificacao para a China",
        lambda: _criar_contraparte_externa(operador, ids),
        201,
        conferir=lambda r: None if ids.get("slaughterhouse_id") else "frigorifico nao foi criado",
        porque=(
            "Mercado condicionado deve virar elegivel quando o sujeito "
            "dependente for escolhido e habilitado."
        ),
    )
    roteiro.passo(
        "4",
        "Operador confirma a qualificacao do frigorifico escolhido",
        lambda: _registrar_qualificacao(operador, ids),
        201,
        conferir=lambda r: (
            None if r["status"] == "HABILITADO" else "qualificacao nao foi registrada"
        ),
        porque=(
            "A regra da China depende de uma qualificacao publicada "
            "para o estabelecimento selecionado."
        ),
    )
    roteiro.passo(
        "5",
        "Operador repete a avaliacao do lote agora com o frigorifico escolhido",
        lambda: operador.post(
            "/v1/livestock/market-eligibility/lots/evaluations",
            {
                "lot_id": ids["lot_id"],
                "markets": [
                    MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                    MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
                ],
                "slaughterhouse_counterparty_id": ids["slaughterhouse_id"],
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["commercial_outlook"] == "TOTALMENTE_COMERCIALIZAVEL"
            and r["eligible_markets"]
            == [
                MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
            ]
            and r["conditioned_markets"] == []
            and r["required_subjects"] == []
            else "o lote nao passou a refletir o frigorifico escolhido"
        ),
        porque=(
            "Quando o frigorifico exigido e informado e esta habilitado, a China "
            "deixa de ser pendencia e entra no conjunto comercializavel do lote."
        ),
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(
        description="Roteiro do endpoint orientado a mercado para lote."
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
