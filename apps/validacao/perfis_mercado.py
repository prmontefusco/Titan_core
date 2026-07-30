"""Roteiro executavel da listagem de perfis de mercado.

python -m uv run --locked python -m apps.validacao.perfis_mercado
python -m uv run --locked python -m apps.validacao.perfis_mercado --pausar
"""

import argparse
import os
import sys

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro
from packages.livestock_application.market_eligibility import MarketEligibilityPurpose


def _perfis_tem_forma_esperada(items: list[dict[str, object]]) -> bool:
    por_mercado = {str(item.get("market")): item for item in items}
    china = por_mercado.get(MarketEligibilityPurpose.EXPORTACAO_CHINA.code)
    eua = por_mercado.get(MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code)
    ue = por_mercado.get(MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA.code)
    if set(por_mercado) != {
        MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
        MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
        MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA.code,
    }:
        return False
    if not isinstance(china, dict) or not isinstance(eua, dict) or not isinstance(ue, dict):
        return False
    requisitos_china = china.get("requirements")
    requisitos_eua = eua.get("requirements")
    requisitos_ue = ue.get("requirements")
    return (
        eua.get("declared_withdrawal_period_days") == 30
        and isinstance(requisitos_eua, list)
        and len(requisitos_eua) == 1
        and isinstance(requisitos_ue, list)
        and len(requisitos_ue) == 3
        and isinstance(requisitos_china, list)
        and len(requisitos_china) == 2
        and requisitos_china[1].get("dependent_subject_key") == "slaughterhouse"
        and requisitos_china[1].get("dependent_subject_label") == "estabelecimento"
    )


def _montar_roteiro(operador: Cliente) -> Roteiro:
    roteiro = Roteiro("Perfis de mercado suportados", diario=operador.diario)
    roteiro.passo(
        "1",
        "Operador consulta os perfis publicados de mercado",
        lambda: operador.get("/v1/livestock/market-eligibility/profiles"),
        200,
        conferir=lambda r: (
            None if _perfis_tem_forma_esperada(r) else "perfis nao refletiram os mercados esperados"
        ),
        porque=(
            "Antes de pedir uma avaliacao, a integracao precisa descobrir quais "
            "mercados existem e quais dependencias adicionais cada um exige."
        ),
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro da listagem de perfis de mercado.")
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
